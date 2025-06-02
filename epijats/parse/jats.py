from __future__ import annotations

from warnings import warn

from lxml import etree

from .. import baseprint as bp
from .. import condition as fc
from ..tree import (
    Citation, CitationTuple, Element, MixedContent, StartTag, make_paragraph
)

from . import kit
from .kit import (
    AttribView,
    TagModelBase,
    Binder,
    ContentParser,
    IssueCallback,
    tag_model,
    Model,
    Parser,
    ReaderBinder,
    Sink,
    UnionModel,
)
from .tree import (
    DataElementModel,
    EModel,
    HtmlDataElementModel,
    MixedContentBinder,
    MixedContentLoader,
    TagElementModelBase,
    TextElementModel,
    parse_mixed_content,
)
from .math import disp_formula_model, inline_formula_model, math_model


class ExtLinkModel(TagElementModelBase):
    def __init__(self, content_model: EModel):
        super().__init__('ext-link')
        self.content_model = content_model

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        link_type = e.attrib.get("ext-link-type")
        if link_type and link_type != "uri":
            log(fc.UnsupportedAttributeValue.issue(e, "ext-link-type", link_type))
            return None
        k_href = "{http://www.w3.org/1999/xlink}href"
        href = e.attrib.get(k_href)
        kit.check_no_attrib(log, e, ["ext-link-type", k_href])
        if href is None:
            log(fc.MissingAttribute.issue(e, k_href))
            return None
        else:
            ret = bp.Hyperlink(href)
            parse_mixed_content(log, e, self.content_model, ret.content)
            return ret


class BiblioRefPool:
    def __init__(self, avail: list[bp.BiblioRefItem]):
        self._avail = avail
        self.used: list[bp.BiblioRefItem] = []

    def cite(self, rid: str)-> int:
        """Cite a reference in the bibliography.

        Returns:
            Zero if no reference found, otherwise 1 to N for bibliography entry.
        """

        for i, ref in enumerate(self.used):
            if rid == ref.id:
                return i + 1
        for ref in self._avail:
            if rid == ref.id:
                self.used.append(ref)
                return len(self.used) 
        return 0


class CitationModel(TagElementModelBase):
    def __init__(self, biblio: BiblioRefPool):
        super().__init__(StartTag('xref', {'ref-type': 'bibr'}))
        self._biblio = biblio

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        assert e.attrib.get("ref-type") == "bibr"
        alt = e.attrib.get("alt")
        if alt and alt == e.text and not len(e):
            del e.attrib["alt"]
        kit.check_no_attrib(log, e, ["rid", "ref-type"])
        rid = e.attrib.get("rid")
        if rid is None:
            log(fc.MissingAttribute.issue(e, "rid"))
            return None
        for s in e:
            log(fc.UnsupportedElement.issue(s))
        i = self._biblio.cite(rid)
        if i:
            if e.text and e.text.strip() != str(i):
                log(fc.IgnoredText.issue(e))
            return Citation(rid, i)
        else:
            log(fc.InvalidCitation.issue(e))
            ret = bp.CrossReference(rid, "bibr")
            ret.content.append_text(e.text)
            return ret


class AutoCorrectCitationModel(CitationModel):
    def __init__(self, biblio: BiblioRefPool):
        super().__init__(biblio)

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        citation = super().load(log, e)
        if not citation:
            return None
        ret = CitationTuple()
        ret.append(citation)
        return ret


class CitationTupleModel(TagElementModelBase):
    def __init__(self, biblio: BiblioRefPool):
        super().__init__('sup')
        self._submodel = CitationModel(biblio)

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        assert e.tag == 'sup'
        kit.check_no_attrib(log, e)
        if not any(c.tag == 'xref' and c.attrib.get('ref-type') == 'bibr' for c in e):
          return None
        delim = e.text.strip() if e.text else ''
        if delim not in ['', '[', '(']:
            log(fc.IgnoredText.issue(e))
        for child in e:
            delim = child.tail.strip() if child.tail else ''
            if delim not in ['', ',', ';', ']', ')']:
                log(fc.IgnoredText.issue(e))
        ret = CitationTuple()
        eparser = self._submodel.bind(log, ret.append)
        for child in e:
            child.tail = None
            if not eparser.parse_element(child):
                log(fc.UnsupportedElement.issue(child))
        return ret


