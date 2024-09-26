#!/usr/bin/env -S just --justfile

default:
    just --list

export JUSTFILE_DIR := justfile_directory()

test:
    python3 -Wdefault -m pytest

dist:
    python3 -m build

[no-cd]
dev-build $DEST:
    PYROOT=$JUSTFILE_DIR $JUSTFILE_DIR/scripts/build-pydist-wheel.sh

clean:
    rm -rf dist
    rm -rf build
    rm -rf epijats.egg-info
    rm -f epijats/_version.py
