import os, pytest
from pathlib import Path

from epijats import condition as fc
from epijats.html import HtmlFormatter, html_content_to_str
from epijats.parse import jats, kit, tree

from .test_baseprint import lxml_element_from_str


HTML = HtmlFormatter()

P_CHILD_CASE = Path(__file__).parent / "cases" / "p_child"


def html_from_element(src: tree.Element) -> str:
    return html_content_to_str([HTML.root(src)])


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
def test_p_child_roundtrip(case):
    xml_path = P_CHILD_CASE/ case / "jats.xml"
    with open(xml_path, "r") as f:
        p_child = parse_element(f.read(), jats.p_child_model())
        got = html_from_element(p_child)
    expect_path = P_CHILD_CASE/ case / "expect.html"
    with open(expect_path, "r") as f:
        expect = f.read().strip()
    assert got == expect