class CrossReferenceModel(TagElementModelBase):
    def __init__(self, content_model: EModel):
        super().__init__('xref')
        self.content_model = content_model

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        alt = e.attrib.get("alt")
        if alt and alt == e.text and not len(e):
            del e.attrib["alt"]
        kit.check_no_attrib(log, e, ["rid"])
        rid = e.attrib.get("rid")
        if rid is None:
            log(fc.MissingAttribute.issue(e, "rid"))
            return None
        ref_type = e.attrib.get("ref-type")
        if ref_type == "bibr":
            warn("CitationModel not handling xref ref-type bibr")
        ret = bp.CrossReference(rid, ref_type)
        parse_mixed_content(log, e, self.content_model, ret.content)
        return ret


def disp_quote_mode(p_elements: EModel) -> EModel:
    """<disp-quote> Quote, Displayed

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/disp-quote.html
    """
    p = TextElementModel({'p': 'p'}, p_elements)
    return HtmlDataElementModel('disp-quote', p, 'blockquote')


class ListModel(TagElementModelBase):
    def __init__(self, p_elements_model: EModel):
        super().__init__('list')
        # https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/list-item-model.html
        # %list-item-model
        p = TextElementModel({'p': 'p'}, p_elements_model)
        list_item_content = p | self
        self._list_content_model = HtmlDataElementModel(
            'list-item', list_item_content, 'li'
        )

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        kit.check_no_attrib(log, e, ['list-type'])
        list_type = kit.get_enum_value(log, e, 'list-type', bp.ListTypeCode)
        ret = bp.List(list_type)
        self._list_content_model.bind(log, ret.append).parse_array_content(e)
        return ret


def def_term_model() -> EModel:
    """<term> Definition List: Term

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/term.html
    """
    return TextElementModel({'term': 'dt'}, base_hypertext_model())


def def_def_model(p_elements: EModel) -> EModel:
    """<def> Definition List: Definition

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/def.html
    """
    p = TextElementModel({'p': 'p'}, p_elements)
    return HtmlDataElementModel('def', p, 'dd')


def def_item_model(p_elements: EModel) -> EModel:
    """<def-item> Definition List: Definition Item

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/def-item.html
    """
    content_model = def_term_model() | def_def_model(p_elements)
    return DataElementModel('def-item', content_model)


def def_list_model(p_elements: EModel) -> EModel:
    """<def-list> Definition List

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/def-list.html
    """
    content_model = def_item_model(p_elements)
    return HtmlDataElementModel('def-list', content_model, 'dl')


class TableCellModel(TagElementModelBase):
    def __init__(self, content_model: EModel, *, header: bool):
        super().__init__('th' if header else 'td')
        self.content_model = content_model

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        kit.check_no_attrib(log, e, ['align'])
        align = kit.get_enum_value(log, e, 'align', bp.AlignCode)
        ret = bp.TableCell(self.tag == 'th', align)
        parse_mixed_content(log, e, self.content_model, ret.content)
        return ret


def mixed_element_model(tag: str) -> Model[MixedContent]:
    return tag_model(tag, MixedContentLoader(base_hypertext_model()))


def title_model(tag: str) -> Model[MixedContent]:
    content_model = base_hypertext_model() | break_model()
    return tag_model(tag, MixedContentLoader(content_model))


def hypertext_element_binder(tag: str) -> Binder[MixedContent]:
    return MixedContentBinder(tag, base_hypertext_model())


title_binder = hypertext_element_binder


def title_group_model() -> Model[MixedContent]:
    reader = kit.SingleSubElementReader(title_model('article-title'))
    return ReaderBinder('title-group', reader)


def orcid_model() -> Model[bp.Orcid]:
    return tag_model('contrib-id', load_orcid)


def load_orcid(log: IssueCallback, e: etree._Element) -> bp.Orcid | None:
    if e.tag != 'contrib-id' or e.attrib.get('contrib-id-type') != 'orcid':
        return None
    kit.check_no_attrib(log, e, ['contrib-id-type'])
    for s in e:
        log(fc.UnsupportedElement.issue(s))
    try:
        url = e.text or ""
        return bp.Orcid.from_url(url)
    except ValueError:
        log(fc.InvalidOrcid.issue(e, url))
        return None


def load_author_group(log: IssueCallback, e: etree._Element) -> list[bp.Author] | None:
    kit.check_no_attrib(log, e)
    acp = ContentParser(log)
    ret = acp.every(tag_model('contrib', load_author))
    acp.parse_array_content(e)
    return list(ret)


def person_name_model() -> Model[bp.PersonName]:
    return tag_model('name', load_person_name)


def load_person_name(log: IssueCallback, e: etree._Element) -> bp.PersonName | None:
    kit.check_no_attrib(log, e)
    p = ContentParser(log)
    surname = p.one(tag_model('surname', kit.load_string))
    given_names = p.one(tag_model('given-names', kit.load_string))
    p.parse_array_content(e)
    if not surname.out and not given_names.out:
        log(fc.MissingContent.issue(e))
        return None
    return bp.PersonName(surname.out, given_names.out)


def load_author(log: IssueCallback, e: etree._Element) -> bp.Author | None:
    if e.tag != 'contrib':
        return None
    if not kit.confirm_attrib_value(log, e, 'contrib-type', ['author']):
        return None
    kit.check_no_attrib(log, e, ['contrib-type', 'id'])
    p = ContentParser(log)
    name = p.one(person_name_model())
    email = p.one(tag_model('email', kit.load_string))
    orcid = p.one(orcid_model())
    p.parse_array_content(e)
    if name.out is None:
        log(fc.MissingContent.issue(e, "Missing name"))
        return None
    return bp.Author(name.out, email.out, orcid.out)


class AutoCorrectModel(Model[Element]):
    def __init__(self, p_elements: EModel):
        self.p_elements = p_elements

    def bind(self, log: IssueCallback, dest: Sink[Element]) -> Parser:
        return AutoCorrectParser(log, dest, self.p_elements)


class AutoCorrectParser(Parser):
    def __init__(self, log: IssueCallback, dest: Sink[Element], p_elements: EModel):
        super().__init__(log)
        self.dest = dest
        self._parser = p_elements.bind(log, self._correct)

    def _correct(self, parsed_p_element: Element) -> None:
        correction = make_paragraph("")
        correction.content.append(parsed_p_element)
        self.dest(correction)

    def match(self, tag: str, attrib: AttribView) -> kit.ParseFunc | None:
        return self._parser.match(tag, attrib)


class ProtoSectionContentBinder(Binder[bp.ProtoSection]):
    def __init__(self, p_elements: EModel, p_level: EModel):
        self.p_elements = p_elements
        self.p_level = p_level

    def bind(self, log: IssueCallback, dest: bp.ProtoSection) -> Parser:
        ret = ContentParser(log)
        ret.bind(self.p_level, dest.presection.append)
        ret.bind(AutoCorrectModel(self.p_elements), dest.presection.append)
        ret.bind(SectionModel(self.p_elements), dest.subsections.append)
        return ret


def proto_section_binder(tag: str, p_elements: EModel) -> Binder[bp.ProtoSection]:
    p_level = TextElementModel({'p': 'p'}, p_elements)
    return kit.SingleElementBinder(tag, ProtoSectionContentBinder(p_elements, p_level))


class SectionModel(TagModelBase[bp.Section]):
    """<sec> Section
    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/sec.html
    """

    def __init__(self, p_elements: EModel):
        super().__init__('sec')
        p_level = p_level_model(p_elements)
        self._proto = ProtoSectionContentBinder(p_elements, p_level)

    def load(self, log: IssueCallback, e: etree._Element) -> bp.Section | None:
        kit.check_no_attrib(log, e, ['id'])
        ret = bp.Section([], [], e.attrib.get('id'), MixedContent())
        cp = ContentParser(log)
        cp.bind(title_binder('title'), ret.title)
        cp.bind(self._proto, ret)
        cp.parse_array_content(e)
        return ret


class PersonGroupModel(TagModelBase[list[bp.PersonName | str]]):
    """<person-group> Person Group for a Cited Publication
    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/person-group.html
    """

    def __init__(self, group_type: str) -> None:
        super().__init__('person-group', {'person-group-type': group_type})

    def load(
        self, log: IssueCallback, e: etree._Element
    ) -> list[bp.PersonName | str] | None:
        ret: list[bp.PersonName | str] = []
        k = 'person-group-type'
        kit.check_no_attrib(log, e, [k])
        cp = ContentParser(log)
        cp.bind(tag_model('name', load_person_name), ret.append)
        cp.bind(tag_model('string-name', kit.load_string), ret.append)
        cp.parse_array_content(e)
        return ret


def break_model() -> EModel:
    """<break> Line Break
    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/break.html
    """
    return TextElementModel({'break': 'br'}, False)


