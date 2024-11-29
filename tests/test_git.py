import pytest

import tempfile
from pathlib import Path

import git

from hidos.util import EMPTY_TREE 
from epijats.util import swhid_from_files


def test_empty_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert "swh:1:dir:" + EMPTY_TREE == swhid_from_files(tmpdir)


def get_swhid_from_git(path: Path):
    if not path.is_dir():
        return "swh:1:cnt:" + str(git.Git().hash_object(path))
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = git.Repo.init(tmpdir)
        g = git.Git(path)  # path is working dir
        g.set_persistent_git_options(git_dir=repo.git_dir)
        g.add(".")
        return "swh:1:dir:" + str(g.write_tree())
