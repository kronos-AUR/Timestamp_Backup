import hashlib
import os
import shutil
import zipfile
import tarfile
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _resolve_network_path(destination: str) -> str:
    """Converts an smb:// URI to a local filesystem path.

    KDE uses kio-fuse  → /run/user/{uid}/kio-fuse/smb/{server}/{share}/{sub}
    GNOME uses GVFS    → /run/user/{uid}/gvfs/smb-share:server=...,share=.../sub
    Windows uses UNC   → \\\\server\\share\\sub
    """
    if not destination.lower().startswith("smb://"):
        return destination

    parsed = urlparse(destination)
    server = parsed.hostname or ""
    path_parts = parsed.path.lstrip("/").split("/", 1)
    share   = path_parts[0] if path_parts else ""
    subpath = path_parts[1].rstrip("/") if len(path_parts) > 1 else ""

    if os.name == "nt":
        unc = f"\\\\{server}\\{share}"
        if subpath:
            unc += "\\" + subpath.replace("/", "\\")
        return unc

    uid = os.getuid()

    # KDE — kio-fuse FUSE mount
    kiofuse = Path(f"/run/user/{uid}/kio-fuse")
    if os.path.ismount(str(kiofuse)):
        p = str(kiofuse / "smb" / server / share)
        if subpath:
            p += f"/{subpath}"
        return p

    # GNOME — scan GVFS directory for the actual mount point
    # (the directory name includes user/domain params which vary by session)
    gvfs_dir = Path(f"/run/user/{uid}/gvfs")
    if gvfs_dir.exists():
        for d in gvfs_dir.iterdir():
            if not d.name.startswith("smb-share:"):
                continue
            params = {}
            for part in d.name[len("smb-share:"):].split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    params[k] = v
            if params.get("server") == server and params.get("share") == share:
                p = str(d)
                if subpath:
                    p += f"/{subpath}"
                return p

    # Fallback: kio-fuse path (daemon not yet started — will fail at _check_destination)
    p = str(kiofuse / "smb" / server / share)
    if subpath:
        p += f"/{subpath}"
    return p


def _file_hash(path: Path, block_size: int = 65536) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(block_size):
            h.update(chunk)
    return h.hexdigest()


def _needs_copy(src: Path, dst: Path) -> bool:
    if not dst.exists():
        return True
    if src.stat().st_size != dst.stat().st_size:
        return True
    return _file_hash(src) != _file_hash(dst)


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
        shutil.copyfileobj(fsrc, fdst)
        fdst.flush()
        os.fsync(fdst.fileno())
    shutil.copystat(src, dst)
    # Sur un partage réseau, l'écriture peut sembler réussir (aucune exception)
    # alors que les données n'ont jamais réellement atteint le serveur — par
    # exemple si le partage a été démonté entre-temps, ou en cas de mise en
    # cache locale par l'OS. On vérifie donc, après coup, que le fichier est
    # bien présent à destination avec la taille attendue avant de déclarer la
    # copie réussie : si ce n'est pas le cas on lève une erreur explicite
    # plutôt que de la compter silencieusement comme un succès.
    if not dst.exists() or dst.stat().st_size != src.stat().st_size:
        raise OSError(
            f"Échec de vérification après copie vers {dst} "
            "(le partage réseau est-il toujours monté ?)"
        )


def _check_destination(dest: Path) -> str | None:
    """Vérifie que le dossier racine de destination existe déjà.

    On ne le crée jamais "à partir de rien" : si la destination est un
    partage réseau qui n'est pas (ou plus) monté, son dossier n'existe pas
    sur le système, et `mkdir(parents=True)` le fabriquerait silencieusement
    en local (ex: sur le disque système) sans qu'aucune erreur ne soit
    levée — donnant l'impression que tout a été sauvegardé alors que rien
    n'a atteint le partage réel. On échoue donc explicitement dans ce cas.
    """
    try:
        reachable = dest.exists()
    except OSError:
        # Ex. WinError 1326 sur un partage UNC qui exige une authentification
        # ("net use" jamais établi) : à traiter comme "non accessible".
        reachable = False
    if reachable:
        return None
    return (
        f"Destination introuvable : {dest}. "
        "Vérifiez que le dossier existe et, s'il s'agit d'un partage réseau, "
        "qu'il est bien monté."
    )


def _get_smb_credentials(server: str) -> tuple[str, str, str]:
    """Return (username, password, domain) for the given server from stored shares."""
    try:
        from backup.netshares import _load, _decrypt
        for entry in _load()["shares"].values():
            if entry.get("server", "").lower() == server.lower():
                return (
                    entry.get("username", ""),
                    _decrypt(entry.get("password_enc", "")),
                    entry.get("domain", ""),
                )
    except Exception:
        pass
    return "", "", ""


def _run_smb_backup(
    sources: list[str],
    destination: str,
    compress: bool,
    incremental: bool,
    on_progress,
) -> dict:
    """Backup to an smb:// URI using python-smbc (no FUSE mount required)."""
    from backup import smbfs
    if not smbfs.AVAILABLE:
        return {
            "copied": 0, "skipped": 0, "errors": [
                "python-smbc non disponible. Installez : apt install python3-smbc"
            ], "archive": None,
        }

    parsed = urlparse(destination)
    server     = parsed.hostname or ""
    path_parts = parsed.path.lstrip("/").split("/", 1)
    share      = path_parts[0] if path_parts else ""
    subpath    = path_parts[1].rstrip("/") if len(path_parts) > 1 else ""

    username, password, domain = _get_smb_credentials(server)
    ctx = smbfs.make_context(server, username, password, domain)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {"copied": 0, "skipped": 0, "errors": [], "archive": None, "timestamp": timestamp}

    # Verify destination is reachable
    dest_uri = f"smb://{server}/{share}" + (f"/{subpath}" if subpath else "")
    if smbfs.stat(ctx, dest_uri) is None:
        report["errors"].append(
            f"Destination SMB introuvable : {dest_uri}. "
            "Vérifiez les identifiants dans la page Réseau."
        )
        return report

    # Collect source files
    all_files: list[tuple[Path, str]] = []
    for source in sources:
        src_root = Path(source)
        if not src_root.exists():
            report["errors"].append(f"Source introuvable : {source}")
            continue
        if src_root.is_file():
            all_files.append((src_root, f"{dest_uri}/{src_root.name}"))
        else:
            for file in src_root.rglob("*"):
                if file.is_file():
                    rel = str(file.relative_to(src_root.parent)).replace("\\", "/")
                    all_files.append((file, f"{dest_uri}/{rel}"))

    total = len(all_files)

    if compress:
        import tarfile, tempfile
        archive_name = f"backup_{timestamp}.tar.gz"
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            with tarfile.open(tmp_path, "w:gz") as tf:
                for i, (src, _) in enumerate(all_files):
                    if on_progress:
                        on_progress(i + 1, total, src)
                    try:
                        tf.add(src, arcname=src.name)
                        report["copied"] += 1
                    except Exception as e:
                        report["errors"].append(f"{src}: {e}")
            archives_uri = f"{dest_uri}/archives"
            archive_uri  = f"{archives_uri}/{archive_name}"
            smbfs.copy_file(Path(tmp_path), ctx, archive_uri)
            report["archive"] = archive_uri
        except Exception as e:
            report["errors"].append(f"Upload archive : {e}")
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    else:
        for i, (src, dst_uri) in enumerate(all_files):
            if on_progress:
                on_progress(i + 1, total, src)
            try:
                if incremental and not smbfs.needs_copy(src, ctx, dst_uri):
                    report["skipped"] += 1
                    logger.debug("Ignoré (identique) : %s", src)
                    continue
                smbfs.copy_file(src, ctx, dst_uri)
                report["copied"] += 1
                logger.info("Copié SMB : %s → %s", src, dst_uri)
            except Exception as e:
                report["errors"].append(f"{src}: {e}")
                logger.error("Erreur copie SMB %s : %s", src, e)

    return report


def run_backup(
    sources: list[str],
    destination: str,
    compress: bool = False,
    incremental: bool = True,
    on_progress=None,
) -> dict:
    """
    Copie les sources vers destination (local ou smb://).
    Retourne un rapport {copied, skipped, errors, archive}.
    on_progress(current, total, path) appelé pour chaque fichier traité.
    """
    # Sous Linux, les destinations smb:// sont gérées directement via smbc
    # (pas besoin de montage FUSE). Sous Windows, net use donne un accès
    # natif via un chemin UNC classique — inutile et non disponible (smbc
    # est un module Linux uniquement, cf. python3-smbc).
    if destination.lower().startswith("smb://") and os.name != "nt":
        return _run_smb_backup(sources, destination, compress, incremental, on_progress)

    destination = _resolve_network_path(destination)
    dest = Path(destination)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {"copied": 0, "skipped": 0, "errors": [], "archive": None, "timestamp": timestamp}

    dest_error = _check_destination(dest)
    if dest_error:
        report["errors"].append(dest_error)
        logger.error(dest_error)
        return report

    # Collecte tous les fichiers à traiter
    all_files: list[tuple[Path, Path]] = []
    for source in sources:
        src_root = Path(source)
        if not src_root.exists():
            report["errors"].append(f"Source introuvable : {source}")
            logger.warning("Source introuvable : %s", source)
            continue
        if src_root.is_file():
            rel = src_root.name
            all_files.append((src_root, dest / rel))
        else:
            for file in src_root.rglob("*"):
                if file.is_file():
                    rel = file.relative_to(src_root.parent)
                    all_files.append((file, dest / rel))

    total = len(all_files)

    if compress:
        archive_dir = dest / "archives"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_name = f"backup_{timestamp}"

        # On ouvre nous-mêmes le fichier d'archive afin de pouvoir forcer un
        # fsync avant fermeture : cela force l'OS à réellement transmettre les
        # données au partage réseau et fait remonter immédiatement toute
        # erreur de transport, au lieu de la laisser masquée par une mise en
        # cache locale (voir _copy_file pour la même logique).
        if os.name == "nt":
            archive_path = archive_dir / f"{archive_name}.zip"
            with open(archive_path, "wb") as fh:
                with zipfile.ZipFile(fh, "w", zipfile.ZIP_DEFLATED) as zf:
                    for i, (src, _) in enumerate(all_files):
                        if on_progress:
                            on_progress(i + 1, total, src)
                        try:
                            zf.write(src, src.name)
                            report["copied"] += 1
                        except Exception as e:
                            report["errors"].append(f"{src}: {e}")
                            logger.error("Erreur compression %s : %s", src, e)
                fh.flush()
                os.fsync(fh.fileno())
        else:
            archive_path = archive_dir / f"{archive_name}.tar.gz"
            with open(archive_path, "wb") as fh:
                with tarfile.open(fileobj=fh, mode="w:gz") as tf:
                    for i, (src, _) in enumerate(all_files):
                        if on_progress:
                            on_progress(i + 1, total, src)
                        try:
                            tf.add(src, arcname=src.name)
                            report["copied"] += 1
                        except Exception as e:
                            report["errors"].append(f"{src}: {e}")
                            logger.error("Erreur compression %s : %s", src, e)
                fh.flush()
                os.fsync(fh.fileno())

        if not archive_path.exists() or archive_path.stat().st_size == 0:
            msg = f"Échec de vérification de l'archive après écriture : {archive_path}"
            report["errors"].append(msg)
            logger.error(msg)

        report["archive"] = str(archive_path)

    else:
        for i, (src, dst) in enumerate(all_files):
            if on_progress:
                on_progress(i + 1, total, src)
            try:
                if incremental and not _needs_copy(src, dst):
                    report["skipped"] += 1
                    logger.debug("Ignoré (identique) : %s", src)
                    continue
                _copy_file(src, dst)
                report["copied"] += 1
                logger.info("Copié : %s → %s", src, dst)
            except Exception as e:
                report["errors"].append(f"{src}: {e}")
                logger.error("Erreur copie %s : %s", src, e)

    return report




# ══════════════════════════════════════════════════════════════════════
#  Restauration
# ══════════════════════════════════════════════════════════════════════
#
# La restauration est le miroir de la sauvegarde : la source (dossier ou
# archive, locale ou distante en smb://) écrase le contenu du dossier de
# destination (lui aussi local ou distant).
#
# Les quatre combinaisons source/destination sont gérées par un couple
# source « lecteur » / destination « écrivain » :
#   - la source expose la liste des fichiers relatifs à restaurer ;
#   - la destination sait écrire un fichier local OU rapatrier directement
#     un fichier distant, ce qui évite un aller-retour par un temporaire
#     dans le cas courant SMB → local.