def formatted_text_model(sub_model: EModel | None = None) -> EModel:
    formatted_text_tags = {
        'bold': 'strong',
        'italic': 'em',
        'monospace': 'tt',
        'sub': 'sub',
        'sup': 'sup',
    }
    content_model: EModel | bool = True if sub_model is None else sub_model
    return TextElementModel(formatted_text_tags, content_model)


def base_hypertext_model() -> EModel:
    """Base hypertext model"""
    hypertext = UnionModel[Element]()
    hypertext |= ExtLinkModel(formatted_text_model())
    hypertext |= CrossReferenceModel(formatted_text_model())
    hypertext |= inline_formula_model()
    hypertext |= formatted_text_model(hypertext)
    return hypertext


def p_elements_model(biblio: BiblioRefPool | None = None) -> EModel:
    """Paragraph Elements

    Similar to JATS def, but using more restrictive base hypertext model.
    """
    hypertext = base_hypertext_model()
    # NOTE: open issue whether xref should be allowed in preformatted
    preformatted = TextElementModel({'code': 'pre', 'preformat': 'pre'}, hypertext)

    # https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/p-elements.html
    # %p-elements
    p_elements = UnionModel[Element]()
    if biblio:
        p_elements |= AutoCorrectCitationModel(biblio)
        p_elements |= CitationTupleModel(biblio)
    p_elements |= hypertext
    p_elements |= math_model()
    p_elements |= disp_formula_model()
    p_elements |= preformatted
    p_elements |= disp_quote_model(p_elements)
    p_elements |= ListModel(p_elements)
    p_elements |= def_list_model(p_elements)
    return p_elements


def table_wrap_model(p_elements: EModel) -> EModel:
    br = break_model()
    th = TableCellModel(p_elements | br, header=True)
    td = TableCellModel(p_elements | br, header=False)
    tr = HtmlDataElementModel('tr', th | td)
    thead = HtmlDataElementModel('thead', tr)
    tbody = HtmlDataElementModel('tbody', tr)
    table = HtmlDataElementModel('table', thead | tbody)
    return DataElementModel('table-wrap', table)


def disp_quote_model(p_elements: EModel) -> EModel:
    p = TextElementModel({'p': 'p'}, p_elements)
    ret = HtmlDataElementModel('disp-quote', p)
    ret.html = StartTag('blockquote')
    return ret


def p_level_model(p_elements: EModel) -> EModel:
    hypertext = base_hypertext_model()
    p_level = UnionModel[Element]()
    p_level |= TextElementModel({'p': 'p'}, p_elements)
    p_level |= disp_formula_model()
    p_level |= TextElementModel({'code': 'pre', 'preformat': 'pre'}, hypertext)
    p_level |= ListModel(p_elements)
    p_level |= table_wrap_model(p_elements)
    p_level |= disp_quote_model(p_elements)
    return p_level


CC_URLS = {
    'https://creativecommons.org/publicdomain/zero/': bp.CcLicenseType.CC0,
    'https://creativecommons.org/licenses/by/': bp.CcLicenseType.BY,
    'https://creativecommons.org/licenses/by-sa/': bp.CcLicenseType.BYSA,
    'https://creativecommons.org/licenses/by-nc/': bp.CcLicenseType.BYNC,
    'https://creativecommons.org/licenses/by-nc-sa/': bp.CcLicenseType.BYNCSA,
    'https://creativecommons.org/licenses/by-nd/': bp.CcLicenseType.BYND,
    'https://creativecommons.org/licenses/by-nc-nd/': bp.CcLicenseType.BYNCND,
}


def read_license_ref(log: IssueCallback, e: etree._Element, dest: bp.License) -> bool:
    kit.check_no_attrib(log, e, ['content-type'])
    dest.license_ref = kit.load_string_content(log, e)
    got_license_type = kit.get_enum_value(log, e, 'content-type', bp.CcLicenseType)
    for prefix, matching_type in CC_URLS.items():
        if dest.license_ref.startswith(prefix):
            if got_license_type and got_license_type != matching_type:
                log(fc.InvalidAttributeValue.issue(e, 'content-type', got_license_type))
            dest.cc_license_type = matching_type
            return True
    dest.cc_license_type = got_license_type
    return True


