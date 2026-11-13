# Maintainer: Your Name <your.email@example.com>
# Contributor: Your Name <your.email@example.com>

pkgname=timestamp
pkgver=1.1
pkgrel=1
pkgdesc="Outil de sauvegarde et de restauration portable avec interface graphique - Compatible Windows & Linux"
url="https://github.com/yourusername/timestamp"
license=('MIT')
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
    'python-smbc: Support SMB direct sans montage (acces aux partages reseau)'
    'gvfs-smb: Support montage SMB pour GNOME'
    'xdg-user-dirs: Gestion des dossiers utilisateur'
    'kio-fuse: Support montage SMB pour KDE'
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
)
sha256sums=('SKIP')

package() {
    cd "${pkgname}-${pkgver}"
    
    # Installer les fichiers Python dans /usr/lib/timestamp
    install -d "${pkgdir}/usr/lib/${pkgname}"
    cp -r timestamp/* "${pkgdir}/usr/lib/${pkgname}/"
    
    # Installer l'icone
    install -d "${pkgdir}/usr/share/icons/hicolor/scalable/apps"
    install -Dm644 timestamp/icon/timestamp.svg "${pkgdir}/usr/share/icons/hicolor/scalable/apps/timestamp.svg"
    
    # Installer le fichier .desktop
    install -d "${pkgdir}/usr/share/applications"
    install -Dm644 scripts/timestamp.desktop "${pkgdir}/usr/share/applications/timestamp.desktop"
    
    # Installer les scripts de lancement dans /usr/bin
    install -d "${pkgdir}/usr/bin"
    install -Dm755 scripts/timestamp "${pkgdir}/usr/bin/timestamp"
    install -Dm755 scripts/timestamp-gui "${pkgdir}/usr/bin/timestamp-gui"
    install -Dm755 scripts/timestamp-cli "${pkgdir}/usr/bin/timestamp-cli"
    
    # Installer le fichier de configuration par defaut
    install -d "${pkgdir}/usr/share/${pkgname}"
    install -Dm644 timestamp/requirements.txt "${pkgdir}/usr/share/${pkgname}/requirements.txt"
    
    # Installer la documentation
    install -d "${pkgdir}/usr/share/doc/${pkgname}"
    install -Dm644 README.md "${pkgdir}/usr/share/doc/${pkgname}/README.md"
    install -Dm644 LICENSE "${pkgdir}/usr/share/doc/${pkgname}/LICENSE"
    
    # Installer le fichier install script
    install -Dm644 timestamp.install "${pkgdir}/.INSTALL"
}

# vim: ts=4 sw=4 et:
