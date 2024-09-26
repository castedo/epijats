#/usr/bin/env bash
set -o errexit -o pipefail -o nounset

set -o xtrace

VERSION=$(python -m setuptools_scm --root $PYROOT)
python3 -m build --wheel --no-isolation --outdir $DEST $PYROOT
cd $DEST
mv epijats-$VERSION-py3-none-any.whl epijats-py3-none-any.whl