def load_license(log: IssueCallback, e: etree._Element) -> bp.License | None:
    ali = "{http://www.niso.org/schemas/ali/1.0/}"
    ret = bp.License(MixedContent(), "", None)
    kit.check_no_attrib(log, e)
    ap = ContentParser(log)
    ap.bind(hypertext_element_binder('license-p').once(), ret.license_p)
    ap.bind(ReaderBinder(f"{ali}license_ref", read_license_ref).once(), ret)
    ap.parse_array_content(e)
    return None if ret.blank() else ret


def load_permissions(log: IssueCallback, e: etree._Element) -> bp.Permissions | None:
    kit.check_no_attrib(log, e)
    ap = ContentParser(log)
    statement = ap.one(mixed_element_model('copyright-statement'))
    license = ap.one(tag_model("license", load_license))
    ap.parse_array_content(e)
    if license.out is None or statement.out is None or statement.out.blank():
        return None
    return bp.Permissions(license.out, bp.Copyright(statement.out))


def read_article_meta(
    log: IssueCallback, e: etree._Element, dest: bp.Baseprint
) -> bool:
    kit.check_no_attrib(log, e)
    p_elements = p_elements_model()
    cp = ContentParser(log)
    title = cp.one(title_group_model())
    authors = cp.one(tag_model('contrib-group', load_author_group))
    cp.bind(proto_section_binder('abstract', p_elements).once(), dest.abstract)
    permissions = cp.one(tag_model('permissions', load_permissions))
    cp.parse_array_content(e)
    if title.out:
        dest.title = title.out
    if authors.out is not None:
        dest.authors = authors.out
    if permissions.out is not None:
        dest.permissions = permissions.out
    return True


def read_article_front(
    log: IssueCallback, e: etree._Element, dest: bp.Baseprint
) -> bool:
    kit.check_no_attrib(log, e)
    cp = ContentParser(log)
    cp.bind(ReaderBinder('article-meta', read_article_meta).once(), dest)
    cp.parse_array_content(e)
    return True


class IntModel(TagModelBase[int]):
    def __init__(self, tag: str, max_int: int):
        super().__init__(tag)
        self.max_int = max_int

    def load(self, log: IssueCallback, e: etree._Element) -> int | None:
        kit.check_no_attrib(log, e)
        ret = kit.load_int(log, e)
        if ret and ret not in range(1, self.max_int + 1):
            log(fc.UnsupportedAttributeValue.issue(e, self.tag, str(ret)))
            ret = None
        return ret


class DateBuilder:
    def __init__(self, cp: ContentParser):
        self.year = cp.one(tag_model('year', kit.load_int))
        self.month = cp.one(IntModel('month', 12))
        self.day = cp.one(IntModel('day', 31))

    def build(self) -> bp.Date | None:
        ret = None
        if self.year.out:
            ret = bp.Date(self.year.out)
            if self.month.out:
                ret.month = self.month.out
                if self.day.out:
                    ret.day = self.day.out
        return ret


class AccessDateModel(TagModelBase[bp.Date]):
    """<date-in-citation> Date within a Citation

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/date-in-citation.html
    """
    def __init__(self) -> None:
        super().__init__('date-in-citation')

    def load(self, log: IssueCallback, e: etree._Element) -> bp.Date | None:
        kit.check_no_attrib(log, e, ['content-type'])
        if e.attrib.get('content-type') != 'access-date':
            return None
        cp = ContentParser(log)
        date = DateBuilder(cp)
        cp.parse_array_content(e)
        return date.build()


def read_pub_id(
    log: IssueCallback, e: etree._Element, dest: dict[bp.PubIdType, str]
) -> bool:
    """<pub-id> Publication Identifier for a Cited Publication

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/pub-id.html
    """
    kit.check_no_attrib(log, e, ['pub-id-type'])
    pub_id_type = kit.get_enum_value(log, e, 'pub-id-type', bp.PubIdType)
    if not pub_id_type:
        return False
    if pub_id_type in dest:
        log(fc.ExcessElement.issue(e))
        return False
    value = kit.load_string_content(log, e)
    if not value:
        log(fc.MissingContent.issue(e))
        return False
    match pub_id_type:
        case bp.PubIdType.DOI:
            if not value.startswith("10."):
                log(fc.InvalidDoi.issue(e, "DOIs begin with '10.'"))
                https_prefix = "https://doi.org/"
                if value.startswith(https_prefix):
                    value = value[len(https_prefix):]
                else:
                    return False
        case bp.PubIdType.PMID:
            try:
                int(value)
            except ValueError as ex:
                log(fc.InvalidPmid.issue(e, str(ex)))
                return False
    dest[pub_id_type] = value
    return True


