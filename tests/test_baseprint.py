from pathlib import Path

from lxml.html import builder as E
from lxml.html import tostring
from lxml import etree

import epijats.parse as _
from epijats import html
from epijats.baseprint import Baseprint, List
from epijats.reformat import abstract, baseprint_to_xml, sub_element
from epijats import condition as fc


SNAPSHOT_CASE = Path(__file__).parent / "cases" / "snapshot"
ROUNDTRIP_CASE = Path(__file__).parent / "cases" / "roundtrip"

HTML = html.HtmlGenerator()
NSMAP = {
    'ali': "http://www.niso.org/schemas/ali/1.0",
    'mml': "http://www.w3.org/1998/Math/MathML",
    'xlink': "http://www.w3.org/1999/xlink",
}
NSMAP_STR = " ".join('xmlns:{}="{}"'.format(k, v) for k, v in NSMAP.items())


def xml_fromstring(src: str) -> etree._Element:
    parser = etree.XMLParser(remove_comments=True, load_dtd=False)
    return etree.fromstring(src, parser=parser)


def wrap_xml(content: str):
    return ("<root {}>{}</root>\n".format(NSMAP_STR, content))


def assert_bdom_roundtrip(expect: Baseprint):
    dump = etree.tostring(baseprint_to_xml(expect))
    root = xml_fromstring(dump)
    assert _.parse_baseprint_root(root) == expect


def test_minimalish():
    issues = []
    got = _.BaseprintParser(issues.append).parse(SNAPSHOT_CASE / "baseprint")
    assert not issues
    assert got.authors == [_.Author("Wang")]
    paragraph = _.SubElement('A simple test.', [], 'p', 'p', "")
    expect = _.Abstract()
    expect.presection.append(paragraph)
    assert got.abstract == expect
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
    assert tostring(E.TITLE(*HTML.content(bp.title))) == expect


def test_article_title():
    bp = _.parse_baseprint(SNAPSHOT_CASE / "PMC11003838.xml")
    expect = b"""<title>Shedding Light on Data Monitoring Committee Charters on <a href="http://clinicaltrials.gov">ClinicalTrials.gov</a></title>"""
    assert tostring(E.TITLE(*HTML.content(bp.title))) == expect
    assert_bdom_roundtrip(bp)


def xml2html(xml):
    et = etree.fromstring(xml)
    issues = []
    model = _.base_hypertext_model()
    out = _.parse_text_content(issues.append, et, model)
    return (html.html_to_str(*HTML.content(out)), len(issues))


def test_simple_xml_parse():
    xml = """<r>Foo<c>bar</c>baz</r>"""
    assert xml2html(xml) == ("Foobarbaz", 1) 
    xml = """<r>Foo<bold>bar</bold>baz</r>"""
    assert  xml2html(xml) == ("Foo<strong>bar</strong>baz", 0)


def test_ext_link_xml_parse():
    xml = ("""<r xmlns:xlink="http://www.w3.org/1999/xlink">"""
         + """Foo<ext-link xlink:href="http://x.es">bar</ext-link>baz</r>""")
    expect = 'Foo<a href="http://x.es">bar</a>baz'
    assert xml2html(xml) == (expect, 0) 


def test_nested_ext_link_xml_parse():
    xml = wrap_xml('Foo<ext-link xlink:href="https://x.es">bar<sup>baz</sup>boo</ext-link>foo')
    assert xml2html(xml) == ('Foo<a href="https://x.es">bar<sup>baz</sup>boo</a>foo', 0)
    xml = wrap_xml('Foo<sup><ext-link xlink:href="https://x.es">bar</ext-link>baz</sup>boo')
    assert xml2html(xml) == ('Foo<sup><a href="https://x.es">bar</a>baz</sup>boo', 0)
    xml = wrap_xml('Foo<ext-link xlink:href="https://x.es">'
        + '<ext-link xlink:href="https://y.es">bar</ext-link>baz</ext-link>boo')
    assert xml2html(xml) == ('Foo<a href="https://x.es">barbaz</a>boo', 1)
    xml = wrap_xml('<ext-link>Foo<ext-link xlink:href="https://y.es">bar</ext-link>baz</ext-link>boo')
    assert xml2html(xml) == ('Foo<a href="https://y.es">bar</a>bazboo', 2)


def xml_to_root_str(e: etree._Element) -> str:
    root = etree.Element("root", nsmap=NSMAP)
    root.text = "\n"
    root.append(e)
    root.tail = "\n"
    return etree.tostring(root).decode()


def wrap_to_xml(root_wrap: str) -> etree._Element:
    root = xml_fromstring(root_wrap)
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
    model = _.ListModel(_.TextElementModel({'p': 'p'}, _.base_hypertext_model()))
    subel = model.parse(issues.append, wrap_to_xml(dump))
    assert isinstance(subel, List)
    assert len(subel.items) == 3
    assert xml_to_root_str(sub_element(subel)) == dump


def test_abstract_restyle():
    dump = wrap_xml("""
<abstract>
<p>OK</p>
<list list-type="bullet"><list-item><p>Restyle!</p></list-item></list>
<p>OK</p>
</abstract>
""")
    issues = []
    dest = _.Abstract()
    parser = _.ProtoSectionParser(issues.append, dest, _.p_elements_model())
    parser.parse_element(wrap_to_xml(dump))
    restyled = wrap_xml("""
<abstract>
<p>OK</p>
<p>
<list list-type="bullet">
<list-item>
<p>Restyle!</p>
</list-item>
</list>
</p>
<p>OK</p>
</abstract>
""")
    assert xml_to_root_str(abstract(dest)) == restyled
    expect = """<p>OK</p>
<p>
<ul>
<li>
<p>Restyle!</p>
</li>
</ul>
</p>
<p>OK</p>"""
    assert html.html_to_str(*HTML.abstract(dest)) == expect


def test_minimal_with_issues():
    issues = set()
    bp = _.parse_baseprint_root(xml_fromstring("<article/>"), issues.add)
    print(issues)
    assert bp == Baseprint()
    assert len(issues) == 4
    assert set(i.condition for i in issues) == { 
        fc.MissingContent('article-title', 'title-group'),
        fc.MissingContent('contrib', 'contrib-group'),
        fc.MissingContent('abstract', 'article-meta'),
        fc.MissingContent('body', 'article'),
    }
    expect = f"""\
<article {NSMAP_STR}>
  <front>
    <article-meta>
      <title-group>
        <article-title></article-title>
      </title-group>
      <contrib-group>
      </contrib-group>
      <abstract>
      </abstract>
    </article-meta>
  </front>
  <body>
  </body>
</article>
"""
    assert etree.tostring(baseprint_to_xml(bp)).decode() == expect
