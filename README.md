# Timestamp

**Backup and restore tool with graphical user interface for Linux**

[![AUR version](https://img.shields.io/aur/version/timestamp?style=flat-square)](https://aur.archlinux.org/packages/timestamp)
[![License](https://img.shields.io/badge/license-GPL--3.0--only-blue.svg?style=flat-square)](LICENSE)

Timestamp is a simple yet powerful backup solution designed for Linux users who want an easy-to-use tool with both GUI and CLI interfaces.

## Features

- **Graphical User Interface** - Modern, intuitive GUI based on PyQt6/WebView
- **Command Line Interface** - Full-featured CLI for automation and scripting
- **Multiple Backup Types** - Simple copy or compressed archives (zip, tar.gz)
- **Incremental Backups** - Only copy changed files to save time and space
- **Network Shares Support** - Backup to SMB/CIFS network shares
- **Scheduled Backups** - Automate backups using cron or systemd timers
- **Multiple Themes** - Choose from 4 different themes (Dark, Monokai, Amber, Flexoki)
- **Restore Functionality** - Restore individual files or entire backups
- **Backup Groups** - Run multiple backups in sequence
- **Linux** - Tested on Arch, Debian, Ubuntu, Kali, Fedora

## Installation

### From AUR (Arch Linux)

```bash
# With yay (recommended)
yay -S timestamp

# With paru
paru -S timestamp

# With makepkg
git clone https://aur.archlinux.org/timestamp.git
cd timestamp
makepkg -si
```

### Requirements

**Required:**
- python
- python-pywebview (>=4.4)
- python-qtpy (>=2.4)
- python-pillow (>=10.0)
- python-cryptography (>=40.0)
- python-pyqt6
- python-pyqt6-webengine
- cronie
- xcb-util-cursor

**Optional:**
- python-smbc: Direct SMB support (network shares access without mounting)
- gvfs-smb: SMB mounting support for GNOME
- xdg-user-dirs: User directories management
- kio-fuse: SMB mounting support for KDE

Install optional dependencies with:
```bash
yay -S python-smbc gvfs-smb xdg-user-dirs kio-fuse
```

## Usage

### Graphical Interface

```bash
timestamp-gui
```

### Command Line Interface

#### Profile Management

```bash
# List profiles
timestamp-cli profile list

# Add a backup profile
timestamp-cli profile add my_backup /backup/path /home/user/Documents

# Add a backup profile with compression
timestamp-cli profile add my_backup /backup/path /home/user/Documents --compress

# Remove a profile
timestamp-cli profile remove my_backup
```

#### Backup

```bash
# Run a backup
timestamp-cli run my_backup

# Full backup (ignore incremental)
timestamp-cli run my_backup --full

# Run a backup group
timestamp-cli run my_group --group
```

#### Restore

```bash
# Manual restore
timestamp-cli restore /backup/archive.tar.gz /restore/path

# Restore with incremental check
timestamp-cli restore /backup/archive.tar.gz /restore/path --incremental

# Restore using a profile
timestamp-cli restore --profile my_restore_profile

# Manage restore profiles
timestamp-cli restore-profile add my_restore /backup/archive.tar.gz /restore/path
timestamp-cli restore-profile list
timestamp-cli restore-profile remove my_restore
```

Restoring a folder copies its content into the destination folder (the folder structure of the source is preserved); restoring an archive extracts its content the same way.

#### Scheduled Backups

Scheduled backups are managed through the GUI or automatically when creating schedules.

## Configuration

After installation, configuration files are stored in:
- `~/.config/timestamp/config.json` - Main configuration
- `~/.local/share/timestamp/logs/` - Log files
- `~/.local/share/timestamp/runtime/` - Runtime data (icons, encryption keys)

## Themes

4 themes are available:
- `flexoki` - Flexoki theme (default)
- `dark` - Dark theme
- `monokai` - Monokai theme
- `amber` - Yellow/Gray theme

## Network Shares

### SMB Support

Timestamp supports SMB/CIFS network shares through multiple methods:

1. **Direct SMB (recommended)** - Install `python-smbc` for direct access without mounting
2. **GNOME GVFS** - Install `gvfs-smb` for GNOME integration
3. **KDE kio-fuse** - Install `kio-fuse` for KDE integration

### Adding a Network Share

In the GUI:
1. Go to Network page
2. Click "Add" button
3. Enter server details, credentials, and share name
4. Save and test connection

## Troubleshooting

### QtWebEngine and Wayland

If you use Wayland and the GUI doesn't open, try:
```bash
QT_QPA_PLATFORM=xcb timestamp-gui
```

### SMB Issues

If network shares don't work:
1. Install `python-smbc` for direct SMB support
2. Or install `gvfs-smb` (GNOME) or `kio-fuse` (KDE) for mounting

### Cron Not Enabled

If scheduled backups don't run:
```bash
sudo systemctl enable --now cronie
```

## Uninstallation

```bash
# With AUR helper
yay -Rns timestamp

# Manual
sudo pacman -Rns timestamp

# Remove configuration files (optional)
rm -rf ~/.config/timestamp/
rm -rf ~/.local/share/timestamp/
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

GNU General Public License version 3 (GPL-3.0-only) - see [LICENSE](LICENSE) file for details.

---

## Documentation en Français

Voir [AUR-README.md](AUR-README.md) pour la documentation en français.

---

**Note:** This project is not affiliated with any commercial backup service. It's a free and open-source backup tool for personal use.
