#!/usr/bin/python3

import argparse
from collections import Counter
from pathlib import Path
from pprint import pprint

from lxml import etree

from fastindex import FastIndex

XML = etree.XMLParser(remove_comments=True, load_dtd=False)


PUB_TYPES = Counter()
JOURNAL_FIELDS: dict[str, Counter] = dict()
WEBPAGE_FIELDS: dict[str, Counter] = dict()
BOOK_FIELDS: dict[str, Counter] = dict()
FIELDS: dict[str, Counter] = dict()
PUB_ID_TYPES = Counter()

FIELD_CATEGORY = {
    'source': 'TITLE',
    'article-title': 'TITLE',
    'part-title': 'TITLE',
    'data-title': 'TITLE',
    'year': 'DATE',
    'month': 'DATE',
    'day': 'DATE',
    'season': 'DATE',
    'date': 'DATE',
    'date-in-citation': 'DATE',
    'conf-date': 'DATE',
    'edition': 'VERSION',
    'version': 'VERSION',
    'volume': 'PART',
    'issue': 'PART',
    'issue-part': 'PART',
    'series': 'PART',
    'supplement': 'PART',
    'elocation-id': 'PAGES',
    'fpage': 'PAGES',
    'lpage': 'PAGES',
    'page-range': 'PAGES',
    'size': 'PAGES',
    'uri': 'LINK',
    'object-id': 'LINK',
    'ext-link': 'LINK',
}


def tally_element_citation(path: Path, e):
    assert e is not None
    assert e.tag == 'element-citation'
    pub_type = e.attrib.get('publication-type')
    PUB_TYPES.update([pub_type])
    for s in e:
        if s.tag in ['pub-id']:
            PUB_ID_TYPES.update([s.get('pub-id-type')])
        elif s.tag not in ['person-group']:
            category = FIELD_CATEGORY.get(s.tag, 'OTHER')
            match pub_type:
                case 'journal':
                    counter = JOURNAL_FIELDS.setdefault(category, Counter())
                case 'webpage':
                    counter = WEBPAGE_FIELDS.setdefault(category, Counter())
                case 'book':
                    counter = BOOK_FIELDS.setdefault(category, Counter())
                case _:
                    counter = FIELDS.setdefault(category, Counter())
            counter.update([s.tag])


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
    print("\n<element-citation publication-type=")
    pprint(PUB_TYPES)
    print("\n<pub-id pub-id-type=")
    pprint(PUB_ID_TYPES)
    print("\n<element-citation publication-type='journal' 'fields'")
    pprint(JOURNAL_FIELDS)
    print("\n<element-citation publication-type='webpage' 'fields'")
    pprint(WEBPAGE_FIELDS)
    print("\n<element-citation publication-type='book' 'fields'")
    pprint(BOOK_FIELDS)
    print("\n<element-citation publication-type= other 'fields'")
    pprint(FIELDS)
