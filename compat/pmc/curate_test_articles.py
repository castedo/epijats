#!/usr/bin/python3

import argparse
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from pprint import pp, pprint
from sys import stdout

from lxml import etree

from epijats import condition as fc
from epijats.parse import parse_baseprint_root

from fastindex import FastIndex


XML = etree.XMLParser(remove_comments=True, load_dtd=False)


IGNORE_CLASS = (
  fc.ProcessingInstruction,
  fc.UnsupportedAttribute,  # for now
)

IGNORE = {
  fc.MissingContent(tag='abstract', parent='article-meta'),
  fc.UnsupportedElement(tag='article-categories', parent='article-meta'),
  fc.UnsupportedElement(tag='article-id', parent='article-meta'),
  fc.UnsupportedElement(tag='author-notes', parent='article-meta'),
  fc.UnsupportedElement(tag='copyright-holder', parent='permissions'),
  fc.UnsupportedElement(tag='copyright-year', parent='permissions'),
  fc.UnsupportedElement(tag='counts', parent='article-meta'),
  fc.UnsupportedElement(tag='custom-meta-group', parent='article-meta'),
  fc.UnsupportedElement(tag='elocation-id', parent='article-meta'),
  fc.UnsupportedElement(tag='ext-link', parent='comment'),
  fc.UnsupportedElement(tag='ext-link', parent='element-citation'),
  fc.UnsupportedElement(tag='fpage', parent='article-meta'),
  fc.UnsupportedElement(tag='funding-group', parent='article-meta'),
  fc.UnsupportedElement(tag='history', parent='article-meta'),
  fc.UnsupportedElement(tag='hr', parent='th'),
  fc.UnsupportedElement(tag='issue', parent='article-meta'),
  fc.UnsupportedElement(tag='journal-meta', parent='front'),
  fc.UnsupportedElement(tag='kwd-group', parent='article-meta'),
  fc.UnsupportedElement(tag='label', parent='ref'),
  fc.UnsupportedElement(tag='lpage', parent='article-meta'),
  fc.UnsupportedElement(tag='processing-meta', parent='article'),
  fc.UnsupportedElement(tag='pub-date', parent='article-meta'),
  fc.UnsupportedElement(tag='related-article', parent='article-meta'),
  fc.UnsupportedElement(tag='self-uri', parent='article-meta'),
  fc.UnsupportedElement(tag='volume', parent='article-meta'),
}

PENALTY = {
  1: {
    fc.ExcessElement(tag='comment', parent='element-citation'),
    fc.IgnoredText(tag='date-in-citation', parent='element-citation'),
    fc.InvalidInteger(tag='month', parent='element-citation'),
    fc.MissingContent(tag='body', parent='article'),
    fc.UnsupportedElement(tag='address', parent='contrib'),
    fc.UnsupportedElement(tag='aff', parent='contrib-group'),
    fc.UnsupportedElement(tag='conf-loc', parent='element-citation'),
    fc.UnsupportedElement(tag='degrees', parent='contrib'),
    fc.UnsupportedElement(tag='italic', parent='comment'),
    fc.UnsupportedElement(tag='role', parent='contrib'),
    fc.UnsupportedElement(tag='size', parent='element-citation'),
    fc.UnsupportedElement(tag='sup', parent='article-title'),
    fc.UnsupportedElement(tag='sup', parent='source'),
    fc.UnsupportedElement(tag='supplement', parent='element-citation'),
    fc.UnsupportedElement(tag='title', parent='abstract'),
    fc.UnsupportedElement(tag='uri', parent='license-p'),
    fc.UnsupportedElement(tag='xref', parent='contrib'),
  },
  10: {
    fc.ExcessElement(tag='contrib-group', parent='article-meta'),
    fc.UnsupportedElement(tag='ack', parent='back'),
    fc.UnsupportedElement(tag='aff', parent='article-meta'),
    fc.UnsupportedElement(tag='collab', parent='element-citation'),
    fc.UnsupportedElement(tag='collab', parent='person-group'),
    fc.UnsupportedElement(tag='part-title', parent='element-citation'),
    fc.UnsupportedElement(tag='sc', parent='p'),
    fc.UnsupportedElement(tag='table-wrap-foot', parent='table-wrap'),
  },
  100: {
    fc.UnsupportedElement(tag='caption', parent='fig'),
    fc.UnsupportedElement(tag='fig', parent='body'),
    fc.UnsupportedElement(tag='fig', parent='sec'),
    fc.UnsupportedElement(tag='fn-group', parent='back'),
    fc.UnsupportedElement(tag='graphic', parent='fig'),
    fc.UnsupportedElement(tag='graphic', parent='p'),
    fc.UnsupportedElement(tag='inline-graphic', parent='alternatives'),
    fc.UnsupportedElement(tag='label', parent='fig'),
  },
  1000: {
    fc.ExcessElement(tag='abstract', parent='article-meta'),
    fc.UnsupportedAttributeValue(tag="xref", attribute="ref-type", value="bibr"),
    fc.UnsupportedElement(tag='bio', parent='back'),
    fc.UnsupportedElement(tag='boxed-text', parent='sec'),
    fc.UnsupportedElement(tag='citation-alternatives', parent='ref'),
    fc.UnsupportedElement(tag='glossary', parent='back'),
    fc.UnsupportedElement(tag='inline-supplementary-material', parent='p'),
    fc.UnsupportedElement(tag='mixed-citation', parent='ref'),
    fc.UnsupportedElement(tag='notes', parent='back'),
    fc.UnsupportedElement(tag='sec', parent='back'),
    fc.UnsupportedElement(tag='supplementary-material', parent='p'),
    fc.UnsupportedElement(tag='supplementary-material', parent='sec'),
    fc.UnsupportedElement(tag='trans-abstract', parent='article-meta'),
    fc.UnsupportedElement(tag='trans-source', parent='element-citation'),
    fc.UnsupportedElement(tag='trans-title', parent='element-citation'),
    fc.UnsupportedElement(tag='trans-title-group', parent='title-group'),
  }
}


def get_penalty(c: fc.FormatCondition) -> int:
    ret = -1
    for num, conditions in PENALTY.items():
        if c in conditions and num > ret:
            ret = num
    if ret == -1:
        ret = 10 # unknown condition
    return ret


@dataclass
class TestCase:
    path: Path
    penalty: int = 0
    mathml: bool = False
    conditions: set = field(default_factory=set)
    tbd: set = field(default_factory=set)

    def __post_init__(self):
        xml_parser = etree.XMLParser(remove_comments=True, remove_pis=True)
        et = etree.parse(self.path, parser=xml_parser)
        self.root = et.getroot()
        self.article_type = self.root.get('article-type', '')
        self.jid = self.root.findtext('front/journal-meta/journal-id')

    def handle_issue(self, issue: fc.FormatIssue):
        c = issue.condition
        if isinstance(c, IGNORE_CLASS) or c in IGNORE:
            return
        self.conditions.add(c)

    def parse(self):
        parse_baseprint_root(self.root, self.handle_issue)
        for c in self.conditions:
            assert isinstance(c.tag, str)
            if c.tag.startswith('{http://www.w3.org/1998/Math/MathML}'):
                self.mathml = True
            penalty = get_penalty(c)
            self.penalty += penalty
            if penalty >= 1:
                self.tbd.add(c)


class Tally:
    count = Counter()
    penalty_dist = Counter()
    type_count = Counter()
    jid_count = Counter()
    forgo_jid_count = Counter()
    mathml_jid_count = Counter()

    def test_article(self, fp: Path) -> None:
        if not fp.exists():
            # print(fp)
            self.count.update(['NOTFOUND'])
            return
        t = TestCase(fp)
        if t.article_type in ['correction', 'retraction', 'news', 'abstract']:
            self.count.update(['SKIPPED'])
            return
#        print(t.path)
        t.parse()
        if t.penalty >= 1000:
            self.count.update(['FORGO'])
            self.forgo_jid_count.update([t.jid])
            return
        if t.mathml:
            self.count.update(['MATHML'])
            self.mathml_jid_count.update([t.jid])
            return
        self.type_count.update([t.article_type])
        self.jid_count.update([t.jid])
        self.penalty_dist.update([t.penalty if t.penalty < 100 else 100])
        if t.penalty < 100:
            pp({
                'path': str(t.path),
                'type': t.article_type,
                'penalty': t.penalty,
                'tbd': t.tbd,
            }, width=88)
        self.count.update(['TBD'])

    def print(self) -> None:
        stdout.write("\nArticles: ")
        pprint(self.count)
        print("Forgone article journal distribution:")
        pprint(self.forgo_jid_count)
        print("MathML article journal distribution:")
        pprint(self.mathml_jid_count)
        print("TBD article type distribution:")
        pprint(self.type_count)
        print("TBD article journal distribution:")
        pprint(self.jid_count)
        print("TBD article penalty distribution (truncated):")
        pprint(dict(self.penalty_dist))


JUMP = 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PubMed Central Data Probe")
    parser.add_argument("pmcpath", type=Path, help="path to PMC S3 data dump")
    args = parser.parse_args()
    index = FastIndex(args.pmcpath)
    paths = list(index.journal_list_paths('journal_list.txt'))
    tally = Tally()
    print()
    for p in paths[::JUMP]:
        tally.test_article(p)
    tally.print()
