from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING
from warnings import warn

from .. import baseprint as bp
from .. import condition as fc
from ..tree import (
    Citation,
    CitationTuple,
    Element,
    MixedContent,
    StartTag,
    make_paragraph,
)

from . import kit
from .kit import (
    TagModelBase,
    Binder,
    ContentParser,
    IssueCallback,
    tag_model,
    Model,
    Parser,
    Sink,
    UnionModel,
)
from .htmlish import (
    ExtLinkModel,
    ListModel,
    break_model,
    def_list_model,
    disp_quote_model,
    formatted_text_model,
    table_wrap_model,
)
from .tree import (
    EModel,
    MixedContentBinder,
    MixedContentLoader,
    TextElementModel,
    parse_mixed_content,
)
from .math import disp_formula_model, inline_formula_model

if TYPE_CHECKING:
    from ..xml import XmlElement


class BiblioRefPool:
    def __init__(self, orig: Iterable[bp.BiblioRefItem]):
        self._orig = list(orig)
        self.used: list[bp.BiblioRefItem] = []
        self._orig_order = True

    def cite(self, rid: str, ideal_rord: int | None) -> Citation | None:
        for zidx, ref in enumerate(self.used):
            if rid == ref.id:
                return Citation(rid, zidx + 1)
        for zidx, ref in enumerate(self._orig):
            if rid == ref.id:
                if self._orig_order:
                    if zidx + 1 == ideal_rord:
                        for j in range(len(self.used), zidx):
                            self.used.append(self._orig[j])
                    else:
                        self._orig_order = False
                self.used.append(ref)
                return Citation(rid, len(self.used))
        return None

    def get_by_rord(self, rord: int) -> bp.BiblioRefItem:
        """Get using one-based index of 'rord' value"""

        return self.used[rord - 1]

    def inner_range(self, before: Citation, after: Citation) -> Iterator[Citation]:
        for rord in range(before.rord + 1, after.rord):
            rid = self.get_by_rord(rord).id
            yield Citation(rid, rord)


class CitationModel(kit.TagModelBase[Citation]):
    def __init__(self, biblio: BiblioRefPool):
        super().__init__(StartTag('xref', {'ref-type': 'bibr'}))
        self.biblio = biblio

    def load(self, log: IssueCallback, e: XmlElement) -> Citation | None:
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
        try:
            rord = int(e.text or '')
        except ValueError:
            rord = None
        ret = self.biblio.cite(rid, rord)
        if not ret:
            log(fc.InvalidCitation.issue(e, rid))
        elif e.text and not ret.matching_text(e.text):
            log(fc.IgnoredText.issue(e))
        return ret


class AutoCorrectCitationModel(kit.TagModelBase[Element]):
    def __init__(self, biblio: BiblioRefPool):
        submodel = CitationModel(biblio)
        super().__init__(submodel.stag)
        self._submodel = submodel

    def load(self, log: IssueCallback, e: XmlElement) -> CitationTuple | None:
        citation = self._submodel.load(log, e)
        if citation:
            return CitationTuple([citation])
        else:
            return None


class CitationRangeHelper:
    def __init__(self, log: IssueCallback, biblio: BiblioRefPool):
        self.log = log
        self._biblio = biblio
        self.starter: Citation | None = None
        self.stopper: Citation | None = None

    @staticmethod
    def is_tuple_open(text: str | None) -> bool:
        delim = text.strip() if text else ''
        return delim in {'', '[', '('}

    def get_range(self, child: XmlElement, citation: Citation) -> Iterator[Citation]:
        if citation.matching_text(child.text):
            self.stopper = citation
        if self.starter:
            if self.stopper:
                return self._biblio.inner_range(self.starter, self.stopper)
            else:
                msg = f"Invalid citation '{citation.rid}' to end range"
                self.log(fc.InvalidCitation.issue(child, msg))
        return iter(())

    def new_start(self, child: XmlElement) -> None:
        delim = child.tail.strip() if child.tail else ''
        if delim in {'-', '\u2010', '\u2011', '\u2012', '\u2013', '\u2014'}:
            self.starter = self.stopper
            if not self.starter:
                msg = "Invalid citation to start range"
                self.log(fc.InvalidCitation.issue(child, msg))
        else:
            self.starter = None
            if delim not in {'', ',', ';', ']', ')'}:
                self.log(fc.IgnoredTail.issue(child))
        self.stopper = None


