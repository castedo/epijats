import pytest

import os
from pathlib import Path

from epijats import util
from epijats.jats import JatsBaseprint
from epijats.webstract import Webstract


TESTS_DIR = Path(__file__).parent
CASES_DIR = TESTS_DIR / "cases-webstract"
test_cases = os.listdir(CASES_DIR)


@pytest.mark.parametrize("case", test_cases)
def test_webstracts(case, tmp_path):
    bp = JatsBaseprint(CASES_DIR / case / "input", tmp_path, [])
    got = bp.to_webstract()
    expect = Webstract.load_json(CASES_DIR / case / "output.json")
    assert got == expect


@pytest.mark.parametrize("case", test_cases)
def test_xml(case):
    got = Webstract.load_xml(CASES_DIR / case / "output.xml")
    expect = Webstract.load_json(CASES_DIR / case / "output.json")
    assert got == expect


def test_hash_file():
    got = util.swhid_from_files(CASES_DIR / "basic1/input/article.xml")
    assert got == "swh:1:cnt:2c0193c32db0f3d20f974b5f6f5e656e6898d56e"


def test_hash_dir():
    got = util.swhid_from_files(CASES_DIR / "basic1/input")
    assert got == "swh:1:dir:7a05d41c586ea4cbfa5a5e0021bc2a00ac8998ba"
