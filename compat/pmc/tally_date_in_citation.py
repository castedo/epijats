#!/usr/bin/python3

import argparse
from collections import Counter
from pathlib import Path
from pprint import pprint

from lxml import etree

from fastindex import FastIndex


XML = etree.XMLParser(remove_comments=True, load_dtd=False)


CONTENT_TYPES = Counter()
FLAGS = Counter()

def tally_date(path: Path, e):
    assert e is not None
    assert e.tag == 'date-in-citation'
    ctype = e.attrib.get('content-type')
    CONTENT_TYPES.update([ctype])
    if ctype == 'access-date':
        flag = 0
        if len(e) > 0:
            assert e.text is None or not e.text.strip()
            assert all(s.tail is None or not s.tail.strip() for s in e)
            flag += 4 * int(e.find('year') is not None)
            flag += 2 * int(e.find('month') is not None)
            flag += 1 * int(e.find('day') is not None)
        else:
            flag += 8 * int('iso-8601-date' in e.attrib)
        FLAGS.update([flag])


def tally_article(path: Path):
    et = etree.parse(path, parser=XML)
    root = et.getroot()
    for ref in root.findall('back/ref-list/ref'):
        for e in ref.findall('element-citation/date-in-citation'):
            tally_date(path, e)
        for e in ref.findall('citation-alternatives/element-citation/date-in-citation'):
            tally_date(path, e)


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
    pprint(CONTENT_TYPES)
    pprint(FLAGS)
