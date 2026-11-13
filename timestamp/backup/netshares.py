"""
Gestion des partages réseau pour Timestamp.

Ce module gère la configuration des partages SMB
en utilisant les chemins XDG pour une installation système.
"""

import json
import os
import subprocess
from pathlib import Path

from cryptography.fernet import Fernet

# Importer les chemins depuis le module parent
from timestamp import RUNTIME_DIR, ensure_directories

# S'assurer que les répertoires existent
ensure_directories()


def _get_root() -> Path:
    """Retourne le répertoire racine pour les données runtime."""
    return RUNTIME_DIR


def _key_path() -> Path:
    """Retourne le chemin de la clé de chiffrement."""
    return _get_root() / "net_key.bin"


def _shares_path() -> Path:
    """Retourne le chemin du fichier de configuration des partages."""
    return _get_root() / "net_shares.json"


def _fernet() -> Fernet:
    """Retourne une instance Fernet pour le chiffrement."""
    kp = _key_path()
    kp.parent.mkdir(exist_ok=True)
    if not kp.exists():
        kp.write_bytes(Fernet.generate_key())
        if os.name != "nt":
            os.chmod(kp, 0o600)
    return Fernet(kp.read_bytes())


def _encrypt(plaintext: str) -> str:
    """Chiffre un texte."""
    return _fernet().encrypt(plaintext.encode()).decode() if plaintext else ""


def _decrypt(ciphertext: str) -> str:
    """Déchiffre un texte."""
    if not ciphertext:
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except Exception:
        return ""


