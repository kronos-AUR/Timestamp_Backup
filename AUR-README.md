# Timestamp AUR Package

This repository contains the AUR package for **Timestamp**, a backup and restore tool with graphical user interface for Linux.

## Installation

### Using an AUR Helper (Recommended)

```bash
# With yay (recommended)
yay -S timestamp-backup

# With paru
paru -S timestamp-backup

# With pikaur
pikaur -S timestamp-backup
```

### Manual Installation

```bash
# Clone the AUR repository
git clone https://aur.archlinux.org/timestamp-backup.git
cd timestamp-backup

# Build and install
makepkg -si
```

## Dependencies

### Required Dependencies
- python
- python-pywebview
- python-qtpy
- python-pillow
- python-cryptography
- python-pyqt6
- python-pyqt6-webengine
- cronie
- xcb-util-cursor

### Optional Dependencies
- **python-smbc**: For direct SMB support (access network shares without mounting)
- **gvfs-smb**: For SMB mount support on GNOME
- **xdg-user-dirs**: For user directories management
- **kio-fuse**: For SMB mount support on KDE

Install optional dependencies with:
```bash
yay -S python-smbc gvfs-smb xdg-user-dirs kio-fuse
```

## Usage

### Launch the Graphical Interface
```bash
timestamp-backup-gui
```

### Use the Command Line Interface
```bash
# List profiles
timestamp-backup-cli profile list

# Add a backup profile
timestamp-backup-cli profile add my_profile /backup /home/user/Documents

# Run a backup
timestamp-backup-cli run my_profile

# Full backup (ignore incremental)
timestamp-backup-cli run my_profile --full

# Run a group backup
timestamp-backup-cli run my_group --group

# Restore from a backup
timestamp-backup-cli restore /backup/my_profile.zip /restore/path

# Add a profile with compression enabled, then run it
timestamp-backup-cli profile add my_backup /backup /home/user/Documents --compress
timestamp-backup-cli run my_backup

# Show complete help
timestamp-backup-cli --help
```

## Configuration

After installation, configuration files are created in:
- `~/.config/timestamp-backup/config.json` - Main configuration
- `~/.local/share/timestamp-backup/logs/` - Log files
- `~/.local/share/timestamp-backup/runtime/` - Runtime data (icons, encryption keys)

## Uninstallation

```bash
# Using an AUR helper
yay -Rns timestamp

# Manual removal
sudo pacman -Rns timestamp-backup

# Remove configuration files (optional)
rm -rf ~/.config/timestamp-backup/
rm -rf ~/.local/share/timestamp-backup/
```

## Known Issues

### QtWebEngine and Wayland
If you're using Wayland and the GUI doesn't open, try:
```bash
QT_QPA_PLATFORM=xcb timestamp-backup-gui
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

### Running as Root
If you run as root (e.g., on Kali Linux), you may need to set:
```bash
export QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox"
```

## Contributing

To contribute to this AUR package:
1. Fork this repository
2. Make your changes
3. Send a pull request

## License

**GNU General Public License version 3 (GPL-3.0-only)** - see the [LICENSE](LICENSE) file for details.

---

For issues and feature requests, please open an issue on GitHub or visit the AUR package page:
https://aur.archlinux.org/packages/timestamp-backup
