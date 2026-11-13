import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import webview
from backup import scheduler
from backup.config import (
    add_profile, get_profile, list_profiles, remove_profile, update_profile,
    add_group, get_group, list_groups, remove_group, update_group,
    add_restore, get_restore, list_restores, remove_restore, update_restore,
    add_schedule as _cfg_add_schedule,
    remove_schedule as _cfg_remove_schedule,
    list_schedules,
    get_theme, set_theme,
)
from backup.core import restore_backup as _restore, run_backup as _run_backup

# Importer les chemins depuis le module parent
from timestamp import DATA_DIR, RUNTIME_DIR, CONFIG_DIR, ensure_directories

# Ensure directories exist
ensure_directories()

logger = logging.getLogger(__name__)

# Set project directory for backup.config
import backup.config
backup.config._project_root = CONFIG_DIR

_ROOT = CONFIG_DIR
_LOGS_DIR = DATA_DIR / "logs"

# Minimum interval between progress bar refreshes.
_PROGRESS_INTERVAL = 0.08


def _short_path(path) -> str:
    """Chemin raccourci pour l'affichage dans la barre de progression."""
    text = str(path).replace("\\", "/")
    return text[-70:]


def _throttled(emit, interval: float = _PROGRESS_INTERVAL):
    """Limit the frequency of progress callbacks."""
    last = [0.0]

    def callback(current, total, path):
        now = time.monotonic()
        if current != total and now - last[0] < interval:
            return
        last[0] = now
        emit(current, total, path)

    return callback


def _percent(current, total) -> int:
    return int(current / total * 100) if total else 100


