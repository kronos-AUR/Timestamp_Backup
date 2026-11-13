# Timestamp AUR Package

Ce dépôt contient le paquet AUR pour **Timestamp**, un outil de sauvegarde et de restauration avec interface graphique.

## Installation

### Avec un helper AUR

```bash
# Avec yay (recommandé)
yay -S timestamp

# Avec paru
paru -S timestamp

# Avec pikaur
pikaur -S timestamp
```

### Manuellement

```bash
# Cloner le dépôt AUR
git clone https://aur.archlinux.org/timestamp.git
cd timestamp

# Construire et installer
makepkg -si
```

## Dépendances

### Dépendances obligatoires
- python
- python-pywebview
- python-qtpy
- python-pillow
- python-cryptography
- python-pyqt6
- python-pyqt6-webengine
- cronie
- xcb-util-cursor

### Dépendances optionnelles
- **python-smbc** : Pour le support SMB direct (accès aux partages réseau sans montage)
- **gvfs-smb** : Pour le support montage SMB sous GNOME
- **xdg-user-dirs** : Pour la gestion des dossiers utilisateur
- **kio-fuse** : Pour le support montage SMB sous KDE

Installez les dépendances optionnelles avec :
```bash
yay -S python-smbc gvfs-smb xdg-user-dirs kio-fuse
```

## Utilisation

### Lancer l'interface graphique
```bash
timestamp-gui
```

### Utiliser l'interface en ligne de commande
```bash
# Lister les profils
timestamp-cli profile list

# Ajouter un profil de sauvegarde
timestamp-cli profile add mon_profil /backup /home/user/Documents

# Lancer une sauvegarde
timestamp-cli run mon_profil

# Sauvegarde complète (ignore l'incrémental)
timestamp-cli run mon_profil --full

# Lancer une sauvegarde de groupe
timestamp-cli run mon_groupe --group

# Restaurer depuis une sauvegarde
timestamp-cli restore /backup/mon_profil.zip /restore/path

# Voir l'aide complète
timestamp-cli --help
```

## Configuration

Après l'installation, les fichiers de configuration sont créés dans :
- `~/.config/timestamp/config.json` - Configuration principale
- `~/.local/share/timestamp/logs/` - Journaux
- `~/.local/share/timestamp/runtime/` - Données runtime (icônes, clés de chiffrement)

## Désinstallation

```bash
# Avec un helper AUR
yay -Rns timestamp

# Manuellement
sudo pacman -Rns timestamp

# Supprimer les fichiers de configuration (optionnel)
rm -rf ~/.config/timestamp/
rm -rf ~/.local/share/timestamp/
```

## Problèmes connus

### QtWebEngine et Wayland
Si vous utilisez Wayland et que l'interface graphique ne s'ouvre pas, essayez :
```bash
QT_QPA_PLATFORM=xcb timestamp-gui
```

### Problèmes avec SMB
Si les partages réseau ne fonctionnent pas :
1. Installez `python-smbc` pour le support SMB direct
2. Ou installez `gvfs-smb` (GNOME) ou `kio-fuse` (KDE) pour le montage

### Cron non activé
Si les planifications ne s'exécutent pas :
```bash
sudo systemctl enable --now cronie
```

## Contribution

Pour contribuer à ce paquet AUR :
1. Fork ce dépôt
2. Faites vos modifications
3. Envoyez une pull request

## Licence

MIT License - voir le fichier [LICENSE](LICENSE) pour plus de détails.
