#!/bin/python3

import hidos

import os, tempfile
from pathlib import Path

from epijats import Webstract
from epijats import jats


HERE_DIR = Path(__file__).parent
CASES_DIR = HERE_DIR / "tests/cases/webstract"
SUCC_DIR = HERE_DIR / "tests/cases/succession"


for case in os.listdir(CASES_DIR):
    print(case)
    w = jats.webstract_from_jats(CASES_DIR / case / "input")
    w.dump_json(CASES_DIR / case / "output.json")
    w.dump_xml(CASES_DIR / case / "output.xml")

archive = hidos.Archive(".", unsigned_ok=True)

with tempfile.TemporaryDirectory() as tmpdir:
    for case in os.listdir(SUCC_DIR):
        print(case)
        succ = archive.find_succession(case)
        for edition in succ.root.all_subeditions():
            if edition.has_digital_object:
                dest = SUCC_DIR / case / str(edition.edid)
                w = Webstract.from_edition(edition, tmpdir / str(edition.dsi))
                w.dump_json(dest / "output.json")
                w.dump_xml(dest / "output.xml")
