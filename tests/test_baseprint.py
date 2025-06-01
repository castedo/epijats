import os, pytest
from pathlib import Path
from typing import Tuple

from lxml import etree

import epijats.parse.jats as _
from epijats import html
from epijats import baseprint as bp
from epijats.baseprint import Abstract, Baseprint, List
from epijats import condition as fc
from epijats import restyle
from epijats.parse import parse_baseprint, parse_baseprint_root
from epijats.tree import Element, make_paragraph
from epijats.xml import xml_element


TEST_CASES = Path(__file__).parent / "cases"
SNAPSHOT_CASE = Path(__file__).parent / "cases" / "snapshot"
ROUNDTRIP_CASE = Path(__file__).parent / "cases" / "roundtrip"

HTML = html.HtmlGenerator()
NSMAP = {
    'ali': "http://www.niso.org/schemas/ali/1.0/",
    'mml': "http://www.w3.org/1998/Math/MathML",
    'xlink': "http://www.w3.org/1999/xlink",
}
NSMAP_STR = " ".join('xmlns:{}="{}"'.format(k, v) for k, v in NSMAP.items())


def assert_eq_if_exists(got: str, expect: Path):
    if expect.exists():
        with open(expect, "r") as f:
            assert got == f.read()


def str_from_lxml_element(e: etree._Element) -> str:
    root = etree.Element("root", nsmap=NSMAP)
    root.append(e)
    return etree.tostring(e, method="c14n", exclusive=True).decode()


def root_wrap(content: str):
    return ("<root {}>{}</root>\n".format(NSMAP_STR, content))


def lxml_root_from_str(src: str) -> etree._Element:
    parser = etree.XMLParser(remove_comments=True, load_dtd=False)
    return etree.fromstring(src, parser=parser)


def lxml_element_from_str(s: str) -> etree._Element:
    root = lxml_root_from_str(root_wrap(s.strip()))
    assert not root.text
    assert len(root) == 1
    return root[0]


def str_from_element(ele: Element) -> str:
    return str_from_lxml_element(xml_element(ele))


def assert_bdom_roundtrip(expect: Baseprint):
    xe = xml_element(restyle.article(expect))
    dump = etree.tostring(xe).decode()
    root = lxml_root_from_str(dump)
    assert parse_baseprint_root(root) == expect


def parse_abstract(e: etree._Element) -> Tuple[Abstract, list[fc.FormatIssue]]:
    issues: list[fc.FormatIssue] = []
    ret = Abstract()
    binder = _.proto_section_binder('abstract', _.p_elements_model())
    p = binder.bind(issues.append, ret)
    p.parse_element(e)
    return (ret, issues)


def test_minimalish():
    issues = []
    got = parse_baseprint(SNAPSHOT_CASE / "baseprint", issues.append)
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
        expect = f.read().rstrip()
    issues = []
    bp = parse_baseprint(xml_path, issues.append)
    assert bp is not None, issues
    xe = xml_element(restyle.article(bp))
    assert etree.tostring(xe, encoding="unicode") == expect
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
    body = HTML.html_body_content(bp)
    assert_eq_if_exists(body, case_path / "body.html")


def test_minimal_html_title():
    bp = parse_baseprint(SNAPSHOT_CASE / "baseprint")
    assert HTML.content_to_str(bp.title) == 'A test'


def test_article_title():
    bp = parse_baseprint(SNAPSHOT_CASE / "PMC11003838.xml")
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
    xml = root_wrap('Foo<ext-link xlink:href="https://x.es">bar<sup>baz</sup>boo</ext-link>foo')
    assert xml2html(xml) == ('Foo<a href="https://x.es">bar<sup>baz</sup>boo</a>foo', 0)
    xml = root_wrap('Foo<sup><ext-link xlink:href="https://x.es">bar</ext-link>baz</sup>boo')
    assert xml2html(xml) == ('Foo<sup><a href="https://x.es">bar</a>baz</sup>boo', 0)
    xml = root_wrap('Foo<ext-link xlink:href="https://x.es">'
        + '<ext-link xlink:href="https://y.es">bar</ext-link>baz</ext-link>boo')
    assert xml2html(xml) == ('Foo<a href="https://x.es">barbaz</a>boo', 1)
    xml = root_wrap('<ext-link>Foo<ext-link xlink:href="https://y.es">bar</ext-link>baz</ext-link>boo')
    assert xml2html(xml) == ('Foo<a href="https://y.es">bar</a>bazboo', 2)


def test_list_rountrip():
    expect = """\
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
</list>"""
    issues = []
    model = _.ListModel(_.p_elements_model())
    subel = model.load(issues.append, lxml_element_from_str(expect))
    assert isinstance(subel, List)
    assert len(list(subel)) == 3
    assert str_from_element(subel) == expect


def test_list_ordered_rountrip():
    expect = """\
<list list-type="order">
  <list-item>
    <p>Def <italic>time</italic>.</p>
  </list-item>
  <list-item>
    <p>Foo
bar.</p>
  </list-item>
</list>"""
    issues = []
    model = _.ListModel(_.p_elements_model())
    subel = model.load(issues.append, lxml_element_from_str(expect))
    assert isinstance(subel, List)
    assert len(list(subel)) == 2
    assert str_from_element(subel) == expect


