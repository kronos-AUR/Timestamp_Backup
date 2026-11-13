"""Direct SMB file operations via python-smbc (libsmbclient).

Used when the backup destination is an smb:// URI.
Credentials are provided explicitly — no FUSE mount required.
"""
import hashlib
import os
import stat as _stat_module
from pathlib import Path

try:
    import smbc as _smbc
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


# ── Context ───────────────────────────────────────────────────────────────────

def make_context(server: str, username: str, password: str, domain: str = ""):
    """Return an authenticated smbc.Context for the given server."""
    _server = server.lower()

    def _auth(srv, shr, wkgrp, usr, pwd):
        if not _server or srv.lower() == _server:
            return (domain or wkgrp, username or usr, password or pwd)
        return (wkgrp, usr, pwd)

    return _smbc.Context(auth_fn=_auth)


# ── Low-level helpers ─────────────────────────────────────────────────────────

def stat(ctx, uri: str):
    """Return stat tuple or None if path does not exist."""
    try:
        return ctx.stat(uri)
    except Exception:
        return None


def mkdir_p(ctx, uri: str) -> None:
    """Recursively create SMB directories as needed."""
    # smb://server/share/a/b/c  →  parts = ['smb:', '', server, share, 'a', 'b', 'c']
    # We start creating from depth=5 (first sub-dir inside the share)
    parts = uri.rstrip("/").split("/")
    for depth in range(5, len(parts) + 1):
        partial = "/".join(parts[:depth])
        if stat(ctx, partial) is None:
            try:
                ctx.mkdir(partial, 0o755)
            except Exception:
                pass


def file_hash(ctx, uri: str, block: int = 65536) -> str:
    h = hashlib.md5()
    fh = ctx.open(uri, os.O_RDONLY, 0)
    try:
        while chunk := fh.read(block):
            h.update(chunk)
    finally:
        fh.close()
    return h.hexdigest()


def local_hash(path: Path, block: int = 65536) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(block):
            h.update(chunk)
    return h.hexdigest()


def needs_copy(local_src: Path, ctx, dst_uri: str) -> bool:
    st = stat(ctx, dst_uri)
    if st is None:
        return True
    if local_src.stat().st_size != st[6]:   # st_size at index 6
        return True
    return local_hash(local_src) != file_hash(ctx, dst_uri)


def copy_file(local_src: Path, ctx, dst_uri: str) -> None:
    """Upload local_src to dst_uri, creating parent dirs as needed."""
    parent_uri = "/".join(dst_uri.split("/")[:-1])
    mkdir_p(ctx, parent_uri)

    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    with open(local_src, "rb") as fsrc:
        fh = ctx.open(dst_uri, flags, 0o644)
        try:
            while chunk := fsrc.read(65536):
                fh.write(chunk)
        finally:
            fh.close()

    expected = local_src.stat().st_size
    st = stat(ctx, dst_uri)
    if st is None or st[6] != expected:
        raise OSError(
            f"Vérification échouée après copie vers {dst_uri} "
            "(taille incorrecte — partage toujours accessible ?)"
        )


def is_dir(ctx, uri: str) -> bool:
    """True si l'URI désigne un dossier SMB."""
    st = stat(ctx, uri)
    if st is not None:
        try:
            return _stat_module.S_ISDIR(st[0])
        except (TypeError, IndexError):
            pass
    # Certains serveurs renvoient un mode inexploitable : on retombe sur un
    # opendir, qui échoue sur un fichier.
    try:
        ctx.opendir(uri)
        return True
    except Exception:
        return False


def download_file(ctx, src_uri: str, local_dst: Path) -> None:
    """Télécharge src_uri vers local_dst (dossiers parents créés au besoin)."""
    local_dst.parent.mkdir(parents=True, exist_ok=True)
    fh = ctx.open(src_uri, os.O_RDONLY, 0)
    try:
        with open(local_dst, "wb") as fdst:
            while chunk := fh.read(65536):
                fdst.write(chunk)
            fdst.flush()
            os.fsync(fdst.fileno())
    finally:
        fh.close()

    st = stat(ctx, src_uri)
    if st is not None and local_dst.stat().st_size != st[6]:
        raise OSError(
            f"Vérification échouée après téléchargement de {src_uri} "
            "(taille incorrecte — partage toujours accessible ?)"
        )


def needs_download(ctx, src_uri: str, local_dst: Path) -> bool:
    """Inverse de needs_copy : le fichier distant diffère-t-il du fichier local ?"""
    if not local_dst.exists():
        return True
    st = stat(ctx, src_uri)
    if st is None:
        return True
    if local_dst.stat().st_size != st[6]:
        return True
    return local_hash(local_dst) != file_hash(ctx, src_uri)


def rglob_files(ctx, uri: str) -> list[str]:
    """Recursively yield all file URIs under an SMB directory."""
    result = []
    try:
        dh = ctx.opendir(uri)
        for entry in dh.getdents():
            if entry.name in (".", ".."):
                continue
            child = f"{uri.rstrip('/')}/{entry.name}"
            if entry.smbc_type == _smbc.DIR:
                result.extend(rglob_files(ctx, child))
            elif entry.smbc_type == _smbc.FILE:
                result.append(child)
    except Exception:
        pass
    return result


# ── Connection test ───────────────────────────────────────────────────────────

def test_connection(server: str, share: str, username: str,
                    password: str, domain: str = "") -> tuple[bool, str]:
    """Verify credentials by listing the share root."""
    if not AVAILABLE:
        return False, "python-smbc (libsmbclient) non disponible"
    uri = f"smb://{server}/{share}"
    ctx = make_context(server, username, password, domain)
    try:
        ctx.opendir(uri).getdents()
        return True, "Connexion réussie"
    except _smbc.ConnectionRefusedError:
        return False, f"Connexion refusée par {server}"
    except _smbc.PermissionError:
        return False, "Identifiants incorrects (accès refusé)"
    except _smbc.TimedOutError:
        return False, f"Délai dépassé — serveur inaccessible ({server})"
    except _smbc.NoEntryError:
        return False, f"Partage '{share}' introuvable sur {server}"
    except Exception as e:
        return False, str(e)
