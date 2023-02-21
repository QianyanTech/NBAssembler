 
# Maintainer: Alvin Zhu <alvin.zhuge@gmail.com>
pkgname=python-nbasm
pkgver=11.6.2
pkgrel=1
pkgdesc="NB Assembler"
arch=('any')
url="https://github.com/AlvinZhu/NBAssembler"
license=('GPL')
groups=('aur-alvin')
depends=('python')
optdepends=("CUDA: NVIDIA's GPU programming toolkit")
makedepends=('python-setuptools')

package() {
  cp -r ../nbas ../nbasm ../setup.py "$srcdir"
  python setup.py install --root="$pkgdir/" --optimize=1
}