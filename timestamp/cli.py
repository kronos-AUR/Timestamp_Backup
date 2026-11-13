#!/usr/bin/env python3
"""
Timestamp - Interface en ligne de commande.

Outil de sauvegarde et restauration via CLI.
"""

import sys
from pathlib import Path

# Importer le module d'initialisation pour définir les chemins
from timestamp import CONFIG_DIR, ensure_directories

# S'assurer que les répertoires existent
ensure_directories()

# Définir le répertoire de projet pour le module backup
import backup.config
backup.config._project_root = CONFIG_DIR

import argparse
import logging

from backup.config import (
    add_profile, get_profile, list_profiles, remove_profile,
    add_group, get_group, list_groups, remove_group,
    add_restore, get_restore, list_restores, remove_restore,
)
from backup.core import restore_backup, run_backup

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s: %(message)s",
)


def _progress(current: int, total: int, path) -> None:
    pct = int(current / total * 100) if total else 100
    bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
    print(f"\r  [{bar}] {pct:3d}%  {str(path)[-50:]}", end="", flush=True)
    if current == total:
        print()


def cmd_backup(args):
    if args.group:
        cmd_backup_group(args)
        return

    profile = get_profile(args.profile)
    if not profile:
        print(f"Profil introuvable : '{args.profile}'")
        sys.exit(1)

    print(f"Sauvegarde du profil '{args.profile}'...")
    report = run_backup(
        sources=profile["sources"],
        destination=profile["destination"],
        compress=profile.get("compress", False),
        incremental=not args.full,
        on_progress=_progress,
    )

    print(f"\n  Copies  : {report['copied']}")
    print(f"  Ignores : {report['skipped']}")
    if report["archive"]:
        print(f"  Archive : {report['archive']}")
    if report["errors"]:
        print(f"  Erreurs ({len(report['errors'])}) :")
        for err in report["errors"]:
            print(f"    - {err}")
        sys.exit(1)


def cmd_backup_group(args):
    group = get_group(args.profile)
    if not group:
        print(f"Groupe introuvable : '{args.profile}'")
        sys.exit(1)

    profiles = group.get("profiles", [])
    print(f"Sauvegarde du groupe '{args.profile}' ({len(profiles)} profil(s))...")

    total_copied, total_skipped, total_errors = 0, 0, []
    for i, pname in enumerate(profiles, 1):
        profile = get_profile(pname)
        if not profile:
            total_errors.append(f"[{pname}] Profil introuvable")
            continue
        print(f"\n[{i}/{len(profiles)}] Profil '{pname}'")
        report = run_backup(
            sources=profile["sources"],
            destination=profile["destination"],
            compress=profile.get("compress", False),
            incremental=not args.full,
            on_progress=_progress,
        )
        total_copied += report["copied"]
        total_skipped += report["skipped"]
        total_errors.extend(f"[{pname}] {e}" for e in report["errors"])

    print(f"\n  Copies  : {total_copied}")
    print(f"  Ignores : {total_skipped}")
    if total_errors:
        print(f"  Erreurs ({len(total_errors)}) :")
        for err in total_errors:
            print(f"    - {err}")
        sys.exit(1)


def cmd_restore(args):
    """Restauration ponctuelle (source/destination) ou via un profil enregistré."""
    if args.profile:
        profile = get_restore(args.profile)
        if not profile:
            print(f"Profil de restauration introuvable : '{args.profile}'")
            sys.exit(1)
        source      = profile["source"]
        destination = profile["destination"]
        incremental = profile.get("incremental", False)
        print(f"Restauration du profil '{args.profile}'...")
    else:
        if not args.source or not args.destination:
            print("Indiquez une source et une destination, ou --profile <nom>.")
            sys.exit(1)
        source, destination = args.source, args.destination
        incremental = args.incremental

    print(f"  {source}\n  -> {destination}")
    report = restore_backup(
        source=source,
        destination=destination,
        incremental=incremental,
        on_progress=_progress,
    )
    print(f"\n  Restaurés : {report['restored']}")
    print(f"  Ignorés   : {report['skipped']}")
    if report["errors"]:
        print(f"  Erreurs ({len(report['errors'])}) :")
        for err in report["errors"]:
            print(f"    - {err}")
        sys.exit(1)


def cmd_restore_add(args):
    profile = add_restore(
        name=args.name,
        source=args.source,
        destination=args.destination,
        incremental=args.incremental,
    )
    print(f"Profil de restauration '{args.name}' cree :")
    print(f"  Source      : {profile['source']}")
    print(f"  Destination : {profile['destination']}")
    print(f"  Incremental : {'oui' if profile['incremental'] else 'non'}")


def cmd_restore_remove(args):
    if remove_restore(args.name):
        print(f"Profil de restauration '{args.name}' supprime.")
    else:
        print(f"Profil de restauration introuvable : '{args.name}'")
        sys.exit(1)


def cmd_restore_list(args):
    restores = list_restores()
    if not restores:
        print("Aucun profil de restauration configure.")
        return
    for name, r in restores.items():
        print(f"  {name}")
        print(f"    Source      : {r['source']}")
        print(f"    Destination : {r['destination']}")
        print(f"    Incremental : {'oui' if r.get('incremental') else 'non'}")


