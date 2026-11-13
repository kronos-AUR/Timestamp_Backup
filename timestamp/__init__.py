"""
Timestamp - Module d'initialisation pour l'installation AUR.

Ce module définit les chemins de base pour une installation système.
Il doit être importé avant tout autre module timestamp.
"""

import os
import sys
from pathlib import Path

# Chemins pour l'installation AUR
PKG_DIR = Path("/usr/lib/timestamp")

# Dossier de configuration utilisateur (XDG compliant)
CONFIG_DIR = Path.home() / ".config" / "timestamp"

# Dossier de données utilisateur (XDG compliant)
DATA_DIR = Path.home() / ".local" / "share" / "timestamp"

# Dossier de cache utilisateur (XDG compliant)
CACHE_DIR = Path.home() / ".cache" / "timestamp"

# Dossier de logs
LOGS_DIR = DATA_DIR / "logs"

# Dossier runtime
RUNTIME_DIR = DATA_DIR / "runtime"

# Dossier des icônes
ICONS_DIR = Path("/usr/share/icons/hicolor/scalable/apps")


def ensure_directories():
    """Créer les répertoires nécessaires si ils n'existent pas."""
    for directory in [CONFIG_DIR, DATA_DIR, LOGS_DIR, RUNTIME_DIR, CACHE_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


# Ajouter le dossier du paquet à sys.path si nécessaire
if str(PKG_DIR) not in sys.path:
    sys.path.insert(0, str(PKG_DIR))

# Initialiser les répertoires
ensure_directories()

# Définir les variables pour les autres modules
# Ces variables seront utilisées par backup.config, netshares, etc.
_project_root = CONFIG_DIR
_runtime_root = RUNTIME_DIR

# Exporter pour compatibilité
__all__ = [
    'PKG_DIR', 'CONFIG_DIR', 'DATA_DIR', 'CACHE_DIR', 
    'LOGS_DIR', 'RUNTIME_DIR', 'ICONS_DIR',
    '_project_root', '_runtime_root',
    'ensure_directories'
]