class BackupAPI:
    def __init__(self):
        self._window = None

    @property
    def window(self):
        if self._window is None and webview.windows:
            self._window = webview.windows[0]
        return self._window

    @window.setter
    def window(self, val):
        self._window = val

    def _js(self, func: str, *args) -> None:
        """Appelle une fonction JS avec des arguments serialises en JSON."""
        window = self.window
        if window is None:
            return
        payload = ", ".join(
            json.dumps(a, ensure_ascii=False, default=str) for a in args
        )
        try:
            window.evaluate_js(f"{func}({payload})")
        except Exception as e:
            logger.warning("evaluate_js %s a echoue : %s", func, e)

    # ── Profiles ──────────────────────────────────────────────────────

    def get_profiles(self):
        return list_profiles()

    def add_profile(self, name: str, sources: list, destination: str, compress: bool):
        try:
            add_profile(name, sources, destination, compress)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def update_profile(self, old_name: str, name: str, sources: list, destination: str, compress: bool):
        try:
            update_profile(old_name, name, sources, destination, compress)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def remove_profile(self, name: str):
        return {"ok": remove_profile(name)}

    # ── Groups ────────────────────────────────────────────────────────

    def get_groups(self):
        return list_groups()

    def add_group(self, name: str, profiles: list):
        try:
            add_group(name, profiles)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def update_group(self, old_name: str, name: str, profiles: list):
        try:
            update_group(old_name, name, profiles)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def remove_group(self, name: str):
        return {"ok": remove_group(name)}

    def run_group(self, group_name: str, full: bool = False):
        group = get_group(group_name)
        if not group:
            return {"ok": False, "error": f"Groupe introuvable : {group_name}"}

        profiles = group.get("profiles", [])

        def _task():
            total = {"copied": 0, "skipped": 0, "errors": [], "per_profile": []}
            n = len(profiles)
            for idx, pname in enumerate(profiles, 1):
                profile = get_profile(pname)
                if not profile:
                    total["errors"].append(f"[{pname}] Profil introuvable")
                    total["per_profile"].append(
                        {"profile": pname, "copied": 0, "skipped": 0, "errors": 1}
                    )
                    continue

                def emit(current, total_files, path, _idx=idx, _pname=pname):
                    self._js("updateGroupProgress", _idx, n, _pname,
                             _percent(current, total_files), _short_path(path))

                try:
                    report = _run_backup(
                        sources=profile["sources"],
                        destination=profile["destination"],
                        compress=profile.get("compress", False),
                        incremental=not full,
                        on_progress=_throttled(emit),
                    )
                    total["copied"] += report["copied"]
                    total["skipped"] += report["skipped"]
                    total["errors"].extend(f"[{pname}] {e}" for e in report["errors"])
                    total["per_profile"].append({
                        "profile": pname,
                        "copied": report["copied"],
                        "skipped": report["skipped"],
                        "errors": len(report["errors"]),
                    })
                except Exception as e:
                    total["errors"].append(f"[{pname}] {e}")
                    total["per_profile"].append(
                        {"profile": pname, "copied": 0, "skipped": 0, "errors": 1}
                    )

            self._js("groupBackupComplete", total)

        threading.Thread(target=_task, daemon=True).start()
        return {"ok": True}

    # ── Backup ────────────────────────────────────────────────────────

    def run_backup(self, profile_name: str, full: bool = False, compress=None):
        profile = get_profile(profile_name)
        if not profile:
            return {"ok": False, "error": f"Profil introuvable : {profile_name}"}

        use_compress = profile.get("compress", False) if compress is None else bool(compress)

        def _task():
            def emit(current, total, path):
                self._js("updateProgress", current, total,
                         _percent(current, total), _short_path(path))
            try:
                report = _run_backup(
                    sources=profile["sources"],
                    destination=profile["destination"],
                    compress=use_compress,
                    incremental=not full,
                    on_progress=_throttled(emit),
                )
                self._js("backupComplete", report)
            except Exception as e:
                logger.exception("Backup interrupted")
                self._js("backupError", str(e))

        threading.Thread(target=_task, daemon=True).start()
        return {"ok": True}

    # ── Restore (manuelle) ────────────────────────────────────────────

    def restore(self, source: str, destination: str, incremental: bool = False):
        return self._start_restore(source, destination, incremental, prefix="restore")

    # ── Restore profiles ──────────────────────────────────────────────

    def get_restores(self):
        return list_restores()

    def add_restore(self, name: str, source: str, destination: str,
                    incremental: bool = False):
        try:
            add_restore(name, source, destination, incremental)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def update_restore(self, old_name: str, name: str, source: str,
                       destination: str, incremental: bool = False):
        try:
            update_restore(old_name, name, source, destination, incremental)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def remove_restore(self, name: str):
        return {"ok": remove_restore(name)}

    def run_restore(self, name: str):
        """Lance un profil de restauration enregistre."""
        profile = get_restore(name)
        if not profile:
            return {"ok": False, "error": f"Profil de restauration introuvable : {name}"}
        return self._start_restore(
            profile["source"], profile["destination"],
            profile.get("incremental", False), prefix="restoreProfile",
        )

    def _start_restore(self, source: str, destination: str,
                       incremental: bool, prefix: str):
        """Execute une restauration en tache de fond."""
        if not source or not destination:
            return {"ok": False, "error": "Source et destination sont obligatoires."}

        def _task():
            def emit(current, total, path):
                self._js(f"update{prefix[0].upper()}{prefix[1:]}Progress",
                         current, total, _percent(current, total), _short_path(path))
            try:
                report = _restore(
                    source, destination,
                    incremental=incremental,
                    on_progress=_throttled(emit),
                )
                self._js(f"{prefix}Complete", report)
            except Exception as e:
                logger.exception("Restore interrupted")
                self._js(f"{prefix}Error", str(e))

        threading.Thread(target=_task, daemon=True).start()
        return {"ok": True}

    # ── Schedules ─────────────────────────────────────────────────────

    @staticmethod
    def _schedule_args(sched_type: str, target: str) -> list:
        """Arguments passes au wrapper timestamp-backup-cli."""
        if sched_type == "group":
            return ["run", target, "--group"]
        if sched_type == "restore":
            return ["restore", "--profile", target]
        return ["run", target]

    def get_schedules(self):
        return list_schedules()

    def get_scheduler_info(self):
        return {"backend": scheduler.backend(), "label": scheduler.backend_label()}

    def add_schedule(self, name: str, target: str, sched_type: str, frequency: str,
                     time: str = "02:00", day: str = None):
        try:
            warning = scheduler.create(
                name, self._schedule_args(sched_type, target), frequency, time, day
            )
            _cfg_add_schedule(name, target, frequency, sched_type, time, day)
            res = {"ok": True}
            if warning:
                res["warning"] = warning
            return res
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def update_schedule(self, old_name: str, name: str, target: str, sched_type: str,
                        frequency: str, time: str = "02:00", day: str = None):
        try:
            scheduler.delete(old_name)
            warning = scheduler.create(
                name, self._schedule_args(sched_type, target), frequency, time, day
            )
            _cfg_remove_schedule(old_name)
            _cfg_add_schedule(name, target, frequency, sched_type, time, day)
            res = {"ok": True}
            if warning:
                res["warning"] = warning
            return res
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def remove_schedule(self, name: str):
        try:
            scheduler.delete(name)
            _cfg_remove_schedule(name)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Network Shares ───────────────────────────────────────────────

    def get_network_shares(self):
        from backup.netshares import list_shares
        return list_shares()

    def add_network_share(self, name: str, server: str, share: str, subpath: str,
                          username: str, password: str, domain: str = ""):
        try:
            from backup.netshares import add_share
            add_share(name, server, share, subpath, username, password, domain)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def update_network_share(self, old_name: str, name: str, server: str, share: str,
                             subpath: str, username: str, password: str, domain: str = ""):
        try:
            from backup.netshares import update_share
            update_share(old_name, name, server, share, subpath, username, password, domain)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def remove_network_share(self, name: str):
        try:
            from backup.netshares import remove_share
            return {"ok": remove_share(name)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def mount_network_share(self, name: str):
        try:
            from backup.netshares import mount_share
            ok, msg = mount_share(name)
            return {"ok": ok, "message": msg}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def unmount_network_share(self, name: str):
        try:
            from backup.netshares import unmount_share
            ok, msg = unmount_share(name)
            return {"ok": ok, "message": msg}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    # ── Logs ──────────────────────────────────────────────────────────

    def get_logs(self) -> list:
        if not _LOGS_DIR.exists():
            return []
        files = sorted(_LOGS_DIR.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)
        return [
            {
                "name": f.name,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M"),
            }
            for f in files
        ]

    def get_log_content(self, filename: str) -> str:
        target = (_LOGS_DIR / Path(filename).name).resolve()
        if target.parent != _LOGS_DIR.resolve() or not target.exists():
            return ""
        return target.read_text(encoding="utf-8", errors="replace")

    def clear_logs(self) -> dict:
        deleted = 0
        for f in _LOGS_DIR.glob("*.log"):
            try:
                f.unlink()
                deleted += 1
            except Exception:
                pass
        return {"ok": True, "deleted": deleted}

    # ── Theme ─────────────────────────────────────────────────────────

    def get_theme(self) -> str:
        return get_theme()

    def set_theme(self, theme: str) -> dict:
        try:
            return {"ok": True, "theme": set_theme(theme)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Shortcut ──────────────────────────────────────────────────────

    def create_shortcut(self) -> dict:
        try:
            if sys.platform == "win32":
                return self._shortcut_windows()
            return self._shortcut_linux()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _shortcut_windows(self) -> dict:
        import ctypes

        def ps_quote(value: str) -> str:
            return "'" + str(value).replace("'", "''") + "'"

        desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
        if not desktop.exists():
            desktop = Path.home() / "Desktop"
        lnk = desktop / "Timestamp.lnk"
        # Use pythonw.exe to avoid console window
        pythonw = Path(sys.executable).parent / "pythonw.exe"
        ico = RUNTIME_DIR / "icon.ico"
        icon_line = f"$s.IconLocation = {ps_quote(ico)};" if ico.exists() else ""
        ps = (
            f"$ws = New-Object -comObject WScript.Shell;"
            f"$s = $ws.CreateShortcut({ps_quote(lnk)});"
            f"$s.TargetPath = {ps_quote(pythonw)};"
            f"$s.Arguments = '-m timestamp.app';"
            f"$s.WorkingDirectory = {ps_quote(sys.prefix)};"
            f"{icon_line}"
            f"$s.Save()"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if r.returncode != 0:
            return {"ok": False, "error": r.stderr.strip() or r.stdout.strip()}
        try:
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        except Exception:
            pass
        return {"ok": True, "path": str(lnk)}

    def _shortcut_linux(self) -> dict:
        import stat

        png = RUNTIME_DIR / "icon.png"
        content = (
            "[Desktop Entry]\n"
            "Version=1.0\n"
            "Type=Application\n"
            "Name=Timestamp\n"
            "Comment=Logiciel de sauvegarde\n"
            "Exec=timestamp-backup-gui\n"
            f"Icon={png if png.exists() else 'drive-harddisk'}\n"
            "Terminal=false\n"
            "StartupNotify=true\n"
            "Categories=Utility;Archiving;Backup;\n"
        )

        try:
            xdg = subprocess.run(["xdg-user-dir", "DESKTOP"],
                                 capture_output=True, text=True, timeout=10)
            desktop = Path(xdg.stdout.strip()) if xdg.returncode == 0 and xdg.stdout.strip() \
                else Path.home() / "Desktop"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            desktop = Path.home() / "Desktop"

        written = []
        for directory in (desktop, Path.home() / ".local" / "share" / "applications"):
            try:
                directory.mkdir(parents=True, exist_ok=True)
                target = directory / "Timestamp.desktop"
                target.write_text(content, encoding="utf-8")
                target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                written.append(str(target))
            except OSError as e:
                logger.warning("Raccourci non cree dans %s : %s", directory, e)

        if not written:
            return {"ok": False, "error": "Impossible d'ecrire le fichier .desktop."}

        for cmd in (["gio", "set", written[0], "metadata::trusted", "true"],
                    ["update-desktop-database", str(Path.home() / ".local/share/applications")]):
            try:
                subprocess.run(cmd, capture_output=True, timeout=10)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        return {"ok": True, "path": written[0]}

    # ── File dialogs ──────────────────────────────────────────────────

    def pick_folder(self):
        window = self.window
        if window is None:
            return None
        result = window.create_file_dialog(webview.FOLDER_DIALOG)
        return result[0] if result else None

    def pick_file(self):
        window = self.window
        if window is None:
            return None
        result = window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=(
                "Archives (*.zip;*.tar.gz;*.tgz;*.tar.bz2;*.tar.xz;*.tar)",
                "Tous les fichiers (*.*)",
            ),
        )
        return result[0] if result else None
