#!/usr/bin/env -S just --justfile

default:
    just --list

export JUSTFILE_DIR := justfile_directory()

test: && test-runtime
    ruff check epijats || true
    mypy --strict epijats
    cd tests && mypy --ignore-missing-imports .  # cd for separate mypy cache+config

test-runtime:
    python3 -m pytest -vv tests

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
