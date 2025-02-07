import os, pytest
from pathlib import Path
from typing import Tuple

from lxml import etree

import epijats.parse as _
from epijats import html
from epijats import baseprint as bp
from epijats.baseprint import Abstract, Baseprint, List
from epijats import condition as fc
from epijats import restyle
from epijats.parse import parse_baseprint
from epijats.tree import make_paragraph
from epijats.xml import xml_element


SNAPSHOT_CASE = Path(__file__).parent / "cases" / "snapshot"
ROUNDTRIP_CASE = Path(__file__).parent / "cases" / "roundtrip"

HTML = html.HtmlGenerator()
NSMAP = {
    'ali': "http://www.niso.org/schemas/ali/1.0",
    'mml': "http://www.w3.org/1998/Math/MathML",
    'xlink': "http://www.w3.org/1999/xlink",
}
NSMAP_STR = " ".join('xmlns:{}="{}"'.format(k, v) for k, v in NSMAP.items())


def assert_eq_if_exists(got: str, expect: Path):
    if expect.exists():
        with open(expect, "r") as f:
            assert got == f.read()


def xml_sub_element(src) -> etree._Element:
    ret = xml_element(src)
    ret.tail = "\n"
    return ret


def xml_fromstring(src: str) -> etree._Element:
    parser = etree.XMLParser(remove_comments=True, load_dtd=False)
    return etree.fromstring(src, parser=parser)


def wrap_xml(content: str):
    return ("<root {}>{}</root>\n".format(NSMAP_STR, content))


def assert_bdom_roundtrip(expect: Baseprint):
    xe = xml_sub_element(restyle.article(expect))
    dump = etree.tostring(xe).decode()
    root = xml_fromstring(dump)
    assert _.parse_baseprint_root(root) == expect


def parse_abstract(e: etree._Element) -> Tuple[Abstract, list[fc.FormatIssue]]:
    issues: list[fc.FormatIssue] = []
    ret = Abstract()
    parser = _.ProtoSectionParser(issues.append, ret, _.p_elements_model(), 'abstract')
    parser.parse_element(e)
    return (ret, issues)


def test_minimalish():
    issues = []
    got = _.parse_baseprint(SNAPSHOT_CASE / "baseprint", issues.append)
    assert not issues
    assert got.authors == [bp.Author(bp.PersonName("Wang"))]
    expect = Abstract()
    expect.presection.append(make_paragraph('A simple test.'))
    assert got.abstract == expect
    assert_bdom_roundtrip(got)


@pytest.mark.parametrize("case", os.listdir(ROUNDTRIP_CASE))
def test_roundtrip(case):
    xml_path = ROUNDTRIP_CASE / case / "article.xml"
    with open(xml_path, "r") as f:
        expect = f.read()
    issues = []
    bp = _.parse_baseprint(xml_path, issues.append)
    assert bp is not None, issues
    xe = xml_sub_element(restyle.article(bp))
    assert etree.tostring(xe).decode() == expect
    assert not issues


@pytest.mark.parametrize("case", os.listdir(ROUNDTRIP_CASE))
def test_html(case):
    case_path = ROUNDTRIP_CASE / case
    issues = []
    bp = parse_baseprint(case_path / "article.xml", issues.append)
    assert bp
    title = HTML.content_to_str(bp.title)
    assert_eq_if_exists(title, case_path / "title.html")
    abstract = HTML.proto_section_to_str(bp.abstract)
    assert_eq_if_exists(abstract, case_path / "abstract.html")
    body = HTML.proto_section_to_str(bp.body)
    assert_eq_if_exists(body, case_path / "body.html")


def test_minimal_html_title():
    bp = _.parse_baseprint(SNAPSHOT_CASE / "baseprint")
    assert HTML.content_to_str(bp.title) == 'A test'


def test_article_title():
    bp = _.parse_baseprint(SNAPSHOT_CASE / "PMC11003838.xml")
    expect = """Shedding Light on Data Monitoring Committee Charters on <a href="http://clinicaltrials.gov">ClinicalTrials.gov</a>"""
    assert HTML.content_to_str(bp.title) == expect
    assert_bdom_roundtrip(bp)


def xml2html(xml):
    et = etree.fromstring(xml)
    issues = []
    model = _.base_hypertext_model()
    out = _.MixedContent()
    _.parse_mixed_content(issues.append, et, model, out)
    return (HTML.content_to_str(out), len(issues))


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
    subel = model.read(issues.append, wrap_to_xml(dump))
    assert isinstance(subel, List)
    assert len(list(subel)) == 3
    xe = xml_sub_element(subel)
    assert xml_to_root_str(xe) == dump


def test_author_restyle():
    dump = wrap_xml("""
<contrib-group>
  <contrib contrib-type="author">
    <contrib-id contrib-id-type="orcid">https://orcid.org/0000-0002-5014-4809</contrib-id>
    <name>
      <surname>Ellerman</surname>
      <given-names>E. Castedo</given-names>
    </name>
    <email>castedo@castedo.com</email>
  </contrib>
</contrib-group>
""")
    issues = []
    parser = _.AuthorGroupParser(issues.append)
    assert parser.parse_element(wrap_to_xml(dump))
    assert parser.out is not None
    assert len(issues) == 0
    x = xml_sub_element(restyle.contrib_group(parser.out))
    assert xml_to_root_str(x) == dump


def test_abstract_restyle():
    bad_style = wrap_xml("""
<abstract>
    <p>OK</p>
                <list list-type="bullet">
        <list-item>
            <p>Restyle!</p>
        </list-item>
    </list>
                <p>OK</p>
</abstract>
""")
    (bdom, _) = parse_abstract(wrap_to_xml(bad_style))
    restyled = wrap_xml("""
<abstract>
  <p>OK</p>
  <p><list list-type="bullet">
      <list-item>
        <p>Restyle!</p>
      </list-item>
    </list></p>
  <p>OK</p>
</abstract>
""")
    xe = xml_sub_element(restyle.abstract(bdom))
    assert xml_to_root_str(xe) == restyled

    issues = []
    (roundtrip, issues) = parse_abstract(xe)
    assert not issues
    assert roundtrip == bdom

    expect_html = """<p>OK</p>
<p><ul>
    <li>
      <p>Restyle!</p>
    </li>
  </ul></p>
<p>OK</p>
"""
    assert HTML.proto_section_to_str(bdom) == expect_html


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
    xe = xml_sub_element(restyle.article(bp))
    assert etree.tostring(xe).decode() == expect
