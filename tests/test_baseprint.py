from pathlib import Path

import epijats.baseprint as _


SNAPSHOT_CASE = Path(__file__).parent / "cases" / "snapshot"


def test_minimal():
    issues = []
    got = _.BaseprintBuilder(issues.append).build(SNAPSHOT_CASE / "baseprint")
    assert not issues
    assert "A test" in got.title.inner_html()
    assert [_.Author("Wang")] == got.authors
    expect = _.Abstract([_.RichText('A simple test.', [])])
    assert expect == got.abstract