def cmd_profile_add(args):
    sources = args.sources
    profile = add_profile(
        name=args.name,
        sources=sources,
        destination=args.destination,
        compress=args.compress,
    )
    print(f"Profil '{args.name}' cree :")
    print(f"  Sources     : {', '.join(profile['sources'])}")
    print(f"  Destination : {profile['destination']}")
    print(f"  Compression : {'oui' if profile['compress'] else 'non'}")


def cmd_profile_remove(args):
    if remove_profile(args.name):
        print(f"Profil '{args.name}' supprime.")
    else:
        print(f"Profil introuvable : '{args.name}'")
        sys.exit(1)


def cmd_profile_list(args):
    profiles = list_profiles()
    if not profiles:
        print("Aucun profil configure.")
        return
    for name, p in profiles.items():
        compress = "oui" if p.get("compress") else "non"
        print(f"  {name}")
        print(f"    Sources     : {', '.join(p['sources'])}")
        print(f"    Destination : {p['destination']}")
        print(f"    Compression : {compress}")


def cmd_group_add(args):
    group = add_group(name=args.name, profiles=args.profiles)
    print(f"Groupe '{args.name}' cree :")
    print(f"  Profils : {', '.join(group['profiles'])}")


def cmd_group_remove(args):
    if remove_group(args.name):
        print(f"Groupe '{args.name}' supprime.")
    else:
        print(f"Groupe introuvable : '{args.name}'")
        sys.exit(1)


def cmd_group_list(args):
    groups = list_groups()
    if not groups:
        print("Aucun groupe configure.")
        return
    for name, g in groups.items():
        print(f"  {name}")
        print(f"    Profils : {', '.join(g['profiles'])}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="timestamp-cli",
        description="Outil de sauvegarde simple - Windows & Linux",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # backup run
    p_run = sub.add_parser("run", help="Lancer une sauvegarde")
    p_run.add_argument("profile", help="Nom du profil (ou du groupe avec --group) a utiliser")
    p_run.add_argument("--full", action="store_true", help="Sauvegarde complete (ignore l'incremental)")
    p_run.add_argument("--group", action="store_true",
                        help="Traite l'argument comme un nom de groupe pluto^t qu'un profil")
    p_run.set_defaults(func=cmd_backup)

    # backup restore
    p_restore = sub.add_parser("restore", help="Restaurer une sauvegarde")
    p_restore.add_argument("source", nargs="?",
                           help="Archive ou dossier source (local ou smb://)")
    p_restore.add_argument("destination", nargs="?", help="Dossier de destination")
    p_restore.add_argument("--profile", help="Utiliser un profil de restauration enregistre")
    p_restore.add_argument("--incremental", action="store_true",
                           help="Ignorer les fichiers deja identiques a destination")
    p_restore.set_defaults(func=cmd_restore)

    # backup restore-profile
    p_rst = sub.add_parser("restore-profile", help="Gerer les profils de restauration")
    sub_rst = p_rst.add_subparsers(dest="subcommand", required=True)

    p_radd = sub_rst.add_parser("add", help="Ajouter un profil de restauration")
    p_radd.add_argument("name", help="Nom du profil")
    p_radd.add_argument("source", help="Archive ou dossier source (local ou smb://)")
    p_radd.add_argument("destination", help="Dossier de destination")
    p_radd.add_argument("--incremental", action="store_true",
                        help="Ignorer les fichiers deja identiques a destination")
    p_radd.set_defaults(func=cmd_restore_add)

    p_rrm = sub_rst.add_parser("remove", help="Supprimer un profil de restauration")
    p_rrm.add_argument("name", help="Nom du profil")
    p_rrm.set_defaults(func=cmd_restore_remove)

    p_rls = sub_rst.add_parser("list", help="Lister les profils de restauration")
    p_rls.set_defaults(func=cmd_restore_list)

    # backup profile
    p_profile = sub.add_parser("profile", help="Gerer les profils")
    sub_profile = p_profile.add_subparsers(dest="subcommand", required=True)

    p_add = sub_profile.add_parser("add", help="Ajouter un profil")
    p_add.add_argument("name", help="Nom du profil")
    p_add.add_argument("destination", help="Dossier de destination")
    p_add.add_argument("sources", nargs="+", help="Dossiers/fichiers sources")
    p_add.add_argument("--compress", action="store_true", help="Activer la compression")
    p_add.set_defaults(func=cmd_profile_add)

    p_rm = sub_profile.add_parser("remove", help="Supprimer un profil")
    p_rm.add_argument("name", help="Nom du profil")
    p_rm.set_defaults(func=cmd_profile_remove)

    p_ls = sub_profile.add_parser("list", help="Lister les profils")
    p_ls.set_defaults(func=cmd_profile_list)

    # backup group
    p_group = sub.add_parser("group", help="Gerer les groupes de sauvegarde")
    sub_group = p_group.add_subparsers(dest="subcommand", required=True)

    p_gadd = sub_group.add_parser("add", help="Ajouter un groupe")
    p_gadd.add_argument("name", help="Nom du groupe")
    p_gadd.add_argument("profiles", nargs="+", help="Noms des profils inclus, dans l'ordre d'execution")
    p_gadd.set_defaults(func=cmd_group_add)

    p_grm = sub_group.add_parser("remove", help="Supprimer un groupe")
    p_grm.add_argument("name", help="Nom du groupe")
    p_grm.set_defaults(func=cmd_group_remove)

    p_gls = sub_group.add_parser("list", help="Lister les groupes")
    p_gls.set_defaults(func=cmd_group_list)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
