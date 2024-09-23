#!/usr/bin/env -S just --justfile

default:
    just --list

test:
    python3 -Wdefault -m pytest

dist:
    python3 -m build

clean:
    rm -rf dist
    rm -rf build
    rm -rf epijats.egg-info
    rm -f epijats/_version.py
