from pathlib import Path

from lxml.html import builder as E
from lxml.html import tostring

import epijats.baseprint as _
from epijats import html


SNAPSHOT_CASE = Path(__file__).parent / "cases" / "snapshot"

GEN = html.HtmlGenerator()


def test_minimal():
    issues = []
    got = _.BaseprintBuilder(issues.append).build(SNAPSHOT_CASE / "baseprint")
    assert not issues
    assert [_.Author("Wang")] == got.authors
    expect = _.Abstract([_.RichText('A simple test.', [])])
    assert expect == got.abstract


def test_minimal_html_title():
    bp = _.parse_baseprint(SNAPSHOT_CASE / "baseprint")
    expect = tostring(E.TITLE('A test'))
    assert expect == tostring(E.TITLE(*GEN.content(bp.title)))