class CitationTupleModel(kit.ModelBase[Element]):
    def __init__(self, biblio: BiblioRefPool):
        super().__init__()
        self._submodel = CitationModel(biblio)

    def match(self, xe: XmlElement) -> bool:
        if xe.tag == 'sup':
            if any(c.tag == 'xref' and c.attrib.get('ref-type') == 'bibr' for c in xe):
                return True
        return False

    def load(self, log: IssueCallback, e: XmlElement) -> Element | None:
        kit.check_no_attrib(log, e)
        range_helper = CitationRangeHelper(log, self._submodel.biblio)
        if not range_helper.is_tuple_open(e.text):
            log(fc.IgnoredText.issue(e))
        ret = CitationTuple()
        for child in e:
            citation = self._submodel.load_if_match(log, child)
            if citation is None:
                log(fc.UnsupportedElement.issue(child))
            else:
                ret.extend(range_helper.get_range(child, citation))
                citation.tail = ''
                ret.append(citation)
            range_helper.new_start(child)
        return ret if len(ret) else None


class CrossReferenceModel(kit.TagModelBase[Element]):
    def __init__(self, content_model: EModel):
        super().__init__('xref')
        self.content_model = content_model

    def load(self, log: IssueCallback, e: XmlElement) -> Element | None:
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


def mixed_element_model(tag: str) -> Model[MixedContent]:
    return tag_model(tag, MixedContentLoader(base_hypertext_model()))


def title_model(tag: str) -> Model[MixedContent]:
    content_model = base_hypertext_model() | break_model()
    return tag_model(tag, MixedContentLoader(content_model))


def hypertext_element_binder(tag: str) -> Binder[MixedContent]:
    return MixedContentBinder(tag, base_hypertext_model())


title_binder = hypertext_element_binder


def title_group_model() -> Model[MixedContent]:
    loader = kit.SingleSubElementLoader(title_model('article-title'))
    return tag_model('title-group', loader)


def orcid_model() -> Model[bp.Orcid]:
    return tag_model('contrib-id', load_orcid)


def load_orcid(log: IssueCallback, e: XmlElement) -> bp.Orcid | None:
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


def load_author_group(log: IssueCallback, e: XmlElement) -> list[bp.Author] | None:
    kit.check_no_attrib(log, e)
    acp = ContentParser(log)
    ret = acp.every(tag_model('contrib', load_author))
    acp.parse_array_content(e)
    return list(ret)


def person_name_model() -> Model[bp.PersonName]:
    return tag_model('name', load_person_name)


def load_person_name(log: IssueCallback, e: XmlElement) -> bp.PersonName | None:
    kit.check_no_attrib(log, e)
    p = ContentParser(log)
    surname = p.one(tag_model('surname', kit.load_string))
    given_names = p.one(tag_model('given-names', kit.load_string))
    p.parse_array_content(e)
    if not surname.out and not given_names.out:
        log(fc.MissingContent.issue(e))
        return None
    return bp.PersonName(surname.out, given_names.out)


def load_author(log: IssueCallback, e: XmlElement) -> bp.Author | None:
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

    def match(self, xe: XmlElement) -> kit.ParseFunc | None:
        return self._parser.match(xe)


class ProtoSectionContentBinder(Binder[bp.ProtoSection]):
    def __init__(self, p_elements: Model[Element], p_level: Model[Element]):
        self.p_elements = p_elements
        self.p_level = p_level

    def bind(self, log: IssueCallback, dest: bp.ProtoSection) -> Parser:
        ret = ContentParser(log)
        ret.bind(self.p_level, dest.presection.append)
        ret.bind(AutoCorrectModel(self.p_elements), dest.presection.append)
        ret.bind(SectionModel(self.p_elements), dest.subsections.append)
        return ret