_ARCHIVE_SUFFIXES = (".zip", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar")


def _is_archive_name(name: str) -> bool:
    lower = name.lower()
    return any(lower.endswith(suffix) for suffix in _ARCHIVE_SUFFIXES)


def _split_smb_uri(uri: str) -> tuple[str, str, str]:
    """smb://server/share/sub/dir → (server, share, 'sub/dir')."""
    parsed = urlparse(uri)
    server = parsed.hostname or ""
    parts = parsed.path.lstrip("/").split("/", 1)
    share = parts[0] if parts else ""
    subpath = parts[1].strip("/") if len(parts) > 1 else ""
    return server, share, subpath


def _smb_context_for(uri: str):
    """Retourne (contexte authentifié, URI normalisée sans identifiants)."""
    from backup import smbfs
    server, share, subpath = _split_smb_uri(uri)
    username, password, domain = _get_smb_credentials(server)
    ctx = smbfs.make_context(server, username, password, domain)
    base = f"smb://{server}/{share}" + (f"/{subpath}" if subpath else "")
    return ctx, base


def _tar_extract(tf: tarfile.TarFile, member, dest: Path) -> None:
    """Extraction d'un membre tar avec le filtre « data ».

    Sans filtre, une archive piégée peut écrire hors du dossier cible via des
    chemins absolus, des « .. » ou des liens symboliques. Le filtre « data »
    (Python 3.12+, obligatoire à partir de 3.14) bloque ces cas ; on retombe
    sur l'extraction historique sur les interpréteurs plus anciens.
    """
    try:
        tf.extract(member, dest, filter="data")
    except TypeError:
        tf.extract(member, dest)


def _open_archive(path: Path):
    """Retourne (handle, [(nom_affiché, membre)]) pour un zip ou un tar."""
    if path.suffix.lower() == ".zip":
        zf = zipfile.ZipFile(path, "r")
        return zf, [(n, n) for n in zf.namelist()]
    tf = tarfile.open(path, "r:*")
    return tf, [(m.name, m) for m in tf.getmembers()]


class _LocalTarget:
    """Destination sur le système de fichiers local (ou partage monté)."""

    remote = False

    def __init__(self, destination: str):
        self.root = Path(_resolve_network_path(destination))

    def check(self) -> str | None:
        return _check_destination(self.root)

    def put_local(self, rel: str, src_path: Path, incremental: bool) -> bool:
        dst = self.root / rel
        if incremental and not _needs_copy(src_path, dst):
            return False
        _copy_file(src_path, dst)
        return True

    def put_remote(self, rel: str, ctx, src_uri: str, incremental: bool) -> bool:
        from backup import smbfs
        dst = self.root / rel
        if incremental and not smbfs.needs_download(ctx, src_uri, dst):
            return False
        smbfs.download_file(ctx, src_uri, dst)
        return True


class _SmbTarget:
    """Destination sur un partage SMB, écrite directement via libsmbclient."""

    remote = True

    def __init__(self, destination: str):
        self.ctx, self.base = _smb_context_for(destination)

    def check(self) -> str | None:
        from backup import smbfs
        if smbfs.stat(self.ctx, self.base) is None:
            return (f"Destination SMB introuvable : {self.base}. "
                    "Vérifiez les identifiants dans la page Réseau.")
        return None

    def put_local(self, rel: str, src_path: Path, incremental: bool) -> bool:
        from backup import smbfs
        dst_uri = f"{self.base}/{rel}"
        if incremental and not smbfs.needs_copy(src_path, self.ctx, dst_uri):
            return False
        smbfs.copy_file(src_path, self.ctx, dst_uri)
        return True

    def put_remote(self, rel: str, ctx, src_uri: str, incremental: bool) -> bool:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / Path(rel).name
            from backup import smbfs
            smbfs.download_file(ctx, src_uri, local)
            return self.put_local(rel, local, incremental)


def _use_smbc(uri: str) -> bool:
    """smb:// géré directement par libsmbclient (Linux uniquement).

    Sous Windows, un chemin UNC donne un accès natif : inutile de passer par
    smbc, qui n'y est de toute façon pas disponible.
    """
    if not uri.lower().startswith("smb://") or os.name == "nt":
        return False
    from backup import smbfs
    return smbfs.AVAILABLE


def _restore_archive(archive: Path, target, report: dict, on_progress) -> None:
    """Extrait une archive locale vers la destination (locale ou SMB)."""
    if not target.remote:
        handle, members = _open_archive(archive)
        try:
            total = len(members)
            for i, (name, member) in enumerate(members):
                if on_progress:
                    on_progress(i + 1, total, name)
                try:
                    if isinstance(handle, zipfile.ZipFile):
                        # ZipFile.extract neutralise déjà « .. » et les chemins absolus
                        handle.extract(member, target.root)
                    else:
                        _tar_extract(handle, member, target.root)
                    report["restored"] += 1
                except Exception as e:
                    report["errors"].append(f"{name}: {e}")
                    logger.error("Erreur extraction %s : %s", name, e)
        finally:
            handle.close()
        return

    # Destination distante : on extrait dans un dossier temporaire local puis
    # on téléverse fichier par fichier (libsmbclient n'écrit pas en flux).
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        handle, members = _open_archive(archive)
        try:
            for name, member in members:
                try:
                    if isinstance(handle, zipfile.ZipFile):
                        handle.extract(member, staging)
                    else:
                        _tar_extract(handle, member, staging)
                except Exception as e:
                    report["errors"].append(f"{name}: {e}")
        finally:
            handle.close()

        files = [f for f in staging.rglob("*") if f.is_file()]
        total = len(files)
        for i, file in enumerate(files):
            rel = file.relative_to(staging).as_posix()
            if on_progress:
                on_progress(i + 1, total, rel)
            try:
                target.put_local(rel, file, False)
                report["restored"] += 1
            except Exception as e:
                report["errors"].append(f"{rel}: {e}")
                logger.error("Erreur envoi %s : %s", rel, e)


def restore_backup(source: str, destination: str, incremental: bool = False,
                   on_progress=None) -> dict:
    """Restaure une source (dossier ou archive, locale ou smb://) vers destination.

    Les fichiers de la source écrasent ceux de la destination. Avec
    incremental=True, les fichiers déjà identiques (taille + empreinte) sont
    ignorés — utile pour reprendre une restauration interrompue.

    Retourne un rapport {restored, skipped, errors}.
    on_progress(current, total, path) est appelé pour chaque fichier traité.
    """
    report = {"restored": 0, "skipped": 0, "errors": []}

    src_remote = _use_smbc(source)
    dst_remote = _use_smbc(destination)

    try:
        target = _SmbTarget(destination) if dst_remote else _LocalTarget(destination)
    except Exception as e:
        report["errors"].append(f"Destination inutilisable : {e}")
        return report

    if source.lower().startswith("smb://") and not src_remote and os.name != "nt":
        # Pas de libsmbclient : on retombe sur un éventuel montage FUSE
        logger.info("python-smbc indisponible — tentative via un montage local")

    # ── Source distante (libsmbclient) ────────────────────────────────
    if src_remote:
        from backup import smbfs
        try:
            ctx, base = _smb_context_for(source)
        except Exception as e:
            report["errors"].append(f"Source SMB inutilisable : {e}")
            return report

        if smbfs.stat(ctx, base) is None:
            report["errors"].append(
                f"Source SMB introuvable : {base}. "
                "Vérifiez les identifiants dans la page Réseau."
            )
            return report

        dest_error = target.check()
        if dest_error:
            report["errors"].append(dest_error)
            return report

        if not smbfs.is_dir(ctx, base):
            if not _is_archive_name(base):
                report["errors"].append(f"Format non supporté : {source}")
                return report
            # Archive distante : rapatriée en local avant extraction
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                local_archive = Path(tmp) / Path(base).name
                try:
                    smbfs.download_file(ctx, base, local_archive)
                except Exception as e:
                    report["errors"].append(f"Téléchargement de l'archive : {e}")
                    return report
                _restore_archive(local_archive, target, report, on_progress)
            return report

        uris = smbfs.rglob_files(ctx, base)
        if not uris:
            report["errors"].append(f"Aucun fichier trouvé dans {base}")
            return report
        total = len(uris)
        prefix = base.rstrip("/") + "/"
        for i, uri in enumerate(uris):
            rel = uri[len(prefix):] if uri.startswith(prefix) else Path(uri).name
            if on_progress:
                on_progress(i + 1, total, rel)
            try:
                if target.put_remote(rel, ctx, uri, incremental):
                    report["restored"] += 1
                else:
                    report["skipped"] += 1
                    logger.debug("Ignoré (identique) : %s", rel)
            except Exception as e:
                report["errors"].append(f"{rel}: {e}")
                logger.error("Erreur restauration %s : %s", rel, e)
        return report

    # ── Source locale (ou partage monté) ──────────────────────────────
    src = Path(_resolve_network_path(source))
    try:
        exists = src.exists()
    except OSError:
        exists = False
    if not exists:
        report["errors"].append(f"Source introuvable : {source}")
        return report

    dest_error = target.check()
    if dest_error:
        report["errors"].append(dest_error)
        return report

    if src.is_file():
        if not _is_archive_name(src.name):
            # Fichier isolé : on le restaure tel quel à la racine
            try:
                if target.put_local(src.name, src, incremental):
                    report["restored"] += 1
                else:
                    report["skipped"] += 1
            except Exception as e:
                report["errors"].append(f"{src}: {e}")
            return report
        _restore_archive(src, target, report, on_progress)
        return report

    if not src.is_dir():
        report["errors"].append(f"Format non supporté : {source}")
        return report

    files = [f for f in src.rglob("*") if f.is_file()]
    total = len(files)
    for i, file in enumerate(files):
        rel = file.relative_to(src).as_posix()
        if on_progress:
            on_progress(i + 1, total, rel)
        try:
            if target.put_local(rel, file, incremental):
                report["restored"] += 1
            else:
                report["skipped"] += 1
                logger.debug("Ignoré (identique) : %s", rel)
        except Exception as e:
            report["errors"].append(f"{rel}: {e}")
            logger.error("Erreur restauration %s : %s", rel, e)

    return report
