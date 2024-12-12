import pytest

import subprocess, tempfile
from os import listdir
from pathlib import Path

import hidos

from epijats import util, Webstract, DocLoader
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
    assert got == expect


@pytest.mark.parametrize("case", SUCCESSION_CASES)
def test_editions(case):
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = DocLoader(tmpdir)
        if hasattr(hidos, 'repo_successions'):
            succs = hidos.repo_successions(ARCHIVE_DIR)
            assert 1 == len(succs)
            succ = succs.pop()
        else:  # hidos 1.x does not have top level Archive
            archive = hidos.Archive(ARCHIVE_DIR, unsigned_ok=True)
            succ = archive.find_succession(case)
        assert str(succ.dsi) == case
        for edition in succ.root.all_subeditions():
            if hasattr(edition, 'snapshot'):
                by_snapshot = getattr(edition, 'snapshot', None)
            else:  # hidos 1.x does not have edition.snapshot attribute
                by_snapshot = edition.has_digital_object
            if by_snapshot: 
                got = loader.webstract_from_edition(edition)
                edition_path = CASES_DIR / "succession" / case / str(edition.edid)
                expect = Webstract.load_json(edition_path / "output.json")
                if not hasattr(edition, 'date'):
                    got['date'] = expect['date']  # don't test date with hidos 1.x
                assert got == expect


@pytest.mark.parametrize("case", WEBSTRACT_CASES + EDITION_CASES)
def test_xml(case):
    got = Webstract.load_xml(CASES_DIR / case / "output.xml")
    expect = Webstract.load_json(CASES_DIR / case / "output.json")
    assert got == expect


def test_hash_file():
    got = util.swhid_from_files(CASES_DIR / "webstract/basic1/input/article.xml")
    assert got == "swh:1:cnt:2c0193c32db0f3d20f974b5f6f5e656e6898d56e"


def test_hash_dir():
    got = util.swhid_from_files(CASES_DIR / "webstract/basic1/input")
    assert got == "swh:1:dir:7a05d41c586ea4cbfa5a5e0021bc2a00ac8998ba"
