import os, pytest
from pathlib import Path

from epijats import dom
from epijats.parse import kit, tree
from epijats.parse.body import CoreModels
from epijats.tree import MutableMixedContent
from epijats.xml.format import XmlFormatter
from epijats.xml.html import HtmlGenerator

from . import util

from .test_baseprint import lxml_element_from_str


def assert_not(x):
    assert not x


XML = XmlFormatter(use_lxml=False)


BLOCK_CASE = Path(__file__).parent / "cases" / "block"
P_CHILD_CASE = Path(__file__).parent / "cases" / "p_child"


def html_from_element(src: dom.Element) -> str:
    html = HtmlGenerator()
    content = MutableMixedContent()
    content.append(src)
    return html.content_to_str(content)


def parse_element(src: str | Path, model, issues):
    if isinstance(src, Path):
        with open(src, "r") as f:
            src = f.read().strip()
    e = lxml_element_from_str(src)
    assert isinstance(e.tag, str)
    assert model.match(e)
    try:
        result = kit.SinkDestination[tree.Element]()
        model.parse(issues.append, e, result)
        return result.out
    except:
        mc = MutableMixedContent()
        model.parse(issues.append, e, mc)
        return next(iter(mc))


def check_xml_html(case_dir, model, bare_tex):
    issues = []
    input_xml = case_dir / "input.xml"
    if input_xml.exists():
        element = parse_element(input_xml.read_text(), model, issues)
        with open(case_dir / "expect.xml", "r") as f:
            expected_xml_str = f.read().strip()
    else:
        with open(case_dir / "xhtml.xml", "r") as f:
            expected_xml_str = f.read().strip()
        element = parse_element(expected_xml_str, model, issues)

    assert XML.to_str(element) == expected_xml_str

    util.check_conditions(case_dir, issues)

    expect_html = case_dir / "expect.html"
    if expect_html.exists():
        with open(expect_html, "r") as f:
            expect_html_str = f.read().strip()
    else:
        expect_html_str = expected_xml_str
    html = HtmlGenerator()
    got = html.elements_to_str([element])
    assert html.bare_tex == bare_tex
    assert got == expect_html_str


@pytest.mark.parametrize("case", os.listdir(BLOCK_CASE))
def test_roll_content_html(case):
    case_dir = BLOCK_CASE / case
    core = CoreModels(None)
    check_xml_html(case_dir, core.block, case.startswith("math"))


@pytest.mark.parametrize("case", os.listdir(P_CHILD_CASE))
def test_p_child_html(case):
    case_dir = P_CHILD_CASE / case
    core = CoreModels(None)
    check_xml_html(case_dir, core.inline, case.startswith("math"))
