from pathlib import Path

from lxml.html import builder as E
from lxml.html import tostring
from lxml import etree

import epijats.baseprint as _
from epijats import html


SNAPSHOT_CASE = Path(__file__).parent / "cases" / "snapshot"

GEN = html.HtmlGenerator()


def test_minimal():
    issues = []
    got = _.BaseprintBuilder(issues.append).build(SNAPSHOT_CASE / "baseprint")
    assert not issues
    assert [_.Author("Wang")] == got.authors
    expect = _.Abstract([_.ElementContent('A simple test.', [])])
    assert expect == got.abstract


def test_minimal_html_title():
    bp = _.parse_baseprint(SNAPSHOT_CASE / "baseprint")
    expect = tostring(E.TITLE('A test'))
    assert expect == tostring(E.TITLE(*GEN.content(bp.title)))


def test_article_title():
    bp = _.parse_baseprint(SNAPSHOT_CASE / "PMC11003838.xml")
    expect = b"""<title>Shedding Light on Data Monitoring Committee Charters on <a href="http://clinicaltrials.gov">ClinicalTrials.gov</a></title>"""
    assert expect == tostring(E.TITLE(*GEN.content(bp.title)))


def xml2html(xml, tagmap = {}):
    et = etree.fromstring(xml)
    issues = []
    out = _.ElementContent("", [])
    par = _.RichTextParser(issues.append, tagmap)
    par.parse_content(et, out)
    return (html.html_to_str(*GEN.content(out)), len(issues))


def test_simple_xml_parse():
    xml = """<r>Foo<c>bar</c>baz</r>"""
    assert ("Foobarbaz", 1) == xml2html(xml)
    assert ("Foo<d>bar</d>baz", 0) == xml2html(xml, {'c': 'd'})


def test_ext_link_xml_parse():
    xml = ("""<r xmlns:xlink="http://www.w3.org/1999/xlink">"""
         + """Foo<ext-link xlink:href="http://x.es">bar</ext-link>baz</r>""")
    assert ("Foobarbaz", 1) == xml2html(xml)
    expect = 'Foo<a href="http://x.es">bar</a>baz'
    assert (expect, 0) == xml2html(xml, {'ext-link': 'a'})
