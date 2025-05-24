import pytest

import subprocess, tempfile
from os import listdir
from pathlib import Path

import hidos

from epijats import util, Webstract
from epijats.jats import webstract_from_jats


CASES_DIR = Path(__file__).parent / "cases"

WEBSTRACT_CASES = [f"webstract/{s}" for s in listdir(CASES_DIR / "webstract")]
SUCCESSION_CASES = listdir(CASES_DIR / "succession")

EDITION_CASES = list()
for s in SUCCESSION_CASES:
    for e in listdir(CASES_DIR / "succession" / s):
        EDITION_CASES.append(f"succession/{s}/{e}")

ARCHIVE_DIR = Path(__file__).parent / "_archive"
if not ARCHIVE_DIR.exists():
    bundle = CASES_DIR / "test_succession_archive.bundle"
    subprocess.run(
        ["git", "clone", "--bare", bundle, ARCHIVE_DIR],
        check=True,
    )


@pytest.mark.parametrize("case", WEBSTRACT_CASES)
def test_webstracts(case):
    got = webstract_from_jats(CASES_DIR / case / "input")
    expect = Webstract.load_json(CASES_DIR / case / "output.json")
    if 'issues' not in expect:
        del got['issues']
    assert got == expect


@pytest.mark.parametrize("case", SUCCESSION_CASES)
def test_editions(case):
    with tempfile.TemporaryDirectory() as tmpdir:
        succs = hidos.repo_successions(ARCHIVE_DIR)
        assert 1 == len(succs)
        succ = succs.pop()
        assert str(succ.dsi) == case
        for edition in succ.root.all_subeditions():
            if edition.snapshot: 
                subdir = Path(tmpdir) / str(edition.dsi)
                got = Webstract.from_edition(edition, subdir)

                edition_path = CASES_DIR / "succession" / case / str(edition.edid)
                expect = Webstract.load_json(edition_path / "output.json")
                if 'issues' not in expect:
                    del got['issues']
                assert got == expect
                for v in got.values():
                  assert isinstance(v, (int, str, list, dict))


def test_hash_file():
    got = util.swhid_from_files(CASES_DIR / "webstract/basic1/input/article.xml")
    assert got == "swh:1:cnt:2c0193c32db0f3d20f974b5f6f5e656e6898d56e"


def test_hash_dir():
    got = util.swhid_from_files(CASES_DIR / "webstract/basic1/input")
    assert got == "swh:1:dir:7a05d41c586ea4cbfa5a5e0021bc2a00ac8998ba"
