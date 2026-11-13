"""Planification des tâches, multi-plateforme.

Trois moteurs sont pris en charge, choisis automatiquement :

  - Windows : le Planificateur de tâches (``schtasks``), sous le dossier
    ``\\Timestamp``.
  - Linux avec cron : la crontab de l'utilisateur, chaque ligne étant marquée
    par un commentaire ``# timestamp:<nom>`` qui sert de clé.
  - Linux sans cron : des timers systemd utilisateur.

L'appelant fournit la commande sous forme de liste d'arguments passés au
wrapper (``timestamp-cli``), par exemple ``["run", "Documents"]``
ou ``["restore", "--profile", "Documents"]``.
"""
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

_DAYS_CRON = {"MON": "1", "TUE": "2", "WED": "3", "THU": "4",
              "FRI": "5", "SAT": "6", "SUN": "0"}
_DAYS_SYSTEMD = {"MON": "Mon", "TUE": "Tue", "WED": "Wed", "THU": "Thu",
                 "FRI": "Fri", "SAT": "Sat", "SUN": "Sun"}
# Index Python (lundi = 0) des codes utilisés par l'interface, pour retrouver
# l'abréviation localisée attendue par schtasks.
_DAYS_INDEX = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_NAME_RE = re.compile(r"^[^\x00-\x1f\\/:*?\"<>|%$`\n\r]{1,64}$")


def validate_name(name: str) -> None:
    """Refuse les noms qui casseraient la crontab, schtasks ou une unité systemd."""
    if not name or not name.strip():
        raise ValueError("Le nom de la planification ne peut pas être vide.")
    if not _NAME_RE.match(name):
        raise ValueError(
            "Nom invalide. Évitez les caractères \\ / : * ? \" < > | % $ ` "
            "et limitez-vous à 64 caractères."
        )


def _wrapper() -> str:
    """Retourne le chemin du wrapper CLI."""
    if sys.platform == "win32":
        # Sous Windows, on utilise le script timestamp-cli
        return str(_ROOT / "timestamp-cli")
    # Sous Linux/Unix, on utilise timestamp-cli qui est dans PATH
    return "timestamp-cli"


def _split_time(time: str) -> tuple[str, str]:
    try:
        h, m = time.split(":")[:2]
        return f"{int(h):02d}", f"{int(m):02d}"
    except (ValueError, AttributeError):
        return "02", "00"


def backend() -> str:
    """Moteur de planification utilisé sur cette machine."""
    if sys.platform == "win32":
        return "schtasks"
    if shutil.which("crontab"):
        return "crontab"
    if shutil.which("systemctl"):
        return "systemd"
    return "none"


def backend_label() -> str:
    return {
        "schtasks": "Planificateur de tâches Windows",
        "crontab":  "cron (crontab utilisateur)",
        "systemd":  "timers systemd utilisateur",
        "none":     "aucun moteur disponible",
    }[backend()]


def create(name: str, args: list[str], frequency: str,
           time: str = "02:00", day: str | None = None) -> str | None:
    """Crée (ou remplace) une planification. Retourne un avertissement éventuel."""
    validate_name(name)
    engine = backend()
    if engine == "schtasks":
        return _schtasks_create(name, args, frequency, time, day)
    if engine == "crontab":
        return _cron_add(name, args, frequency, time, day)
    if engine == "systemd":
        return _systemd_add(name, args, frequency, time, day)
    raise RuntimeError(
        "Aucun moteur de planification disponible. Installez cron "
        "(Debian/Kali : sudo apt install cron — Arch/CachyOS : sudo pacman -S cronie)."
    )


def delete(name: str) -> None:
    """Supprime une planification.

    On nettoie tous les moteurs disponibles, pas seulement celui actif :
    une entrée créée avec cron doit disparaître même si cron a été désinstallé
    entre-temps, et inversement.
    """
    if sys.platform == "win32":
        _schtasks_delete(name)
        return
    if shutil.which("crontab"):
        try:
            _cron_remove(name)
        except Exception:
            pass
    if shutil.which("systemctl"):
        _systemd_remove(name)


# ── Windows : schtasks ────────────────────────────────────────────────

def _task_name(name: str) -> str:
    return f"Timestamp\\{name}"


def _localized_day(day: str) -> str | None:
    """Abréviation du jour dans la langue de Windows."""
    idx = _DAYS_INDEX.get(day)
    if idx is None:
        return None
    ps = ("$d=(Get-Culture).DateTimeFormat.AbbreviatedDayNames;"
          f"$d[({idx}+1)%7].ToUpper()")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=15,
                           creationflags=_NO_WINDOW)
    except Exception:
        return None
    out = r.stdout.strip()
    return out or None


def _schtasks_create(name, args, frequency, time, day) -> str | None:
    tr = " ".join([f'"{_wrapper()}"'] + [f'"{a}"' for a in args])
    h, m = _split_time(time)

    base = ["schtasks", "/create", "/tn", _task_name(name), "/tr", tr, "/f"]
    if frequency == "hourly":
        base += ["/sc", "HOURLY", "/mo", "1"]
    elif frequency == "weekly":
        base += ["/sc", "WEEKLY", "/st", f"{h}:{m}"]
    else:
        base += ["/sc", "DAILY", "/st", f"{h}:{m}"]

    def _run(cmd):
        return subprocess.run(cmd, capture_output=True, text=True,
                              creationflags=_NO_WINDOW)

    if frequency == "weekly":
        code = day or "MON"
        r = _run(base + ["/d", code])
        if r.returncode != 0:
            localized = _localized_day(code)
            if localized and localized != code:
                r = _run(base + ["/d", localized])
    else:
        r = _run(base)

    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip()
                           or "Echec de creation de la tache planifiee.")
    return None


