import os, pytest
from pathlib import Path

from epijats.parse import kit, tree
from epijats.parse.body import CoreModels
from epijats.tree import MixedContent
from epijats.xml.format import XmlFormatter
from epijats.xml.html import HtmlGenerator

from .test_baseprint import lxml_element_from_str


def assert_not(x):
    assert not x


XML = XmlFormatter(use_lxml=False)


BLOCK_CASE = Path(__file__).parent / "cases" / "block"
P_CHILD_CASE = Path(__file__).parent / "cases" / "p_child"


def html_from_element(src: tree.Inline) -> str:
    html = HtmlGenerator()
    content = MixedContent()
    content.append(src)
    return html.content_to_str(content)


def parse_element(src: str | Path, model: kit.Model[kit.Inline]):
    if isinstance(src, Path):
        with open(src, "r") as f:
            src = f.read().strip()

    result = kit.SinkDestination[tree.Element]()
    parser = model.bound_parser(assert_not, result)

    e = lxml_element_from_str(src)
    assert isinstance(e.tag, str)
    parse_func = parser.match(e)
    assert parse_func
    assert parse_func(e)

    assert isinstance(result.out, tree.Element)
    return result.out


@pytest.mark.parametrize("case", os.listdir(BLOCK_CASE))
def test_roll_content_html(case):
    case_dir = BLOCK_CASE / case
    core = CoreModels(None)
    input_xml = case_dir / "input.xml"
    if input_xml.exists():
        block = parse_element(input_xml.read_text(), core.block)
        with open(case_dir / "expect.xml", "r") as f:
            expected_xml_str = f.read().strip()
    else:
        with open(case_dir / "xhtml.xml", "r") as f:
            expected_xml_str = f.read().strip()
        block = parse_element(expected_xml_str, core.block)

    assert XML.to_str(block) == expected_xml_str

    expect_html = case_dir / "expect.html"
    if expect_html.exists():
        with open(expect_html, "r") as f:
            expect_html_str = f.read().strip()
    else:
        expect_html_str = expected_xml_str
    html = HtmlGenerator()
    got = html.content_to_str(MixedContent([block]))
    assert html.bare_tex == case.startswith("math")
    assert got == expect_html_str


@pytest.mark.parametrize("case", os.listdir(P_CHILD_CASE))
def test_p_child_html(case):
    core = CoreModels(None)
    jats_xml = P_CHILD_CASE/ case / "jats.xml"
    if jats_xml.exists():
        p_child = parse_element(jats_xml.read_text(), core.hypertext)
        with open(P_CHILD_CASE / case / "expect.xml", "r") as f:
            expected_xml_str = f.read().strip()
    else:
        with open(P_CHILD_CASE / case / "xhtml.xml", "r") as f:
            expected_xml_str = f.read().strip()
        p_child = parse_element(expected_xml_str, core.hypertext)

    assert XML.to_str(p_child) == expected_xml_str

    expect_html = P_CHILD_CASE/ case / "expect.html"
    with open(expect_html, "r") as f:
        expect = f.read().strip()
    html = HtmlGenerator()
    got = html.content_to_str(MixedContent([p_child]))
    assert html.bare_tex == case.startswith("math")
    assert got == expect