class AbstractModel(TagModelBase[bp.Abstract]):
    """<abstract> Abstract

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/abstract.html
    """
    def __init__(self) -> None:
        super().__init__('abstract')
        p_child = p_child_model()
        just_para = TextElementModel({'p'}, p_child)
        self._content = ProtoSectionContentBinder(p_child, just_para)

    def load(self, log: IssueCallback, e: XmlElement) -> bp.Abstract | None:
        ret = bp.Abstract()
        cp = ContentParser(log)
        cp.bind(self._content, ret)
        cp.parse_array_content(e)
        return ret


class SectionModel(TagModelBase[bp.Section]):
    """<sec> Section
    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/sec.html
    """

    def __init__(self, p_elements: EModel):
        super().__init__('sec')
        p_level = p_level_model(p_elements)
        self._proto = ProtoSectionContentBinder(p_elements, p_level)

    def load(self, log: IssueCallback, e: XmlElement) -> bp.Section | None:
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
        super().__init__(StartTag('person-group', {'person-group-type': group_type}))

    def load(
        self, log: IssueCallback, e: XmlElement
    ) -> list[bp.PersonName | str] | None:
        ret: list[bp.PersonName | str] = []
        k = 'person-group-type'
        kit.check_no_attrib(log, e, [k])
        cp = ContentParser(log)
        cp.bind(tag_model('name', load_person_name), ret.append)
        cp.bind(tag_model('string-name', kit.load_string), ret.append)
        cp.parse_array_content(e)
        return ret


def base_hypertext_model() -> EModel:
    """Base hypertext model"""

    only_formatted_text = UnionModel[Element]()
    only_formatted_text |= formatted_text_model(only_formatted_text)

    hypertext = UnionModel[Element]()
    hypertext |= ExtLinkModel(only_formatted_text)
    hypertext |= CrossReferenceModel(only_formatted_text)
    hypertext |= inline_formula_model()
    hypertext |= formatted_text_model(hypertext)
    return hypertext


def p_child_model(biblio: BiblioRefPool | None = None) -> EModel:
    """Paragraph (child) elements (subset of Article Authoring JATS)
    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/p-elements.html
    """
    hypertext = base_hypertext_model()
    # NOTE: open issue whether xref should be allowed in preformatted
    preformatted = TextElementModel({'code', 'preformat'}, hypertext)

    # https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/p-elements.html
    # %p-elements
    p_elements = UnionModel[Element]()
    if biblio:
        p_elements |= AutoCorrectCitationModel(biblio)
        p_elements |= CitationTupleModel(biblio)
    p_elements |= hypertext
    p_elements |= disp_formula_model()
    p_elements |= preformatted
    p_elements |= ListModel(p_elements)
    p_elements |= def_list_model(hypertext, p_elements)
    p_elements |= disp_quote_model(p_elements)
    p_elements |= table_wrap_model(p_elements)
    return p_elements


def p_level_model(p_elements: EModel) -> EModel:
    """Paragraph-level elements (subset of Article Authoring JATS)
    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/para-level.html
    """
    hypertext = base_hypertext_model()
    p_level = UnionModel[Element]()
    p_level |= TextElementModel({'p'}, p_elements)
    p_level |= disp_formula_model()
    p_level |= TextElementModel({'code', 'preformat'}, hypertext)
    p_level |= ListModel(p_elements)
    p_level |= disp_quote_model(p_elements)
    p_level |= table_wrap_model(p_elements)
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


class LicenseRefBinder(kit.Reader[bp.License]):
    TAG = "{http://www.niso.org/schemas/ali/1.0/}license_ref"

    def read(
        self, log: IssueCallback, xe: XmlElement, dest: bp.License
    ) -> None:
        kit.check_no_attrib(log, xe, ['content-type'])
        dest.license_ref = kit.load_string_content(log, xe)
        got_license_type = kit.get_enum_value(log, xe, 'content-type', bp.CcLicenseType)
        for prefix, matching_type in CC_URLS.items():
            if dest.license_ref.startswith(prefix):
                if got_license_type and got_license_type != matching_type:
                    log(fc.InvalidAttributeValue.issue(
                        xe, 'content-type', got_license_type
                    ))
                dest.cc_license_type = matching_type
                return
        dest.cc_license_type = got_license_type


