# Maintainer: Your Name <your.email@example.com>
# Contributor: Your Name <your.email@example.com>

pkgname=timestamp
pkgver=1.1
pkgrel=1
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
provides=('timestamp')
conflicts=()
replaces=()
backup=()
options=()
install=timestamp.install
changelog=

source=(
    "${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz"
    "config.json.default"
)
sha256sums=('SKIP'
            'SKIP')

package() {
    cd "${pkgname}-${pkgver}"
    
    # Install Python files to /usr/lib/timestamp
    install -d "${pkgdir}/usr/lib/${pkgname}"
    cp -r timestamp/* "${pkgdir}/usr/lib/${pkgname}/"
    
    # Install icon
    install -d "${pkgdir}/usr/share/icons/hicolor/scalable/apps"
    install -Dm644 timestamp/icon/timestamp.svg "${pkgdir}/usr/share/icons/hicolor/scalable/apps/timestamp.svg"
    
    # Install .desktop file
    install -d "${pkgdir}/usr/share/applications"
    install -Dm644 scripts/timestamp.desktop "${pkgdir}/usr/share/applications/timestamp.desktop"
    
    # Install startup scripts in /usr/bin
    install -d "${pkgdir}/usr/bin"
    install -Dm755 scripts/timestamp "${pkgdir}/usr/bin/timestamp"
    install -Dm755 scripts/timestamp-gui "${pkgdir}/usr/bin/timestamp-gui"
    install -Dm755 scripts/timestamp-cli "${pkgdir}/usr/bin/timestamp-cli"
    
    # Install default configuration file
    install -d "${pkgdir}/usr/share/${pkgname}"
    install -Dm644 timestamp/requirements.txt "${pkgdir}/usr/share/${pkgname}/requirements.txt"
    install -Dm644 config.json.default "${pkgdir}/usr/share/${pkgname}/config.json.default"
    
    # Install documentation
    install -d "${pkgdir}/usr/share/doc/${pkgname}"
    install -Dm644 README.md "${pkgdir}/usr/share/doc/${pkgname}/README.md"
    install -Dm644 LICENSE "${pkgdir}/usr/share/doc/${pkgname}/LICENSE"
    
    # Install install script
    install -Dm644 timestamp.install "${pkgdir}/.INSTALL"
}

# vim: ts=4 sw=4 et:
