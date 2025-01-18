from pathlib import Path

from lxml.html import builder as E
from lxml.html import tostring
from lxml import etree

import epijats.parse as _
from epijats import html
from epijats.baseprint import Baseprint
from epijats.reformat import baseprint_to_xml


SNAPSHOT_CASE = Path(__file__).parent / "cases" / "snapshot"
ROUNDTRIP_CASE = Path(__file__).parent / "cases" / "roundtrip"

GEN = html.HtmlGenerator()
XML = etree.XMLParser(remove_comments=True, load_dtd=False)


def assert_bdom_roundtrip(expect: Baseprint):
    dump = etree.tostring(baseprint_to_xml(expect))
    root = etree.fromstring(dump, parser=XML)
    assert _.parse_baseprint_root(root) == expect


def test_minimal():
    issues = []
    got = _.BaseprintParser(issues.append).parse(SNAPSHOT_CASE / "baseprint")
    assert not issues
    assert [_.Author("Wang")] == got.authors
    expect = _.Abstract([_.ElementContent('A simple test.', [])])
    assert expect == got.abstract
    assert_bdom_roundtrip(got)

def test_roundtrip():
    xml_path = ROUNDTRIP_CASE / "minimal" / "article.xml"
    with open(xml_path, "r") as f:
        expect = f.read()
    issues = []
    bp = _.BaseprintParser(issues.append).parse(xml_path)
    assert not issues
    assert etree.tostring(baseprint_to_xml(bp)).decode() == expect


def test_minimal_html_title():
    bp = _.parse_baseprint(SNAPSHOT_CASE / "baseprint")
    expect = tostring(E.TITLE('A test'))
    assert tostring(E.TITLE(*GEN.content(bp.title))) == expect


def test_article_title():
    bp = _.parse_baseprint(SNAPSHOT_CASE / "PMC11003838.xml")
    expect = b"""<title>Shedding Light on Data Monitoring Committee Charters on <a href="http://clinicaltrials.gov">ClinicalTrials.gov</a></title>"""
    assert tostring(E.TITLE(*GEN.content(bp.title))) == expect
    assert_bdom_roundtrip(bp)


def xml2html(xml, tagmap = {}, hypertext=False):
    et = etree.fromstring(xml)
    issues = []
    model = _.hypertext_model(tagmap) if hypertext else _.text_model(tagmap)
    out = _.parse_text_content(issues.append, et, model)
    return (html.html_to_str(*GEN.content(out)), len(issues))


def test_simple_xml_parse():
    xml = """<r>Foo<c>bar</c>baz</r>"""
    assert xml2html(xml) == ("Foobarbaz", 1) 
    assert  xml2html(xml, {'c': 'd'}) == ("Foo<d>bar</d>baz", 0)


def test_ext_link_xml_parse():
    xml = ("""<r xmlns:xlink="http://www.w3.org/1999/xlink">"""
         + """Foo<ext-link xlink:href="http://x.es">bar</ext-link>baz</r>""")
    assert xml2html(xml) == ("Foobarbaz", 1)
    expect = 'Foo<a href="http://x.es">bar</a>baz'
    assert xml2html(xml, {'ext-link': 'a'}, True) == (expect, 0) 
