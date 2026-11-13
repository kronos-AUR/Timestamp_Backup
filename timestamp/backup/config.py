"""
Gestion de la configuration pour Timestamp.

Ce module gère la lecture et l'écriture de la configuration
en utilisant les chemins XDG pour une installation système.
"""

import json
import os
from pathlib import Path

# Importer les chemins depuis le module parent
from timestamp import CONFIG_DIR, ensure_directories

# S'assurer que les répertoires existent
ensure_directories()

# Chemins de configuration
def get_config_path() -> Path:
    """Retourne le chemin du fichier de configuration."""
    return CONFIG_DIR / "config.json"


def _default_config() -> dict:
    """Retourne une configuration par défaut."""
    return {
        "profiles":  {},
        "schedules": {},
        "groups":    {},
        "restores":  {},
        "settings":  {"theme": "flexoki"},
    }


DEFAULT_CONFIG = _default_config()

# Variable pour compatibilité ascendante avec l'ancien système
_project_root: Path | None = None


def load_config() -> dict:
    """Charge la configuration depuis le fichier."""
    path = get_config_path()
    if not path.exists():
        cfg = _default_config()
        save_config(cfg)
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _default_config()
    if not isinstance(config, dict):
        return _default_config()
    for key, value in _default_config().items():
        config.setdefault(key, value)
    return config


def save_config(config: dict) -> None:
    """Sauvegarde la configuration dans le fichier (écriture atomique)."""
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


# ── Profiles ──────────────────────────────────────────────────────────

def add_profile(name: str, sources: list[str], destination: str, compress: bool = False) -> dict:
    config = load_config()
    config["profiles"][name] = {
        "sources": sources,
        "destination": destination,
        "compress": compress,
    }
    save_config(config)
    return config["profiles"][name]


def update_profile(old_name: str, name: str, sources: list[str], destination: str, compress: bool = False) -> dict:
    config = load_config()
    if old_name in config["profiles"]:
        del config["profiles"][old_name]
    config["profiles"][name] = {
        "sources": sources,
        "destination": destination,
        "compress": compress,
    }
    if old_name != name:
        for sched in config.get("schedules", {}).values():
            if sched.get("profile") == old_name:
                sched["profile"] = name
    save_config(config)
    return config["profiles"][name]


def remove_profile(name: str) -> bool:
    config = load_config()
    if name not in config["profiles"]:
        return False
    del config["profiles"][name]
    for group in config.get("groups", {}).values():
        if name in group.get("profiles", []):
            group["profiles"] = [p for p in group["profiles"] if p != name]
    save_config(config)
    return True


def get_profile(name: str) -> dict | None:
    config = load_config()
    return config["profiles"].get(name)


def list_profiles() -> dict:
    return load_config()["profiles"]


# ── Groups ────────────────────────────────────────────────────────────

def add_group(name: str, profiles: list[str]) -> dict:
    config = load_config()
    config.setdefault("groups", {})[name] = {"profiles": list(profiles)}
    save_config(config)
    return config["groups"][name]


def update_group(old_name: str, name: str, profiles: list[str]) -> dict:
    config = load_config()
    groups = config.setdefault("groups", {})
    if old_name in groups:
        del groups[old_name]
    groups[name] = {"profiles": list(profiles)}
    if old_name != name:
        for sched in config.get("schedules", {}).values():
            if sched.get("type") == "group" and sched.get("target") == old_name:
                sched["target"] = name
    save_config(config)
    return groups[name]


def remove_group(name: str) -> bool:
    config = load_config()
    groups = config.get("groups", {})
    if name not in groups:
        return False
    del groups[name]
    save_config(config)
    return True


def get_group(name: str) -> dict | None:
    config = load_config()
    return config.get("groups", {}).get(name)


def list_groups() -> dict:
    return load_config().get("groups", {})


# ── Schedules ─────────────────────────────────────────────────────────

def add_schedule(name: str, target: str, frequency: str, sched_type: str = "profile",
                  time: str = "02:00", day: str = None) -> dict:
    config = load_config()
    config.setdefault("schedules", {})[name] = {
        "type": sched_type,
        "target": target,
        "frequency": frequency,
        "time": time,
        "day": day,
    }
    save_config(config)
    return config["schedules"][name]


def remove_schedule(name: str) -> bool:
    config = load_config()
    schedules = config.get("schedules", {})
    if name not in schedules:
        return False
    del schedules[name]
    save_config(config)
    return True


def list_schedules() -> dict:
    schedules = load_config().get("schedules", {})
    for sched in schedules.values():
        if "type" not in sched:
            sched["type"] = "profile"
        if "target" not in sched and "profile" in sched:
            sched["target"] = sched["profile"]
    return schedules


# ── Restore profiles ──────────────────────────────────────────────────

def add_restore(name: str, source: str, destination: str,
                incremental: bool = False) -> dict:
    config = load_config()
    config.setdefault("restores", {})[name] = {
        "source": source,
        "destination": destination,
        "incremental": bool(incremental),
    }
    save_config(config)
    return config["restores"][name]


def update_restore(old_name: str, name: str, source: str, destination: str,
                   incremental: bool = False) -> dict:
    config = load_config()
    restores = config.setdefault("restores", {})
    if old_name in restores:
        del restores[old_name]
    restores[name] = {
        "source": source,
        "destination": destination,
        "incremental": bool(incremental),
    }
    if old_name != name:
        for sched in config.get("schedules", {}).values():
            if sched.get("type") == "restore" and sched.get("target") == old_name:
                sched["target"] = name
    save_config(config)
    return restores[name]


def remove_restore(name: str) -> bool:
    config = load_config()
    restores = config.get("restores", {})
    if name not in restores:
        return False
    del restores[name]
    save_config(config)
    return True


def get_restore(name: str) -> dict | None:
    return load_config().get("restores", {}).get(name)


def list_restores() -> dict:
    return load_config().get("restores", {})


# ── Settings (theme, ...) ───────────────────────────────────────────

THEMES = ("dark", "monokai", "amber", "flexoki")

def get_settings() -> dict:
    settings = load_config().get("settings", {})
    if settings.get("theme") not in THEMES:
        settings["theme"] = "flexoki"
    return settings


def get_theme() -> str:
    return get_settings()["theme"]


def set_theme(theme: str) -> str:
    if theme not in THEMES:
        raise ValueError(f"Theme inconnu : {theme}")
    config = load_config()
    config.setdefault("settings", {})["theme"] = theme
    save_config(config)
    return theme
