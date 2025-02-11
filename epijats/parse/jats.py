from __future__ import annotations

from lxml import etree

from .. import baseprint as bp
from .. import condition as fc
from ..tree import Element, MixedContent, StartTag, make_paragraph

from . import kit
from .kit import (
    BaseModel,
    Binder,
    ContentParser,
    IssueCallback,
    Loader,
    LoaderModel,
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
    TextElementModel,
    parse_mixed_content,
)


class ExtLinkModel(BaseModel[Element]):
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


class CrossReferenceModel(BaseModel[Element]):
    def __init__(self, content_model: EModel):
        super().__init__('xref')
        self.content_model = content_model

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        kit.check_no_attrib(log, e, ["rid", "ref-type"])
        rid = e.attrib.get("rid")
        if rid is None:
            log(fc.MissingAttribute.issue(e, "rid"))
            return None
        ref_type = e.attrib.get("ref-type")
        if ref_type and ref_type != "bibr":
            log(fc.UnsupportedAttributeValue.issue(e, "ref-type", ref_type))
            return None
        ret = bp.CrossReference(rid, ref_type)
        parse_mixed_content(log, e, self.content_model, ret.content)
        return ret


class ListModel(BaseModel[Element]):
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


class TableCellModel(BaseModel[Element]):
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
    return LoaderModel(tag, MixedContentLoader(base_hypertext_model()))


title_model = mixed_element_model

def hypertext_element_binder(tag: str) -> Binder[MixedContent]:
    return MixedContentBinder(tag, base_hypertext_model())


title_binder = hypertext_element_binder


def title_group_model() -> Model[MixedContent]:
    reader = kit.SingleSubElementReader(title_model('article-title'))
    return ReaderBinder('title-group', reader)


def orcid_model() -> Model[bp.Orcid]:
    return LoaderModel('contrib-id', load_orcid)


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
    ret = acp.every(LoaderModel('contrib', load_author))
    acp.parse_array_content(e)
    return list(ret)


def person_name_model() -> Model[bp.PersonName]:
    return LoaderModel('name', load_person_name)


def load_person_name(log: IssueCallback, e: etree._Element) -> bp.PersonName | None:
    kit.check_no_attrib(log, e)
    p = ContentParser(log)
    surname = p.one(LoaderModel('surname', kit.load_string))
    given_names = p.one(LoaderModel('given-names', kit.load_string))
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
    email = p.one(LoaderModel('email', kit.load_string))
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

    def match(self, tag: str) -> kit.ParseFunc | None:
        return self._parser.match(tag)


class ProtoSectionContentBinder(Binder[bp.ProtoSection]):
    def __init__(self, p_elements: EModel, p_level: EModel):
        self.p_elements = p_elements
        self.p_level = p_level

    def bind(self, log: IssueCallback, dest: bp.ProtoSection) -> Parser:
        ret = ContentParser(log)
        ret.bind(self.p_level, dest.presection.append)
        ret.bind(AutoCorrectModel(self.p_elements), dest.presection.append)
        ret.bind(section_model(self.p_elements), dest.subsections.append)
        return ret


def proto_section_binder(tag: str, p_elements: EModel) -> Binder[bp.ProtoSection]:
    p_level = TextElementModel({'p': 'p'}, p_elements)
    return kit.SingleElementBinder(tag, ProtoSectionContentBinder(p_elements,p_level))


class SectionLoader(Loader[bp.Section]):
    def __init__(self, p_elements: EModel):
        p_level = p_level_model(p_elements)
        self._proto = ProtoSectionContentBinder(p_elements, p_level)

    def __call__(self, log: IssueCallback, e: etree._Element) -> bp.Section | None:
        kit.check_no_attrib(log, e, ['id'])
        ret = bp.Section([],[], e.attrib.get('id'), MixedContent())
        cp = ContentParser(log)
        cp.bind(title_binder('title'), ret.title)
        cp.bind(self._proto, ret)
        cp.parse_array_content(e)
        return ret


def section_model(p_elements: EModel) -> Model[bp.Section]:
    return LoaderModel('sec', SectionLoader(p_elements))


def ref_authors_model() -> Model[list[bp.PersonName | str]]:
    return LoaderModel('person-group', load_ref_authors)


def load_ref_authors(
    log: IssueCallback, e: etree._Element
) -> list[bp.PersonName | str] | None:
    ret: list[bp.PersonName | str] = []
    k = 'person-group-type'
    kit.check_no_attrib(log, e, [k])
    v = e.attrib.get(k, "")
    if v != 'author':
        log(fc.UnsupportedAttributeValue.issue(e, k, v))
        return None
    kit.prep_array_elements(log, e)
    for s in e:
        if s.tag == 'name':
            if pname := load_person_name(log, s):
                ret.append(pname)
        elif s.tag == 'string-name':
            if sname := kit.load_string(log, s):
                ret.append(sname)
        else:
            log(fc.UnsupportedElement.issue(s))
    return ret


def formatted_text_model(sub_model: EModel | None = None) -> EModel:
    formatted_text_tags = {
        'bold': 'strong',
        'italic': 'em',
        'monospace': 'tt',
        'sub': 'sub',
        'sup': 'sup',
    }
    content_model = True if sub_model is None else sub_model
    return TextElementModel(formatted_text_tags, content_model)


def base_hypertext_model() -> EModel:
    """Base hypertext model"""
    hypertext = UnionModel[Element]()
    hypertext |= ExtLinkModel(formatted_text_model())
    hypertext |= CrossReferenceModel(formatted_text_model())
    hypertext |= formatted_text_model(hypertext)
    return hypertext