def load_license(log: IssueCallback, e: XmlElement) -> bp.License | None:
    ret = bp.License(MixedContent(), "", None)
    kit.check_no_attrib(log, e)
    ap = ContentParser(log)
    ap.bind(hypertext_element_binder('license-p').once(), ret.license_p)
    ap.bind(LicenseRefBinder().once(), ret)
    ap.parse_array_content(e)
    return None if ret.blank() else ret


def load_permissions(log: IssueCallback, e: XmlElement) -> bp.Permissions | None:
    kit.check_no_attrib(log, e)
    ap = ContentParser(log)
    statement = ap.one(mixed_element_model('copyright-statement'))
    license = ap.one(tag_model("license", load_license))
    ap.parse_array_content(e)
    if license.out is None:
        return None
    if statement.out and not statement.out.blank():
        copyright = bp.Copyright(statement.out)
    else:
        copyright = None
    return bp.Permissions(license.out, copyright)


class ArticleMetaBinder(kit.Reader[bp.Baseprint]):
    TAG = 'article-meta'

    def read(self, log: IssueCallback, xe: XmlElement, dest: bp.Baseprint) -> None:
        kit.check_no_attrib(log, xe)
        cp = ContentParser(log)
        title = cp.one(title_group_model())
        authors = cp.one(tag_model('contrib-group', load_author_group))
        abstract = cp.one(AbstractModel())
        permissions = cp.one(tag_model('permissions', load_permissions))
        cp.parse_array_content(xe)
        if title.out:
            dest.title = title.out
        if authors.out is not None:
            dest.authors = authors.out
        if abstract.out is not None:
            dest.abstract = abstract.out
        if permissions.out is not None:
            dest.permissions = permissions.out


class ArticleFrontBinder(kit.Reader[bp.Baseprint]):
    TAG = 'front'

    def read(self, log: IssueCallback, e: XmlElement, dest: bp.Baseprint) -> None:
        kit.check_no_attrib(log, e)
        cp = ContentParser(log)
        cp.bind(ArticleMetaBinder().once(), dest)
        cp.parse_array_content(e)


def body_binder(biblio: BiblioRefPool | None) -> Binder[bp.ProtoSection]:
    """<body> Body of the Document

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/body.html
    """
    p_child = p_child_model(biblio)
    p_level = p_level_model(p_child)
    return kit.SingleElementBinder('body', ProtoSectionContentBinder(p_child, p_level))


class PositiveIntModel(TagModelBase[int]):
    def __init__(self, tag: str, max_int: int, *, strip_trailing_period: bool = False):
        super().__init__(tag)
        self.max_int = max_int
        self.strip_trailing_period = strip_trailing_period

    def load(self, log: IssueCallback, e: XmlElement) -> int | None:
        kit.check_no_attrib(log, e)
        ret = kit.load_int(log, e, strip_trailing_period=self.strip_trailing_period)
        if ret and ret not in range(1, self.max_int + 1):
            log(fc.UnsupportedAttributeValue.issue(e, self.tag, str(ret)))
            ret = None
        return ret


class DateBuilder:
    def __init__(self, cp: ContentParser):
        self.year = cp.one(tag_model('year', kit.load_int))
        self.month = cp.one(PositiveIntModel('month', 12))
        self.day = cp.one(PositiveIntModel('day', 31))

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

    def load(self, log: IssueCallback, e: XmlElement) -> bp.Date | None:
        kit.check_no_attrib(log, e, ['content-type'])
        if e.attrib.get('content-type') != 'access-date':
            return None
        cp = ContentParser(log)
        date = DateBuilder(cp)
        cp.parse_array_content(e)
        return date.build()