def test_def_list_rountrip():
    expect = """\
<def-list>
  <def-item>
    <term>Base DSI of this specification:</term>
    <def>
      <p><monospace>1wFGhvmv8XZfPx0O5Hya2e9AyXo</monospace></p>
    </def>
  </def-item>
  <def-item>
    <term>DSI of the first edition:</term>
    <def>
      <p><monospace>1wFGhvmv8XZfPx0O5Hya2e9AyXo/1</monospace></p>
    </def>
  </def-item>
</def-list>"""
    issues = []
    model = _.def_list_model(_.p_elements_model())
    subel = model.load(issues.append, lxml_element_from_str(expect))
    assert len(list(subel)) == 2
    assert str_from_element(subel) == expect


def mock_biblio_pool() -> _.BiblioRefPool:
    r1 = bp.BiblioRefItem()
    r1.id = "R1"
    r2 = bp.BiblioRefItem()
    r2.id = "R2"
    return _.BiblioRefPool([r1, r2])


def verify_roundtrip_citation(
    log: _.IssueCallback, start: str, expected: str,
) -> Element:
    model = _.CitationTupleModel(mock_biblio_pool())
    subel1 = model.load(log, lxml_element_from_str(start))
    assert subel1
    got = str_from_element(subel1)
    assert got == expected
    subel2 = model.load(log, lxml_element_from_str(got))
    assert subel2 == subel1
    return subel2


def test_citation_roundtrip():
    issues = []
    el = verify_roundtrip_citation(
        issues.append,
        """<sup><xref rid="R1" ref-type="bibr">1</xref></sup>""",
        """\
<sup>
  <xref ref-type="bibr" rid="R1">1</xref>
</sup>""")
    assert not issues
    assert len(list(el)) == 1


def test_citation_tuple_roundtrip():
    issues = []
    el = verify_roundtrip_citation(
        issues.append,
        """<sup><xref rid="R1" ref-type="bibr">1</xref>,<xref rid="R2" ref-type="bibr">2</xref></sup>""",
        """\
<sup>
  <xref ref-type="bibr" rid="R1">1</xref>,
  <xref ref-type="bibr" rid="R2">2</xref>
</sup>""")
    assert not issues
    assert len(list(el)) == 2


def test_bare_citation():
    issues = []
    model = _.AutoCorrectCitationModel(mock_biblio_pool())
    start = """<xref rid="R1" ref-type="bibr">1</xref>"""
    el = model.load(issues.append, lxml_element_from_str(start))
    assert not issues
    assert el
    assert len(list(el)) == 1
    expect = """\
<sup>
  <xref ref-type="bibr" rid="R1">1</xref>
</sup>"""
    assert str_from_element(el) == expect


def test_author_restyle():
    expect = """\
<contrib-group>
  <contrib contrib-type="author">
    <contrib-id contrib-id-type="orcid">https://orcid.org/0000-0002-5014-4809</contrib-id>
    <name>
      <surname>Ellerman</surname>
      <given-names>E. Castedo</given-names>
    </name>
    <email>castedo@castedo.com</email>
  </contrib>
</contrib-group>"""
    issues = []
    authors = _.load_author_group(issues.append, lxml_element_from_str(expect))
    assert authors is not None
    assert len(issues) == 0
    ele = restyle.contrib_group(authors)
    assert str_from_element(ele) == expect


def test_abstract_restyle():
    bad_style = """\
<abstract>
    <p>OK</p>
                <list list-type="bullet">
        <list-item>
            <p>Restyle!</p>
        </list-item>
    </list>
                <p>OK</p>
</abstract>"""
    (bdom, _) = parse_abstract(lxml_element_from_str(bad_style))
    restyled = """\
<abstract>
  <p>OK</p>
  <p><list list-type="bullet">
      <list-item>
        <p>Restyle!</p>
      </list-item>
    </list></p>
  <p>OK</p>
</abstract>"""
    xe = xml_element(restyle.abstract(bdom))
    assert str_from_lxml_element(xe) == restyled

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


def test_restyle():
    case_dir = TEST_CASES / "restyle"
    issues = []
    bp = parse_baseprint(case_dir / "orig/", issues.append)
    assert bp is not None, issues
    with open(case_dir / "expect/article.xml", "r") as f:
        expect = f.read().rstrip()
    xe = xml_element(restyle.article(bp))
    assert etree.tostring(xe).decode() == expect
    assert {i.condition for i in issues} == {
        fc.InvalidDoi('pub-id', 'element-citation'),
        fc.InvalidPmid('pub-id', 'element-citation'),
        fc.UnsupportedAttribute('element-citation', 'publication-type'),
    }


def test_minimal_with_issues():
    issues = set()
    bp = parse_baseprint_root(lxml_root_from_str("<article/>"), issues.add)
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
</article>"""
    xe = xml_element(restyle.article(bp))
    assert etree.tostring(xe).decode() == expect


def test_no_issues():
    issues = []
    got = parse_baseprint(SNAPSHOT_CASE / "whybaseprint", issues.append)
    assert not issues
