import os, json, pytest
from pathlib import Path

from lxml import etree

from citeproc import SCHEMA_PATH

from epijats.xml import baseprint as restyle
from epijats.metadata import BiblioRefItem
from epijats.parse.back import BiblioRefItemModel
from epijats import biblio
from epijats import condition as fc

from .test_baseprint import lxml_element_from_str, str_from_element


REF_ITEM_CASE = Path(__file__).parent / "cases" / "ref_item"
PMC_REF_CASE = Path(__file__).parent / "cases" / "pmc_ref"


def parse_clean_ref_item(src: str | Path):
    if isinstance(src, Path):
        with open(src, "r") as f:
            src = f.read().strip()
    model = BiblioRefItemModel()
    issues: list[fc.FormatIssue] = []
    ref_item = model.load(issues.append, lxml_element_from_str(src))
    assert not issues
    assert isinstance(ref_item, BiblioRefItem)
    return ref_item


KNOWN_PMC_NO_SUPPORT = {
    fc.UnsupportedElement(tag='ext-link', parent='comment'),
    fc.UnsupportedAttributeValue(tag='pub-id', attribute='pub-id-type', value='pii'), 
    fc.UnsupportedAttributeValue(
        tag='pub-id', attribute='pub-id-type', value='medline'
    ),
    fc.UnsupportedAttribute('element-citation', 'publication-type'),
}

def parse_pmc_ref(p: Path):
    with open(p, "r") as f:
        src = f.read().strip()
    model = BiblioRefItemModel()
    issues: list[fc.FormatIssue] = []
    ref_item = model.load(issues.append, lxml_element_from_str(src))
    conditions = set(i.condition for i in issues) - KNOWN_PMC_NO_SUPPORT
    assert not conditions
    assert isinstance(ref_item, BiblioRefItem)
    return ref_item


@pytest.mark.parametrize("case", os.listdir(REF_ITEM_CASE))
def test_biblio_ref_xml(case):
    with open(REF_ITEM_CASE / case / "article.xml", "r") as f:
        expected_xml_str = f.read().strip()
    jats_xml = REF_ITEM_CASE / case / "jats.xml"
    if jats_xml.exists():
        ref_item = parse_clean_ref_item(jats_xml.read_text())
    else:
        ref_item = parse_clean_ref_item(expected_xml_str)
    subel = restyle.biblio_ref_item(ref_item)
    assert str_from_element(subel) == expected_xml_str


@pytest.mark.parametrize("case", os.listdir(REF_ITEM_CASE))
def test_csljson_from_ref_item(case):
    path = REF_ITEM_CASE / case / "csl.json"
    with open(path, "r") as f:
        expect = json.load(f)[0]
    ref_item = parse_clean_ref_item(REF_ITEM_CASE / case / "article.xml")
    got = biblio.csljson_from_ref_item(ref_item)
    assert got == expect


@pytest.mark.parametrize("case", os.listdir(REF_ITEM_CASE))
def test_ref_item_from_csljson(case):
    with open(REF_ITEM_CASE / case / "article.xml") as f:
        expected = parse_clean_ref_item(f.read())
    path = REF_ITEM_CASE / case / "csl.json"
    with open(path, "r") as f:
        data = json.load(f)[0]
        got = biblio.ref_item_from_csljson(data)
    assert got == expected


def check_html_match(html_path, ref_item, abridged: bool):
    if html_path.exists():
        with open(html_path, "r") as f:
            expect = f.read().strip()
        bf = biblio.CiteprocBiblioFormatter(abridged=abridged)
        assert bf.to_str([ref_item]) == expect


@pytest.mark.parametrize("case", os.listdir(PMC_REF_CASE))
def test_pmc_ref(case):
    case_path = PMC_REF_CASE / case
    with open(case_path / "csl.json", "r") as f:
        expect = json.load(f)[0]
    ref_item = parse_pmc_ref(PMC_REF_CASE / case / "jats.xml")
    got = biblio.csljson_from_ref_item(ref_item)
    assert got == expect
    check_html_match(case_path / "full.html", ref_item, False)
    check_html_match(case_path / "abridged.html", ref_item, True)


@pytest.mark.parametrize("case", os.listdir(REF_ITEM_CASE))
def test_biblio_ref_html(case):
    case_path = REF_ITEM_CASE / case
    ref_item = parse_clean_ref_item(case_path / "article.xml")
    check_html_match(case_path / "full.html", ref_item, False)
    check_html_match(case_path / "abridged.html", ref_item, True)


def test_csl_valid():
        schema = etree.RelaxNG(etree.parse(SCHEMA_PATH))
        csl_path = Path(__file__).parent / "../epijats/csl/full-preview.csl"
        parser = etree.XMLParser(remove_comments=True, encoding='utf-8')
        root = etree.parse(csl_path, parser)
        assert schema.validate(root), str(schema.error_log)