def load_edition(log: IssueCallback, e: etree._Element) -> int | None:
    for s in e:
        log(fc.UnsupportedElement.issue(s))
        if s.tail and s.tail.strip():
            log(fc.IgnoredText.issue(e))
    text = e.text or ""
    if text.endswith('.'):
        text = text[:-1]
    if text.endswith((' Ed', ' ed')):
        text = text[:-3]
    if text.endswith(('st', 'nd', 'rd', 'th')):
        text = text[:-2]
    try:
        return int(text)
    except ValueError:
        log(fc.InvalidInteger.issue(e, text))
        return None


def read_element_citation(
    log: IssueCallback, e: etree._Element, dest: bp.BiblioRefItem
) -> bool:
    kit.check_no_attrib(log, e)
    cp = ContentParser(log)
    source = cp.one(tag_model('source', kit.load_string))
    title = cp.one(tag_model('article-title', kit.load_string))
    authors = cp.one(PersonGroupModel('author'))
    editors = cp.one(PersonGroupModel('editor'))
    edition = cp.one(tag_model('edition', load_edition))
    date = DateBuilder(cp)
    access_date = cp.one(AccessDateModel())
    fields = {}
    for key in bp.BiblioRefItem.BIBLIO_FIELD_KEYS:
        fields[key] = cp.one(tag_model(key, kit.load_string))
    cp.bind(kit.ReaderBinder('pub-id', read_pub_id), dest.pub_ids)
    cp.parse_array_content(e)
    dest.source = source.out
    dest.article_title = title.out
    if authors.out:
        dest.authors = authors.out
    if editors.out:
        dest.editors = editors.out
    dest.edition = edition.out
    dest.date = date.build()
    dest.access_date = access_date.out
    for key, parser in fields.items():
        if parser.out:
            dest.biblio_fields[key] = parser.out
    return True


class BiblioRefItemModel(TagModelBase[bp.BiblioRefItem]):
    """<ref> Reference Item

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/ref.html
    """

    def __init__(self) -> None:
        super().__init__('ref')

    def load(self, log: IssueCallback, e: etree._Element) -> bp.BiblioRefItem | None:
        ret = bp.BiblioRefItem()
        kit.check_no_attrib(log, e, ['id'])
        cp = ContentParser(log)
        cp.bind(ReaderBinder('element-citation', read_element_citation).once(), ret)
        cp.parse_array_content(e)
        ret.id = e.attrib.get('id', "")
        return ret


class RefListModel(TagModelBase[bp.BiblioRefList]):
    def __init__(self) -> None:
        super().__init__('ref-list')

    def load(self, log: IssueCallback, e: etree._Element) -> bp.BiblioRefList | None:
        kit.check_no_attrib(log, e)
        cp = ContentParser(log)
        title = cp.one(title_model('title'))
        references = cp.every(BiblioRefItemModel())
        cp.parse_array_content(e)
        return bp.BiblioRefList(title.out, list(references))


def load_article(log: IssueCallback, e: etree._Element) -> bp.Baseprint | None:
    """Loader function for <article>

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/article.html
    """
    lang = '{http://www.w3.org/XML/1998/namespace}lang'
    kit.confirm_attrib_value(log, e, lang, ['en', None])
    kit.check_no_attrib(log, e, [lang])
    ret = bp.Baseprint()
    back = e.find("back")
    if back is not None:
        ret.ref_list = kit.load_single_sub_element(log, back, RefListModel())
        e.remove(back)
    biblio = BiblioRefPool(ret.ref_list.references) if ret.ref_list else None
    cp = ContentParser(log)
    cp.bind(ReaderBinder('front', read_article_front), ret)
    cp.bind(proto_section_binder('body', p_elements_model(biblio)), ret.body)
    cp.parse_array_content(e)
    if ret.ref_list:
        assert biblio
        ret.ref_list.references = biblio.used
    if ret.title.blank():
        log(fc.FormatIssue(fc.MissingContent('article-title', 'title-group')))
    if not len(ret.authors):
        log(fc.FormatIssue(fc.MissingContent('contrib', 'contrib-group')))
    if ret.abstract.has_no_content():
        log(fc.FormatIssue(fc.MissingContent('abstract', 'article-meta')))
    if ret.body.has_no_content():
        log(fc.FormatIssue(fc.MissingContent('body', 'article')))
    return ret
