# Maintainer: Kronosaur

pkgname=timestamp-backup
pkgver=1.1
pkgrel=2
pkgdesc="Portable backup and restore tool with graphical user interface - Compatible with Linux"
url="https://github.com/kronos-AUR/Timestamp_Backup"
license=('GPL3')
arch=('x86_64' 'aarch64')
groups=()
depends=(
    'python'
    'python-pywebview'
    'python-qtpy'
    'python-pillow'
    'python-cryptography'
    'python-pyqt6'
    'python-pyqt6-webengine'
    'cronie'
    'xcb-util-cursor'
)
makedepends=()
checkdepends=()
optdepends=(
    'python-smbc: Direct SMB support without mounting (access network shares)'
    'gvfs-smb: SMB mount support for GNOME'
    'xdg-user-dirs: User directories management'
    'kio-fuse: SMB mount support for KDE'
)
provides=()
conflicts=()
replaces=()
backup=()
options=()
install=timestamp-backup.install
changelog=

source=(
    "${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz"
    "config.json.default"
)
sha256sums=('SKIP'
            '99ae2234c584031bb0e3bb9846548945c0109d7bfd8d52906422accafeb0cb60')

package() {
    cd "${srcdir}"/Timestamp_Backup-*

    # Install Python files to /usr/lib/timestamp-backup
    install -d "${pkgdir}/usr/lib/${pkgname}"
    cp -r timestamp/* "${pkgdir}/usr/lib/${pkgname}/"
    find "${pkgdir}/usr/lib/${pkgname}" -type d -name '__pycache__' -exec rm -rf {} +
    
    # Install icon
    install -d "${pkgdir}/usr/share/icons/hicolor/scalable/apps"
    install -Dm644 timestamp/icon/timestamp-backup.svg "${pkgdir}/usr/share/icons/hicolor/scalable/apps/timestamp-backup.svg"
    
    # Install .desktop file
    install -d "${pkgdir}/usr/share/applications"
    install -Dm644 scripts/timestamp-backup.desktop "${pkgdir}/usr/share/applications/timestamp-backup.desktop"
    
    # Install startup scripts in /usr/bin
    install -d "${pkgdir}/usr/bin"
    install -Dm755 scripts/timestamp-backup "${pkgdir}/usr/bin/timestamp-backup"
    install -Dm755 scripts/timestamp-backup-gui "${pkgdir}/usr/bin/timestamp-backup-gui"
    install -Dm755 scripts/timestamp-backup-cli "${pkgdir}/usr/bin/timestamp-backup-cli"
    
    # Install default configuration file
    install -d "${pkgdir}/usr/share/${pkgname}"
    install -Dm644 timestamp/requirements.txt "${pkgdir}/usr/share/${pkgname}/requirements.txt"
    install -Dm644 "${srcdir}/config.json.default" "${pkgdir}/usr/share/${pkgname}/config.json.default"
    
    # Install documentation
    install -d "${pkgdir}/usr/share/doc/${pkgname}"
    install -Dm644 README.md "${pkgdir}/usr/share/doc/${pkgname}/README.md"
    install -Dm644 LICENSE "${pkgdir}/usr/share/doc/${pkgname}/LICENSE"
}

# vim: ts=4 sw=4 et:
