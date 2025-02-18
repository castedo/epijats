#!/usr/bin/python3

import argparse
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from fastindex import FastIndex

XML = etree.XMLParser(remove_comments=True, load_dtd=False)

REJECT_FIELDS = {
  'chapter-title',
  'collab',
  'etal',
  'italic',
  'name',
  'role',
  'std',
  'trans-source',
  'trans-title',
}

SKIP_ARTICLE_TYPES = {
    'abstract',
    'addendum',
    'discussion',
    'expression-of-concern',
    'introduction',
    'meeting-report',
    'news',
    'obituary',
    'reply',
}

class FileCase:
    def __init__(self, path: Path):
        self.path = path
        et = etree.parse(self.path, parser=XML)
        root = et.getroot()
        self.article_type = root.get('article-type')
        self.num_cites = 0
        self.num_ecites = 0
        self.bad_fields = Counter()
        for ref in root.findall('back/ref-list/ref'):
            for e in ref.findall('element-citation'):
                self.num_cites += 1
                self.num_ecites += 1
                self._ecitation(e)
            for e in ref.findall('mixed-citation'):
                self.num_cites += 1
            for e in ref.findall('citation-alternatives'):
                self.num_cites += 1
                for s in e.findall('element-citation'):
                    self.num_ecites += 1
                    self._ecitation(s)

    def _ecitation(self, e):
        assert e is not None, self.path
        assert e.tag == 'element-citation'
        for s in e:
            if isinstance(s.tag, str) and s.tag not in OK_FIELDS:
                self.bad_fields.update([s.tag])


OK_FIELDS = {
    'article-title', 
    'comment',
    'conf-date',
    'conf-loc',
    'conf-name',
    'conf-sponsor',
    'data-title',
    'date',
    'date-in-citation',
    'day',
    'edition',
    'elocation-id',
    'ext-link',
    'fpage',
    'gov',
    'isbn',
    'issn',
    'institution',
    'issue',
    'issue-part',
    'issue-title',
    'label',
    'lpage',
    'month',
    'object-id',
    'page-range',
    'patent',
    'part-title',
    'person-group',
    'pub-id',
    'publisher-loc',
    'publisher-name',
    'season',
    'series',
    'size',
    'source',
    'supplement',
    'uri',
    'version',
    'volume',
    'year',
}


@dataclass
class Tally:
    total: int = 0
    local: int = 0
    num_cites: int = 0
    num_ecites: int = 0
    skipped: int = 0
    bad_fields: Counter = field(default_factory=Counter)

    def process(self, p: Path) -> None:
        self.total += 1
        if not p.exists():
            return
        self.local += 1
        test = FileCase(p)
        self.num_cites += test.num_cites
        self.num_ecites += test.num_ecites
        self.bad_fields += test.bad_fields
        if test.article_type in SKIP_ARTICLE_TYPES:
            self.skipped += 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PubMed Central Data Probe")
    parser.add_argument("pmcpath", type=Path, help="path to PMC S3 data dump")
    args = parser.parse_args()
    index = FastIndex(args.pmcpath)

    journals = dict()
    already = set()
    for cat in ['reject', 'mixed', 'unmixed']:
        journals[cat] = index.load_strs(f"{cat}_journals.txt")
        already |= journals[cat]
    missing = set()
    
    tally: dict[str, Tally] = dict()
    for e in index.entries:
        if e.journal_id in already:
            continue
        jt = tally.setdefault(e.journal_id, Tally())
        p = index.path(e)
        if p.exists():
            jt.process(p)
        else:
            missing.add(p)

    for j, jt in tally.items():
        if not REJECT_FIELDS.isdisjoint(jt.bad_fields.keys()):
            journals['reject'].add(j)
        elif jt.num_cites > 10:
            if jt.num_ecites / jt.num_cites < 0.5:
                journals['mixed'].add(j)
            elif jt.num_ecites == jt.num_cites:
                journals['unmixed'].add(j)

    for cat, v in journals.items():
        fn = f"{cat}_journals.txt"
        index.save_strs(fn, v)
        print(fn, "saved.")
    fn = 'missing_files.txt'
    index.save_strs(fn, missing)
    print(fn, "saved.")