class PubIdBinder(kit.Reader[dict[bp.PubIdType, str]]):
    """<pub-id> Publication Identifier for a Cited Publication

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/pub-id.html
    """

    TAG = 'pub-id'

    def read(
        self, log: IssueCallback, e: XmlElement, dest: dict[bp.PubIdType, str]
    ) -> None:
        kit.check_no_attrib(log, e, ['pub-id-type'])
        pub_id_type = kit.get_enum_value(log, e, 'pub-id-type', bp.PubIdType)
        if not pub_id_type:
            return
        if pub_id_type in dest:
            log(fc.ExcessElement.issue(e))
            return
        value = kit.load_string_content(log, e)
        if not value:
            log(fc.MissingContent.issue(e))
            return
        match pub_id_type:
            case bp.PubIdType.DOI:
                if not value.startswith("10."):
                    log(fc.InvalidDoi.issue(e, "DOIs begin with '10.'"))
                    https_prefix = "https://doi.org/"
                    if value.startswith(https_prefix):
                        value = value[len(https_prefix) :]
                    else:
                        return
            case bp.PubIdType.PMID:
                try:
                    int(value)
                except ValueError as ex:
                    log(fc.InvalidPmid.issue(e, str(ex)))
                    return
        dest[pub_id_type] = value


def load_edition(log: IssueCallback, e: XmlElement) -> int | None:
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


class ElementCitationBinder(kit.Reader[bp.BiblioRefItem]):
    TAG = 'element-citation'

    def read(self, log: IssueCallback, e: XmlElement, dest: bp.BiblioRefItem) -> None:
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
        cp.bind(PubIdBinder(), dest.pub_ids)
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


class BiblioRefItemModel(TagModelBase[bp.BiblioRefItem]):
    """<ref> Reference Item

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/ref.html
    """

    def __init__(self) -> None:
        super().__init__('ref')

    def load(self, log: IssueCallback, e: XmlElement) -> bp.BiblioRefItem | None:
        ret = bp.BiblioRefItem()
        kit.check_no_attrib(log, e, ['id'])
        cp = ContentParser(log)
        label = PositiveIntModel('label', 1048576, strip_trailing_period=True)
        cp.one(label)  # ignoring if it's a valid integer
        cp.bind(ElementCitationBinder().once(), ret)
        cp.parse_array_content(e)
        ret.id = e.attrib.get('id', "")
        return ret


class RefListModel(TagModelBase[bp.BiblioRefList]):
    def __init__(self) -> None:
        super().__init__('ref-list')

    def load(self, log: IssueCallback, e: XmlElement) -> bp.BiblioRefList | None:
        kit.check_no_attrib(log, e)
        cp = ContentParser(log)
        title = cp.one(title_model('title'))
        references = cp.every(BiblioRefItemModel())
        cp.parse_array_content(e)
        return bp.BiblioRefList(title.out, list(references))


def load_article(log: IssueCallback, e: XmlElement) -> bp.Baseprint | None:
    """Loader function for <article>

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/article.html
    """
    lang = '{http://www.w3.org/XML/1998/namespace}lang'
    kit.confirm_attrib_value(log, e, lang, ['en', None])
    kit.check_no_attrib(log, e, [lang])
    ret = bp.Baseprint()
    back = e.find("back")
    back_log = list[fc.FormatIssue]()
    if back is not None:
        back_loader = kit.SingleSubElementLoader(RefListModel())
        ret.ref_list = back_loader(back_log.append, back)
        e.remove(back)  # type: ignore[arg-type]
    biblio = BiblioRefPool(ret.ref_list.references) if ret.ref_list else None
    cp = ContentParser(log)
    cp.bind(ArticleFrontBinder().once(), ret)
    cp.bind(body_binder(biblio), ret.body)
    cp.parse_array_content(e)
    if ret.ref_list:
        assert biblio
        ret.ref_list.references = biblio.used
    if ret.title.blank():
        log(fc.FormatIssue(fc.MissingContent('article-title', 'title-group')))
    if not len(ret.authors):
        log(fc.FormatIssue(fc.MissingContent('contrib', 'contrib-group')))
    if not ret.abstract or ret.abstract.has_no_content():
        log(fc.FormatIssue(fc.MissingContent('abstract', 'article-meta')))
    if ret.body.has_no_content():
        log(fc.FormatIssue(fc.MissingContent('body', 'article')))
    for issue in back_log:
        log(issue)
    return ret
