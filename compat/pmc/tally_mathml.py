#!/usr/bin/python3

import argparse
from collections import Counter
from pathlib import Path
from pprint import pprint

from lxml import etree

XML = etree.XMLParser(remove_comments=True, load_dtd=False)

MATHML_NAMESPACE_PREFIX = "{http://www.w3.org/1998/Math/MathML}"


COUNT = Counter()
DISPLAY = Counter()
PARENT = {}
FORMULA_PARENT = dict(
    inline_formula=Counter(),
    disp_formula=Counter(),
)

def tally_article(path: Path):
    et = etree.parse(path, parser=XML)
    root = et.getroot()
    math = False
    for m in root.iter(MATHML_NAMESPACE_PREFIX + 'math'):
        math = True
        display = m.attrib.get('display')
        DISPLAY.update([display])
        PARENT.setdefault(display, Counter())
        PARENT[display].update([m.getparent().tag])
    for m in root.iter('inline-formula'):
        FORMULA_PARENT['inline_formula'].update([m.getparent().tag])
    for m in root.iter('disp-formula'):
        FORMULA_PARENT['disp_formula'].update([m.getparent().tag])

    if math:
        COUNT.update(['math'])
    for m in root.iter('tex-math'):
        COUNT.update(['tex-math'])
        break


JUMP = 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PubMed Central Data Probe")
    parser.add_argument("pmcpath", type=Path, help="path to PMC S3 data dump")
    args = parser.parse_args()

    paths = []
#    paths += list((args.pmcpath / "oa_comm/xml/all").iterdir())
#    paths += list((args.pmcpath / "oa_noncomm/xml/all").iterdir())
    paths = open(args.pmcpath / "mathdocs.txt").readlines()
    paths = [args.pmcpath / p.strip() for p in paths]

    for p in paths[::JUMP]:
        assert p.exists(), p
        tally_article(p)
    print("DISPLAY")
    pprint(DISPLAY)

    print("PARENT")
    pprint(PARENT)

    print("FORMULA_PARENT")
    pprint(FORMULA_PARENT)

    print("COUNT")
    pprint(COUNT)
