from epijats import restyle
from epijats import baseprint as bp
from epijats.parse import jats

from .test_baseprint import wrap_xml, wrap_to_xml, xml_sub_element, xml_to_root_str

def test_book_reference():
    dump = wrap_xml("""
<ref id="ref-hartl_essential_2006">
  <element-citation publication-type="book">
    <person-group person-group-type="author">
      <name>
        <surname>Hartl</surname>
        <given-names>Daniel L.</given-names>
      </name>
      <name>
        <surname>Jones</surname>
        <given-names>Elizabeth W.</given-names>
      </name>
    </person-group>
    <year iso-8601-date="2006">2006</year>
    <source>Essential genetics: A genomics perspective</source>
    <publisher-name>Jones; Bartlett Publishers</publisher-name>
    <publisher-loc>Boston</publisher-loc>
    <edition>4th ed</edition>
    <isbn>978-0-7637-3527-2</isbn>
  </element-citation>
</ref>
""")
    model = jats.BiblioRefItemModel()
    issues = []
    ref_item = model.load(issues.append, wrap_to_xml(dump))
    assert isinstance(ref_item, bp.BiblioRefItem)
    subel = restyle.biblio_ref_item(ref_item)
    xe = xml_sub_element(subel)
    assert xml_to_root_str(xe) == dump
