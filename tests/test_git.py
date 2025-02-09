import pytest

import tempfile
from pathlib import Path

from hidos.util import EMPTY_TREE 
from epijats.util import swhid_from_files


SNAPSHOT_CASE = Path(__file__).parent / "cases" / "snapshot"

CASE_SWHIDS = {
    'just_a_file.txt': 'swh:1:cnt:e7ee9eec323387d82a370674c1e2996d25c2414d',
    'baseprint': 'swh:1:dir:c68c7b8f0d3ba2d5cab95f5b4d4c67dffb588e45',
    'with_hidden_file': 'swh:1:dir:78443c297b679d31de48a1de51af08ff46ba0e7f',
}


def test_empty_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert "swh:1:dir:" + EMPTY_TREE == swhid_from_files(tmpdir)


@pytest.mark.parametrize("case", CASE_SWHIDS.keys())
@pytest.mark.filterwarnings("ignore:Hidden files")
def test_swhids(case):
    assert CASE_SWHIDS[case] == swhid_from_files(SNAPSHOT_CASE / case)


def get_swhid_from_git(path: Path):
    git = pytest.importorskip("git")

    if not path.is_dir():
        return "swh:1:cnt:" + str(git.Git().hash_object(path))
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = git.Repo.init(tmpdir)
        g = git.Git(path)  # path is working dir
        g.set_persistent_git_options(git_dir=repo.git_dir)
        g.add(".")
        return "swh:1:dir:" + str(g.write_tree())


def test_a_file():
    a_file = SNAPSHOT_CASE / "just_a_file.txt"
    assert get_swhid_from_git(a_file) == swhid_from_files(a_file)


def test_a_baseprint():
    bp = SNAPSHOT_CASE / "baseprint"
    assert get_swhid_from_git(bp) == swhid_from_files(bp)


def test_with_hidden_file():
    with pytest.warns(UserWarning):
        bp = SNAPSHOT_CASE / "with_hidden_file"
        assert get_swhid_from_git(bp) != swhid_from_files(bp)
