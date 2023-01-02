#!/bin/python3

import os, tempfile
from pathlib import Path

from epijats.jats import JatsBaseprint

HERE_DIR = Path(__file__).parent
CASES_DIR = HERE_DIR / "tests/cases-webstract"

for case in os.listdir(CASES_DIR):
    print(case)
    with tempfile.TemporaryDirectory() as tmpdir:
        bp = JatsBaseprint(CASES_DIR / case / "input", tmpdir, [])
        w = bp.to_webstract()
        w.dump_json(CASES_DIR / case / 'output.json')
        w.dump_xml(CASES_DIR / case / 'output.xml')
