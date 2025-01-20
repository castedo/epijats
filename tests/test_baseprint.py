from pathlib import Path

from lxml.html import builder as E
from lxml.html import tostring
from lxml import etree

import epijats.parse as _
from epijats import html
from epijats.baseprint import Baseprint, List
from epijats.reformat import baseprint_to_xml, sub_element


SNAPSHOT_CASE = Path(__file__).parent / "cases" / "snapshot"
ROUNDTRIP_CASE = Path(__file__).parent / "cases" / "roundtrip"

GEN = html.HtmlGenerator()
XML = etree.XMLParser(remove_comments=True, load_dtd=False)
NSMAP = {
    'ali': "http://www.niso.org/schemas/ali/1.0",
    'mml': "http://www.w3.org/1998/Math/MathML",
    'xlink': "http://www.w3.org/1999/xlink",
}


def wrap_xml(content: str):
    attribs = ['xmlns:{}="{}"'.format(k, v) for k, v in NSMAP.items()]
    return ("<root {}>{}</root>\n".format(" ".join(attribs), content))


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
    model = _.UnionModel([])
    model += _.TextElementModel(tagmap, model)
    if hypertext:
        model += _.ExtLinkModel(model)
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
    assert xml2html(xml, {}, True) == (expect, 0) 


def test_nested_ext_link_xml_parse():
    xml = wrap_xml('Foo<ext-link xlink:href="https://x.es">bar<b>baz</b>boo</ext-link>foo')
    assert xml2html(xml, {'b': 'b'}, True) == ('Foo<a href="https://x.es">bar<b>baz</b>boo</a>foo', 0)
    xml = wrap_xml('Foo<b><ext-link xlink:href="https://x.es">bar</ext-link>baz</b>boo')
    assert xml2html(xml, {'b': 'b'}, True) == ('Foo<b><a href="https://x.es">bar</a>baz</b>boo', 0)
    xml = wrap_xml('Foo<ext-link xlink:href="https://x.es">'
        + '<ext-link xlink:href="https://y.es">bar</ext-link>baz</ext-link>boo')
    assert xml2html(xml, {}, True) == ('Foo<a href="https://x.es">barbaz</a>boo', 2)
    xml = wrap_xml('<ext-link>Foo<ext-link xlink:href="https://y.es">bar</ext-link>baz</ext-link>boo')
    assert xml2html(xml, {}, True) == ('Foo<a href="https://y.es">bar</a>bazboo', 2)


def xml_to_root_str(e: etree._Element) -> str:
    root = etree.Element("root", nsmap=NSMAP)
    root.text = "\n"
    root.append(e)
    root.tail = "\n"
    return etree.tostring(root).decode()


def wrap_to_xml(root_wrap: str) -> etree._Element:
    root = etree.fromstring(root_wrap, parser=XML)
    assert root.tag == 'root'
    return root[0]


def test_list_rountrip():
    dump = wrap_xml("""
<list list-type="bullet">
<list-item>
<p>Def <italic>time</italic>.</p>
</list-item>
<list-item>
<p>Foo
bar.</p>
</list-item>
<list-item>
<p>Baz</p>
</list-item>
</list>
""")
    issues = []
    model = _.ListModel(_.TextElementModel(_.FAIRLY_RICH_TEXT_TAGS))
    subel = model.parse(issues.append, wrap_to_xml(dump))
    assert isinstance(subel, List)
    assert len(subel.items) == 3
    assert xml_to_root_str(sub_element(subel)) == dump
