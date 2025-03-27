#!/usr/bin/env bash
set -o errexit -o pipefail -o nounset

set -o xtrace

python3 -m build --wheel --no-isolation --outdir $DEST $PYROOT
VERSION=$(python3 -m setuptools_scm --root $PYROOT)
CLEAN_VERSION=$(python3 -m setuptools_scm --root $PYROOT --strip-dev)
cd $DEST
mv epijats-$VERSION-py3-none-any.whl epijats-$CLEAN_VERSION-py3-none-any.whl
