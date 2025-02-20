import os, json, pytest
from pathlib import Path

from epijats import restyle
from epijats import baseprint as bp
from epijats.parse import jats
from epijats import biblio
from epijats import condition as fc

from .test_baseprint import lxml_element_from_str, str_from_element


REF_ITEM_CASE = Path(__file__).parent / "cases" / "ref_item"
PMC_REF_CASE = Path(__file__).parent / "cases" / "pmc_ref"


def parse_clean_ref_item(src: str | Path):
    if isinstance(src, Path):
        with open(src, "r") as f:
            src = f.read().strip()
    model = jats.BiblioRefItemModel()
    issues: list[fc.FormatIssue] = []
    ref_item = model.load(issues.append, lxml_element_from_str(src))
    assert not issues
    assert isinstance(ref_item, bp.BiblioRefItem)
    return ref_item


KNOWN_PMC_NO_SUPPORT = {
    fc.UnsupportedElement(tag='comment', parent='element-citation'),
    fc.UnsupportedAttributeValue(tag='pub-id', attribute='pub-id-type', value='pii'), 
    fc.UnsupportedAttributeValue(
        tag='pub-id', attribute='pub-id-type', value='medline'
    ),
}

def parse_pmc_ref(p: Path):
    with open(p, "r") as f:
        src = f.read().strip()
    model = jats.BiblioRefItemModel()
    issues: list[fc.FormatIssue] = []
    ref_item = model.load(issues.append, lxml_element_from_str(src))
    conditions = set(i.condition for i in issues) - KNOWN_PMC_NO_SUPPORT
    assert not conditions
    assert isinstance(ref_item, bp.BiblioRefItem)
    return ref_item


@pytest.mark.parametrize("case", os.listdir(REF_ITEM_CASE))
def test_xml_roundtrip(case):
    xml_path = REF_ITEM_CASE / case / "jats.xml"
    with open(xml_path, "r") as f:
        expect = f.read().strip()
        ref_item = parse_clean_ref_item(expect)
    subel = restyle.biblio_ref_item(ref_item)
    assert str_from_element(subel) == expect


@pytest.mark.parametrize("case", os.listdir(REF_ITEM_CASE))
def test_csljson(case):
    path = REF_ITEM_CASE / case / "csl.json"
    with open(path, "r") as f:
        expect = json.load(f)[0]
    ref_item = parse_clean_ref_item(REF_ITEM_CASE / case / "jats.xml")
    got = biblio.csljson_from_ref_item(ref_item)
    assert got == expect


@pytest.mark.parametrize("case", os.listdir(PMC_REF_CASE))
def test_pmc_ref(case):
    path = PMC_REF_CASE / case / "csl.json"
    with open(path, "r") as f:
        expect = json.load(f)[0]
    ref_item = parse_pmc_ref(PMC_REF_CASE / case / "jats.xml")
    got = biblio.csljson_from_ref_item(ref_item)
    assert got == expect
    html_path = PMC_REF_CASE / case / "ref.html"
    if html_path.exists():
        with open(html_path, "r") as f:
            expect = f.read()
        csl_path = Path(__file__).parent / "full-preview.csl"
        bf = biblio.CiteprocBiblioFormatter(csl_path)
        assert bf.to_str([ref_item]) == expect


@pytest.mark.parametrize("case", os.listdir(REF_ITEM_CASE))
def test_biblio_ref_html(case):
    pytest.importorskip("citeproc")
    path = REF_ITEM_CASE / case / "ref.html"
    if not path.exists():
        return
    with open(path, "r") as f:
        expect = f.read()
    ref_item = parse_clean_ref_item(REF_ITEM_CASE / case / "jats.xml")
    csl_path = Path(__file__).parent / "full-preview.csl"
    bf = biblio.CiteprocBiblioFormatter(csl_path)
    assert bf.to_str([ref_item]) == expect
