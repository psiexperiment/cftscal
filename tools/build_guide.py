'''
Build the copy of the user guide bundled with cftscal (cftscal/guide).

Usage::

    python tools/build_guide.py              # build it
    python tools/build_guide.py --check dist # check built packages include it

Builds the same pages as the website (docs/, mkdocs.yml) with
mkdocs-offline.yml, so they work without a network: links point at .html
files, search works from disk, and the fonts and scripts the website
loads from the internet (MathJax for formulas, Mermaid for diagrams, the
Roboto font) are downloaded into the build. Home's User Guide panel shows
this copy, falling back to the website when it isn't there.

cftscal/guide isn't tracked by git: the release workflow
(.github/workflows/publish-to-pypi.yml) runs this before packaging, then
--check to make sure the wheel and sdist include it. Run it yourself
before building a package any other way (e.g. with PyInstaller).

Needs mkdocs and mkdocs-material installed, and a network connection
while it runs (to download those files).
'''
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile

REPO = Path(__file__).parents[1]
OUT = REPO / 'cftscal' / 'guide'

#: What a package must contain for the guide to count as included.
GUIDE_INDEX = 'cftscal/guide/index.html'


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    subprocess.run(
        [sys.executable, '-m', 'mkdocs', 'build', '--clean',
         '-f', str(REPO / 'mkdocs-offline.yml'), '-d', str(OUT)],
        cwd=REPO, check=True,
    )
    files = [p for p in OUT.rglob('*') if p.is_file()]
    size = sum(p.stat().st_size for p in files) / 1e6
    print(f'Built {len(files)} files ({size:.1f} MB) in {OUT}')


def package_names(path):
    '''File names inside a wheel or sdist, with '/' separators.'''
    if path.suffix == '.whl':
        with zipfile.ZipFile(path) as z:
            return z.namelist()
    with tarfile.open(path) as t:
        # An sdist's files sit under a top-level <name>-<version>/ folder.
        return [n.split('/', 1)[-1] for n in t.getnames()]


def check(dist):
    '''
    Check every wheel and sdist in ``dist`` includes the guide. Returns
    the number of packages missing it.
    '''
    packages = sorted(Path(dist).glob('*.whl')) + sorted(Path(dist).glob('*.tar.gz'))
    if not packages:
        print(f'No packages found in {dist}')
        return 1
    missing = 0
    for package in packages:
        ok = GUIDE_INDEX in package_names(package)
        print(f'{"ok" if ok else "MISSING THE USER GUIDE"}: {package.name}')
        missing += not ok
    return missing


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--check', metavar='DIST',
                        help='check the packages in DIST include the guide '
                             'instead of building it')
    args = parser.parse_args()
    if args.check:
        sys.exit(1 if check(args.check) else 0)
    build()


if __name__ == '__main__':
    main()
