#!/usr/bin/python3

import argparse
from collections import Counter
from pathlib import Path
from pprint import pp

from lxml import etree

from fastindex import FastIndex


XML = etree.XMLParser(remove_comments=True, load_dtd=False)


CHILD_TAGS: dict[str, Counter] = dict()


def tally_children(parent):
    if len(parent):
        counter = CHILD_TAGS.setdefault(parent.tag, Counter())
        counter.update(['TOTAL'])
        for child in parent:
            counter.update([child.tag])
#                if child.tag == 'xref':
#                    print(path, etree.tostring(child))


def tally_article(path: Path):
    et = etree.parse(path, parser=XML)
    root = et.getroot()

#    for title in root.findall('front/article-meta/title-group/article-title'):
#        tally_children(title)
    for title in root.findall('back/ref-list/ref/element-citation/article-title'):
        tally_children(title)
    for title in root.findall('back/ref-list/ref/element-citation/source'):
        tally_children(title)
    for tag in ['title', 'copyright-statement', 'license-p', 'comment']:
        for parent in root.iter(tag):
            tally_children(parent)


ARTICLES = 0

JUMP = 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PubMed Central Data Probe")
    parser.add_argument("pmcpath", type=Path, help="path to PMC S3 data dump")
    args = parser.parse_args()
    index = FastIndex(args.pmcpath)
    paths = list(index.path(e) for e in index.entries)
    for p in paths[::JUMP]:
        if p.exists():
            tally_article(p)
            ARTICLES += 1

    print(f"{ARTICLES=}")
    pp(CHILD_TAGS)
