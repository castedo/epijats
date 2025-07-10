import os, pytest
from pathlib import Path

from epijats import condition as fc
from epijats.html import HtmlGenerator
from epijats.parse import jats, kit, tree
from epijats.tree import MixedContent
from epijats.xml import XmlFormatter

from .test_baseprint import lxml_element_from_str


XML = XmlFormatter(use_lxml=True)


P_CHILD_CASE = Path(__file__).parent / "cases" / "p_child"


def html_from_element(src: tree.Element) -> str:
    html = HtmlGenerator()
    content = MixedContent()
    content.append(src)
    return html.content_to_str(content)


def parse_element(src: str | Path, model: tree.EModel):
    if isinstance(src, Path):
        with open(src, "r") as f:
            src = f.read().strip()

    issues: list[fc.FormatIssue] = []
    result = kit.Result[tree.Element]()
    parser = model.once().bind(issues.append, result)

    e = lxml_element_from_str(src)
    assert isinstance(e.tag, str)
    parse_func = parser.match(e.tag, e.attrib)
    assert parse_func
    assert parse_func(e)

    assert not issues
    assert isinstance(result.out, tree.Element)
    return result.out


@pytest.mark.parametrize("case", os.listdir(P_CHILD_CASE))
def test_p_child_html(case):
    with open(P_CHILD_CASE/ case / "jats.xml", "r") as f:
        xml_str = f.read().strip()
    p_child = parse_element(xml_str, jats.p_child_model())

    expect_xml = P_CHILD_CASE/ case / "expect.xml"
    if expect_xml.exists():
        with open(expect_xml, "r") as f:
            xml_str = f.read().strip()

    assert XML.to_str(p_child) == xml_str

    expect_html = P_CHILD_CASE/ case / "expect.html"
    with open(expect_html, "r") as f:
        expect = f.read().strip()
    html = HtmlGenerator()
    got = html.content_to_str(MixedContent([p_child]))
    assert html.bare_tex == case.startswith("math")
    assert got == expect
