import pytest

import jsoml

import os
from pathlib import Path


TESTS_DIR = Path(__file__).parent
WEBSTRACT_DIR = TESTS_DIR / "cases/webstract"


@pytest.mark.parametrize("case", os.listdir(WEBSTRACT_DIR))
def test_webstract_xml_dumps_n_loads(case):
    expected = jsoml.load(WEBSTRACT_DIR / case / "output.xml")
    got = jsoml.loads(jsoml.dumps(expected))
    assert got == expected