def p_elements_model() -> EModel:
    """Paragraph Elements

    Similar to JATS def, but using more restrictive base hypertext model.
    """
    hypertext = base_hypertext_model()  # TODO: add xref as hyperlink element
    # NOTE: open issue whether xref should be allowed in preformatted
    preformatted = TextElementModel({'code': 'pre', 'preformat': 'pre'}, hypertext)

    # https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/p-elements.html
    # %p-elements
    p_elements = UnionModel[Element]()
    p_elements |= hypertext
    p_elements |= preformatted
    p_elements |= ListModel(p_elements)
    return p_elements


def table_wrap_model(p_elements: EModel) -> EModel:
    th = TableCellModel(p_elements, header=True)
    td = TableCellModel(p_elements, header=False)
    tr = HtmlDataElementModel('tr', th | td)
    thead = HtmlDataElementModel('thead', tr)
    tbody = HtmlDataElementModel('tbody', tr)
    table = HtmlDataElementModel('table', thead | tbody)
    return DataElementModel('table-wrap', table)


def disp_quote_model(p_elements: EModel) -> EModel:
    p = TextElementModel({'p': 'p'}, p_elements)
    ret =  HtmlDataElementModel('disp-quote', p)
    ret.html = StartTag('blockquote')
    return ret


def p_level_model(p_elements: EModel) -> EModel:
    hypertext = base_hypertext_model()
    p_level = UnionModel[Element]()
    p_level |= TextElementModel({'p': 'p'}, p_elements)
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
    dest.license_ref = kit.load_string(log, e, ['content-type'])
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
    ap.once(hypertext_element_binder('license-p'), ret.license_p)
    ap.once(ReaderBinder(f"{ali}license_ref", read_license_ref), ret)
    ap.parse_array_content(e)
    return None if ret.blank() else ret


def load_permissions(log: IssueCallback, e: etree._Element) -> bp.Permissions | None:
    kit.check_no_attrib(log, e)
    ap = ContentParser(log)
    statement = ap.one(mixed_element_model('copyright-statement'))
    license = ap.one(LoaderModel("license", load_license))
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
    authors = cp.one(LoaderModel('contrib-group', load_author_group))
    cp.once(proto_section_binder('abstract', p_elements), dest.abstract)
    permissions = cp.one(LoaderModel('permissions', load_permissions))
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
    cp.once(ReaderBinder('article-meta', read_article_meta), dest)
    cp.parse_array_content(e)
    return True


def read_element_citation(
    log: IssueCallback, e: etree._Element, dest: bp.BiblioReference
) -> bool:
    kit.check_no_attrib(log, e, ['publication-type'])
    ap = ContentParser(log)
    title = ap.one(title_model('article-title'))
    authors = ap.one(ref_authors_model())
    year = ap.one(LoaderModel('year', kit.load_year))
    fields = {}
    for key in bp.BiblioReference.BIBLIO_FIELD_KEYS:
        fields[key] = ap.one(LoaderModel(key, kit.load_string))
    ap.parse_array_content(e)
    dest.publication_type = e.get('publication-type', '')
    if dest.publication_type not in [
        'book',
        'confproc',
        'journal',
        'other',
        'patent',
        'webpage',
    ]:
        log(
            fc.UnsupportedAttributeValue.issue(
                 e, 'publication-type', dest.publication_type
            )
        )
    dest.article_title = title.out
    if authors.out:
        dest.authors = authors.out
    dest.year = year.out
    for key, parser in fields.items():
        if parser.out:
            dest.biblio_fields[key] = parser.out
    return True


def load_biblio_ref(log: IssueCallback, e: etree._Element) -> bp.BiblioReference | None:
    ret = bp.BiblioReference()
    kit.check_no_attrib(log, e, ['id'])
    cp = ContentParser(log)
    cp.once(ReaderBinder('element-citation', read_element_citation), ret)
    cp.parse_array_content(e)
    ret.id = e.attrib.get('id', "")
    return ret


class RefListModel(BaseModel[bp.RefList]):
    def __init__(self) -> None:
        super().__init__('ref-list')

    def load(self, log: IssueCallback, e: etree._Element) -> bp.RefList | None:
        kit.check_no_attrib(log, e)
        cp = ContentParser(log)
        title = cp.one(title_model('title'))
        references = cp.every(LoaderModel('ref', load_biblio_ref))
        cp.parse_array_content(e)
        return bp.RefList(title.out, list(references))


def load_article(log: IssueCallback , e: etree._Element) -> bp.Baseprint | None:
    lang = '{http://www.w3.org/XML/1998/namespace}lang'
    kit.confirm_attrib_value(log, e, lang, ['en', None])
    kit.check_no_attrib(log, e, [lang])
    ret = bp.Baseprint()
    back = e.find("back")
    if back is not None:
        ret.ref_list = kit.load_single_sub_element(log, back, RefListModel())
        e.remove(back)
    cp = ContentParser(log)
    cp.bind_reader('front', read_article_front, ret)
    cp.bind(proto_section_binder('body', p_elements_model()), ret.body)
    cp.parse_array_content(e)
    if ret.title.blank():
        log(fc.FormatIssue(fc.MissingContent('article-title', 'title-group')))
    if not len(ret.authors):
        log(fc.FormatIssue(fc.MissingContent('contrib', 'contrib-group')))
    if ret.abstract.has_no_content():
        log(fc.FormatIssue(fc.MissingContent('abstract', 'article-meta')))
    if ret.body.has_no_content():
        log(fc.FormatIssue(fc.MissingContent('body', 'article')))
    return ret
