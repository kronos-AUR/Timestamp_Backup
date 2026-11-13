# Timestamp

[![AUR version](https://img.shields.io/aur/version/timestamp?style=flat-square)](https://aur.archlinux.org/packages/timestamp)
[![License](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](LICENSE)

**Timestamp** est un outil de sauvegarde et de restauration portable avec interface graphique, compatible Windows & Linux.

## Fonctionnalités

- ✅ **Sauvegarde simple** : Copie de fichiers/dossiers vers une destination locale ou réseau
- ✅ **Compression** : Création d'archives ZIP ou TAR.GZ
- ✅ **Sauvegarde incrémentale** : Seuls les fichiers modifiés sont copiés
- ✅ **Groupes de sauvegarde** : Exécution de plusieurs sauvegardes en séquence
- ✅ **Restauration** : Restauration depuis une sauvegarde existante
- ✅ **Planification** : Planification automatique via cron (Linux) ou Planificateur de tâches (Windows)
- ✅ **Partages réseau** : Support des partages SMB/CIFS
- ✅ **Multi-thèmes** : 4 thèmes disponibles (Sombre, Monokai, Jaune/Gris, Flexoki)
- ✅ **Interface graphique** : Interface web moderne avec PyQt6
- ✅ **CLI** : Interface en ligne de commande complète

## Installation

### Depuis l'AUR (Arch Linux)

```bash
# Avec yay
yay -S timestamp

# Avec paru
paru -S timestamp

# Avec makepkg
git clone https://aur.archlinux.org/timestamp.git
cd timestamp
makepkg -si
```

### Dépendances

**Obligatoires** :
- python
- python-pywebview
- python-qtpy
- python-pillow
- python-cryptography
- python-pyqt6
- python-pyqt6-webengine
- cronie

**Optionnelles** :
- python-smbc : Support SMB direct (accès aux partages réseau sans montage)
- gvfs-smb : Support montage SMB pour GNOME
- xdg-user-dirs : Gestion des dossiers utilisateur
- kio-fuse : Support montage SMB pour KDE

## Utilisation

### Interface Graphique

```bash
timestamp-gui
```

### Interface en Ligne de Commande

#### Gestion des profils

```bash
# Lister les profils
timestamp-cli profile list

# Ajouter un profil
timestamp-cli profile add <nom> <destination> <source1> [source2...] [--compress]

# Supprimer un profil
timestamp-cli profile remove <nom>
```

#### Sauvegarde

```bash
# Lancer une sauvegarde
timestamp-cli run <profil> [--full] [--group]

# Sauvegarde complète (ignore l'incrémental)
timestamp-cli run <profil> --full
```

#### Restauration

```bash
# Restauration manuelle
timestamp-cli restore <source> <destination> [--incremental]

# Restauration via un profil
timestamp-cli restore --profile <nom>
```

#### Planification

Les planifications sont gérées via l'interface graphique ou automatiquement lors de la création de profils.

## Configuration

Les fichiers de configuration sont stockés dans :
- `~/.config/timestamp/config.json` - Configuration principale
- `~/.local/share/timestamp/logs/` - Journaux
- `~/.local/share/timestamp/runtime/` - Données runtime

## Thèmes

4 thèmes sont disponibles :
- `dark` - Sombre (par défaut)
- `monokai` - Monokai
- `amber` - Jaune/Gris
- `flexoki` - Flexoki

## Contribution

Les contributions sont les bienvenues ! Veuillez ouvrir une issue ou une pull request sur le dépôt GitHub.

## Licence

Ce projet est sous licence MIT - voir le fichier [LICENSE](LICENSE) pour plus de détails.
