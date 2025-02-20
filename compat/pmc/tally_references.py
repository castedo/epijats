#!/usr/bin/python3

import argparse
from collections import Counter
from pathlib import Path
from pprint import pprint

from lxml import etree

from fastindex import FastIndex

XML = etree.XMLParser(remove_comments=True, load_dtd=False)


PUB_ID_TYPES = Counter()


def tally_element_citation(path: Path, e):
    assert e is not None
    assert e.tag == 'element-citation'
    for s in e:
        if s.tag in ['pub-id']:
            PUB_ID_TYPES.update([s.get('pub-id-type')])


def tally_article(path: Path):
    et = etree.parse(path, parser=XML)
    root = et.getroot()
    for ref in root.findall('back/ref-list/ref'):
        for e in ref.findall('element-citation'):
            tally_element_citation(path, e)
        for e in ref.findall('citation-alternatives/element-citation'):
            tally_element_citation(path, e)


JUMP = 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PubMed Central Data Probe")
    parser.add_argument("pmcpath", type=Path, help="path to PMC S3 data dump")
    args = parser.parse_args()
    index = FastIndex(args.pmcpath)
    paths = list(index.journal_list_paths('unmixed_journals.txt'))
    for p in paths[::JUMP]:
        assert p.exists()
        tally_article(p)
    pprint(PUB_ID_TYPES)
