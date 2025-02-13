import os, pytest
from pathlib import Path

from epijats import restyle
from epijats import baseprint as bp
from epijats.parse import jats

from .test_baseprint import lxml_element_from_str, str_from_element


REF_ITEM_CASE = Path(__file__).parent / "cases" / "ref_item"


@pytest.mark.parametrize("case", os.listdir(REF_ITEM_CASE))
def test_xml_roundtrip(case):
    xml_path = REF_ITEM_CASE / case / "jats.xml"
    with open(xml_path, "r") as f:
        expect = f.read().strip()
    model = jats.BiblioRefItemModel()
    issues = []
    ref_item = model.load(issues.append, lxml_element_from_str(expect))
    assert isinstance(ref_item, bp.BiblioRefItem)
    subel = restyle.biblio_ref_item(ref_item)
    assert str_from_element(subel) == expect