def _load() -> dict:
    """Charge la configuration des partages."""
    p = _shares_path()
    if not p.exists():
        return {"shares": {}}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    """Sauvegarde la configuration des partages."""
    p = _shares_path()
    p.parent.mkdir(exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _kiofuse_root(uid: int) -> Path:
    """Retourne le répertoire racine de kio-fuse."""
    return Path(f"/run/user/{uid}/kio-fuse")


def _find_gvfs_mount(server: str, share: str, uid: int) -> str | None:
    """Trouve un point de montage GVFS pour un partage SMB."""
    gvfs = Path(f"/run/user/{uid}/gvfs")
    if not gvfs.exists():
        return None
    for d in gvfs.iterdir():
        if not d.name.startswith("smb-share:"):
            continue
        params = {}
        for part in d.name[len("smb-share:"):].split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = v
        if params.get("server") == server and params.get("share") == share:
            return str(d)
    return None


def _local_path(entry: dict) -> str:
    """Retourne le chemin local pour un partage."""
    server  = entry.get("server", "")
    share   = entry.get("share", "")
    subpath = entry.get("subpath", "")

    if os.name == "nt":
        p = f"\\\\{server}\\{share}"
        if subpath:
            p += "\\" + subpath.replace("/", "\\")
        return p

    uid = os.getuid()

    # KDE: kio-fuse maps smb://server/share -> /run/user/{uid}/kio-fuse/smb/server/share
    kiofuse = _kiofuse_root(uid)
    if os.path.ismount(str(kiofuse)) or \
       "kde" in os.environ.get("XDG_CURRENT_DESKTOP", "").lower():
        p = str(kiofuse / "smb" / server / share)
        if subpath:
            p += f"/{subpath}"
        return p

    # GNOME: scan actual GVFS mount directory
    mount = _find_gvfs_mount(server, share, uid)
    if mount:
        return f"{mount}/{subpath}" if subpath else mount

    # Fallback: kio-fuse path
    p = str(kiofuse / "smb" / server / share)
    if subpath:
        p += f"/{subpath}"
    return p


def _smb_uri(entry: dict) -> str:
    """Retourne l'URI SMB pour un partage."""
    server  = entry.get("server", "")
    share   = entry.get("share", "")
    user    = entry.get("username", "")
    subpath = entry.get("subpath", "")
    base = f"smb://{user}@{server}/{share}" if user else f"smb://{server}/{share}"
    if subpath:
        base += f"/{subpath}"
    return base


def _is_mounted(entry: dict) -> bool:
    """Vérifie si un partage est monté."""
    if os.name == "nt":
        server = entry.get("server", "")
        share  = entry.get("share", "")
        try:
            return Path(f"\\\\{server}\\{share}").exists()
        except OSError:
            return False
    return False


def _public(name: str, entry: dict) -> dict:
    """Retourne les informations publiques pour un partage."""
    return {
        "name":         name,
        "server":       entry.get("server", ""),
        "share":        entry.get("share", ""),
        "subpath":      entry.get("subpath", ""),
        "username":     entry.get("username", ""),
        "domain":       entry.get("domain", ""),
        "has_password": bool(entry.get("password_enc")),
        "smb_uri":      _smb_uri(entry),
        "local_path":   _local_path(entry),
        "mounted":      _is_mounted(entry),
    }


def list_shares() -> dict:
    """Liste tous les partages configurés."""
    data = _load()
    return {k: _public(k, v) for k, v in data["shares"].items()}


def add_share(name: str, server: str, share: str, subpath: str,
              username: str, password: str, domain: str = "") -> dict:
    """Ajoute un nouveau partage."""
    data = _load()
    data["shares"][name] = {
        "server":       server,
        "share":        share,
        "subpath":      subpath.strip("/"),
        "username":     username,
        "password_enc": _encrypt(password),
        "domain":       domain,
    }
    _save(data)
    return _public(name, data["shares"][name])


def update_share(old_name: str, name: str, server: str, share: str, subpath: str,
                 username: str, password: str, domain: str = "") -> dict:
    """Met à jour un partage existant."""
    data = _load()
    old = data["shares"].get(old_name, {})
    pwd_enc = _encrypt(password) if password else old.get("password_enc", "")
    if old_name in data["shares"]:
        del data["shares"][old_name]
    data["shares"][name] = {
        "server":       server,
        "share":        share,
        "subpath":      subpath.strip("/"),
        "username":     username,
        "password_enc": pwd_enc,
        "domain":       domain,
    }
    _save(data)
    return _public(name, data["shares"][name])


def remove_share(name: str) -> bool:
    """Supprime un partage."""
    data = _load()
    if name not in data["shares"]:
        return False
    del data["shares"][name]
    _save(data)
    return True


_NW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def mount_share(name: str) -> tuple[bool, str]:
    """Teste la connexion à un partage."""
    data = _load()
    entry = data["shares"].get(name)
    if not entry:
        return False, f"Partage introuvable : {name}"

    server   = entry["server"]
    share    = entry["share"]
    username = entry.get("username", "")
    password = _decrypt(entry.get("password_enc", ""))
    domain   = entry.get("domain", "")

    if os.name == "nt":
        return _mount_win(server, share, username, password, domain)

    try:
        from backup.smbfs import test_connection
        return test_connection(server, share, username, password, domain)
    except ImportError:
        pass

    return _mount_linux(server, share, username, password)


def unmount_share(name: str) -> tuple[bool, str]:
    """Démonte un partage."""
    data = _load()
    entry = data["shares"].get(name)
    if not entry:
        return False, f"Partage introuvable : {name}"
    if not _is_mounted(entry):
        return True, "Partage deja demonte"
    if os.name == "nt":
        return _unmount_win(entry["server"], entry["share"])
    return _unmount_linux(entry["server"], entry["share"])


def get_share_status(name: str) -> dict:
    """Retourne le statut d'un partage."""
    data = _load()
    entry = data["shares"].get(name)
    if not entry:
        return {"mounted": False, "local_path": ""}
    return {"mounted": _is_mounted(entry), "local_path": _local_path(entry)}


def _mount_linux(server: str, share: str, username: str, password: str) -> tuple[bool, str]:
    """Monte un partage sous Linux."""
    uid = os.getuid()
    kiofuse = _kiofuse_root(uid)

    is_kde = "kde" in os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if is_kde or os.path.ismount(str(kiofuse)):
        if not os.path.ismount(str(kiofuse)):
            r = subprocess.run(
                ["systemctl", "--user", "start", "kio-fuse"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode != 0:
                return False, f"Impossible de demarrer kio-fuse : {r.stderr.strip()}"
            import time; time.sleep(1.5)

        if not os.path.ismount(str(kiofuse)):
            return False, "kio-fuse n'a pas pu demarrer."

        share_path = kiofuse / "smb" / server / share
        try:
            share_path.stat()
            return True, f"Accessible via kio-fuse : {share_path}"
        except FileNotFoundError:
            return False, (
                "kio-fuse actif mais partage inaccessible. "
                "Ouvrez le partage au moins une fois dans Dolphin pour enregistrer "
                "les identifiants dans KWallet, puis reessayez."
            )
        except PermissionError:
            return False, "Acces refuse. Verifiez les identifiants dans KWallet."
        except Exception as e:
            return False, str(e)

    uri = f"smb://{username}@{server}/{share}" if username else f"smb://{server}/{share}"
    try:
        proc = subprocess.Popen(
            ["gio", "mount", uri],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = proc.communicate(input=(password + "\n").encode(), timeout=20)
        if proc.returncode == 0:
            return True, "Monte avec succes"
        msg = (err.decode() + out.decode()).strip()
        return False, msg or "Echec du montage"
    except FileNotFoundError:
        return False, "Commande 'gio' introuvable. Installez gvfs-backends."
    except subprocess.TimeoutExpired:
        return False, "Delai depasse lors du montage"
    except Exception as e:
        return False, str(e)


def _unmount_linux(server: str, share: str) -> tuple[bool, str]:
    """Démonte un partage sous Linux."""
    uid = os.getuid()
    kiofuse = _kiofuse_root(uid)

    if os.path.ismount(str(kiofuse)):
        r = subprocess.run(
            ["systemctl", "--user", "stop", "kio-fuse"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            return True, "kio-fuse arrete (tous les partages deconnectes)"
        return False, r.stderr.strip() or "Impossible d'arreter kio-fuse"

    uri = f"smb://{server}/{share}"
    try:
        r = subprocess.run(
            ["gio", "mount", "--unmount", uri],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            return True, "Demonte"
        return False, r.stderr.strip() or "Echec du demontage"
    except Exception as e:
        return False, str(e)


def _mount_win(server: str, share: str, username: str, password: str, domain: str) -> tuple[bool, str]:
    """Monte un partage sous Windows."""
    unc  = f"\\\\{server}\\{share}"
    user = f"{domain}\\{username}" if domain else username
    r = subprocess.run(
        ["net", "use", unc, password, f"/user:{user}", "/persistent:no"],
        capture_output=True, text=True, creationflags=_NW,
    )
    if r.returncode == 0:
        return True, "Monte avec succes"
    return False, r.stderr.strip() or r.stdout.strip() or "Echec du montage"


def _unmount_win(server: str, share: str) -> tuple[bool, str]:
    """Démonte un partage sous Windows."""
    r = subprocess.run(
        ["net", "use", f"\\\\{server}\\{share}", "/delete", "/yes"],
        capture_output=True, text=True, creationflags=_NW,
    )
    if r.returncode == 0:
        return True, "Demonte"
    return False, r.stderr.strip() or "Echec du demontage"