def _schtasks_delete(name) -> None:
    subprocess.run(["schtasks", "/delete", "/tn", _task_name(name), "/f"],
                   capture_output=True, text=True, creationflags=_NO_WINDOW)


# ── Linux : cron ──────────────────────────────────────────────────────

def _cron_command(args: list[str]) -> str:
    """Genere la commande pour cron."""
    # Utiliser timestamp-cli qui est dans PATH
    cmd = "timestamp-cli " + " ".join([shlex.quote(a) for a in args])
    return cmd.replace("%", r"\%")


def _cron_line(name, args, frequency, time, day) -> str:
    h, m = _split_time(time)
    if frequency == "hourly":
        schedule = "0 * * * *"
    elif frequency == "weekly":
        schedule = f"{m} {h} * * {_DAYS_CRON.get(day or 'MON', '1')}"
    else:
        schedule = f"{m} {h} * * *"
    return f"{schedule} {_cron_command(args)} # timestamp:{name}"


def _cron_missing() -> RuntimeError:
    return RuntimeError(
        "La commande 'crontab' est introuvable. Installez cron "
        "(Debian/Kali : sudo apt install cron — Arch/CachyOS : sudo pacman -S cronie), "
        "ou relancez l'installation."
    )


def _cron_read() -> str:
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    except FileNotFoundError:
        raise _cron_missing()
    return r.stdout if r.returncode == 0 else ""


def _cron_write(content: str) -> None:
    try:
        r = subprocess.run(["crontab", "-"], input=content,
                           capture_output=True, text=True)
    except FileNotFoundError:
        raise _cron_missing()
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "Echec d'ecriture de la crontab.")


def _cron_daemon_warning() -> str | None:
    """Verifie qu'un demon cron tourne."""
    if not shutil.which("systemctl"):
        return None
    for service in ("cron", "cronie", "crond"):
        try:
            r = subprocess.run(["systemctl", "is-active", service],
                               capture_output=True, text=True, timeout=10)
        except Exception:
            return None
        if r.stdout.strip() == "active":
            return None
    return ("Aucun service cron actif detecte — la planification ne "
            "s'executera pas tant qu'il ne l'est pas. "
            "Debian/Kali : sudo systemctl enable --now cron — "
            "Arch/CachyOS : sudo pacman -S cronie && sudo systemctl enable --now cronie.")


def _cron_add(name, args, frequency, time, day) -> str | None:
    lines = [l for l in _cron_read().splitlines() if f"# timestamp:{name}" not in l]
    lines.append(_cron_line(name, args, frequency, time, day))
    _cron_write("\n".join(lines) + "\n")
    return _cron_daemon_warning()


def _cron_remove(name) -> None:
    lines = [l for l in _cron_read().splitlines() if f"# timestamp:{name}" not in l]
    _cron_write("\n".join(lines) + "\n")


# ── Linux : timers systemd utilisateur ────────────────────────────────

def _unit_slug(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]", "_", name)
    return f"timestamp-{slug}"


def _systemd_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "systemd" / "user"


def _systemctl(*args, check: bool = False):
    r = subprocess.run(["systemctl", "--user", *args],
                       capture_output=True, text=True, timeout=30)
    if check and r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip()
                           or f"systemctl --user {' '.join(args)} a echoue.")
    return r


def _on_calendar(frequency, time, day) -> str:
    h, m = _split_time(time)
    if frequency == "hourly":
        return "*-*-* *:00:00"
    if frequency == "weekly":
        return f"{_DAYS_SYSTEMD.get(day or 'MON', 'Mon')} *-*-* {h}:{m}:00"
    return f"*-*-* {h}:{m}:00"


def _linger_warning() -> str | None:
    """Verifie si linger est active pour les timers utilisateur."""
    if not shutil.which("loginctl"):
        return None
    try:
        r = subprocess.run(
            ["loginctl", "show-user", str(os.getuid()), "--property=Linger"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return None
    if "Linger=yes" in r.stdout:
        return None
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or "$USER"
    return ("Planification creee via un timer systemd utilisateur. Elle ne "
            "s'executera que pendant vos sessions ouvertes ; pour qu'elle "
            f"tourne aussi hors session : sudo loginctl enable-linger {user}.")


def _systemd_add(name, args, frequency, time, day) -> str | None:
    unit = _unit_slug(name)
    directory = _systemd_dir()
    directory.mkdir(parents=True, exist_ok=True)

    exec_start = "timestamp-cli " + " ".join([shlex.quote(a) for a in args])
    (directory / f"{unit}.service").write_text(
        "[Unit]\n"
        f"Description=Timestamp — {name}\n\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"WorkingDirectory={_ROOT}\n"
        f"ExecStart={exec_start}\n",
        encoding="utf-8",
    )
    (directory / f"{unit}.timer").write_text(
        "[Unit]\n"
        f"Description=Timestamp — {name}\n\n"
        "[Timer]\n"
        f"OnCalendar={_on_calendar(frequency, time, day)}\n"
        "Persistent=true\n\n"
        "[Install]\n"
        "WantedBy=timers.target\n",
        encoding="utf-8",
    )

    _systemctl("daemon-reload")
    _systemctl("enable", "--now", f"{unit}.timer", check=True)
    return _linger_warning()


def _systemd_remove(name) -> None:
    unit = _unit_slug(name)
    _systemctl("disable", "--now", f"{unit}.timer")
    directory = _systemd_dir()
    for suffix in (".timer", ".service"):
        try:
            (directory / f"{unit}{suffix}").unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
    _systemctl("daemon-reload")
