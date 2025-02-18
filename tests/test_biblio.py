import os, json, pytest
from pathlib import Path

from epijats import restyle
from epijats import baseprint as bp
from epijats.parse import jats
from epijats import biblio

from .test_baseprint import lxml_element_from_str, str_from_element


REF_ITEM_CASE = Path(__file__).parent / "cases" / "ref_item"


def parse_clean_ref_item(xml_path):
    with open(xml_path, "r") as f:
        expect = f.read().strip()
    model = jats.BiblioRefItemModel()
    issues = []
    ref_item = model.load(issues.append, lxml_element_from_str(expect))
    assert not issues
    assert isinstance(ref_item, bp.BiblioRefItem)
    return ref_item


@pytest.mark.parametrize("case", os.listdir(REF_ITEM_CASE))
def test_xml_roundtrip(case):
    xml_path = REF_ITEM_CASE / case / "jats.xml"
    with open(xml_path, "r") as f:
        expect = f.read().strip()
    model = jats.BiblioRefItemModel()
    issues = []
    assert not issues
    ref_item = model.load(issues.append, lxml_element_from_str(expect))
    assert isinstance(ref_item, bp.BiblioRefItem)
    subel = restyle.biblio_ref_item(ref_item)
    assert str_from_element(subel) == expect


@pytest.mark.parametrize("case", os.listdir(REF_ITEM_CASE))
def test_csljson(case):
    path = REF_ITEM_CASE / case / "csl.json"
    with open(path, "r") as f:
        expect = json.load(f)
    ref_item = parse_clean_ref_item(REF_ITEM_CASE / case / "jats.xml")
    got = biblio.csljson_from_ref_item(ref_item)
    assert got == expect


@pytest.mark.parametrize("case", os.listdir(REF_ITEM_CASE))
def test_biblio_ref_html(case):
    path = REF_ITEM_CASE / case / "ref.html"
    if not path.exists():
        return
    with open(path, "r") as f:
        expect = f.read()
    ref_item = parse_clean_ref_item(REF_ITEM_CASE / case / "jats.xml")
    csl_path = Path(__file__).parent / "full-preview.csl"
    bf = biblio.CiteprocBiblioFormatter(csl_path)
    assert bf.to_str([ref_item]) == expect
