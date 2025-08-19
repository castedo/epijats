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
)

from . import kit
from .content import (
    ArrayContentSession,
    ContentBinder,
    ContentInElementModel,
    MergedElementsContentBinder,
)
from .kit import (
    Log,
    Model,
    TagModelBase,
    UnionModel,
    tag_model,
)
from .htmlish import (
    ExtLinkModel,
    ListModel,
    HtmlParagraphModel,
    break_model,
    def_list_model,
    disp_quote_model,
    formatted_text_model,
    table_wrap_model,
)
from .tree import (
    EmptyElementModel,
    MixedContentModel,
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

    def load(self, log: Log, e: XmlElement) -> Citation | None:
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

    def load(self, log: Log, e: XmlElement) -> CitationTuple | None:
        citation = self._submodel.load(log, e)
        if citation:
            return CitationTuple([citation])
        else:
            return None


class CitationRangeHelper:
    def __init__(self, log: Log, biblio: BiblioRefPool):
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


class CitationTupleModel(kit.LoadModel[Element]):
    def __init__(self, biblio: BiblioRefPool):
        super().__init__()
        self._submodel = CitationModel(biblio)

    def match(self, xe: XmlElement) -> bool:
        if xe.tag == 'sup':
            if any(c.tag == 'xref' and c.attrib.get('ref-type') == 'bibr' for c in xe):
                return True
        return False

    def load(self, log: Log, e: XmlElement) -> Element | None:
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
    def __init__(self, content_model: Model[Element]):
        super().__init__('xref')
        self.content_model = content_model

    def load(self, log: Log, e: XmlElement) -> Element | None:
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
            log(fc.InvalidAttributeValue.issue(e, 'ref-type', 'bibr'))
            warn("CitationModel not handling xref ref-type bibr")
        ret = bp.CrossReference(rid, ref_type)
        parse_mixed_content(log, e, self.content_model, ret.content)
        return ret


def article_title_model() -> kit.MonoModel[MixedContent]:
    """
    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/article-title.html
    """
    return MixedContentModel('article-title', base_hypertext_model())


def title_model(hypertext: Model[Element] | None = None) -> kit.MonoModel[MixedContent]:
    """
    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/title.html
    """
    if hypertext is None:
        hypertext = base_hypertext_model()
    child_model = hypertext | break_model()
    return MixedContentModel('title', child_model)


def hypertext_element_model(tag: str) -> kit.MonoModel[MixedContent]:
    return MixedContentModel(tag, base_hypertext_model())


def title_group_model() -> Model[MixedContent]:
    content = MergedElementsContentBinder(article_title_model())
    return ContentInElementModel('title-group', content)


def orcid_model() -> Model[bp.Orcid]:
    return tag_model('contrib-id', load_orcid)


def load_orcid(log: Log, e: XmlElement) -> bp.Orcid | None:
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


def load_author_group(log: Log, e: XmlElement) -> list[bp.Author] | None:
    kit.check_no_attrib(log, e)
    kit.check_required_child(log, e, 'contrib')
    sess = ArrayContentSession(log)
    ret = sess.every(tag_model('contrib', load_author))
    sess.parse_content(e)
    return list(ret)


def person_name_model() -> Model[bp.PersonName]:
    return tag_model('name', load_person_name)


def load_person_name(log: Log, e: XmlElement) -> bp.PersonName | None:
    kit.check_no_attrib(log, e)
    sess = ArrayContentSession(log)
    surname = sess.one(tag_model('surname', kit.load_string))
    given_names = sess.one(tag_model('given-names', kit.load_string))
    suffix = sess.one(tag_model('suffix', kit.load_string))
    sess.parse_content(e)
    if not surname.out and not given_names.out:
        log(fc.MissingContent.issue(e, "Missing surname or given-names element."))
        return None
    return bp.PersonName(surname.out, given_names.out, suffix.out)


def load_author(log: Log, e: XmlElement) -> bp.Author | None:
    if e.tag != 'contrib':
        return None
    if not kit.confirm_attrib_value(log, e, 'contrib-type', ['author']):
        return None
    kit.check_no_attrib(log, e, ['contrib-type'])
    sess = ArrayContentSession(log)
    name = sess.one(person_name_model())
    email = sess.one(tag_model('email', kit.load_string))
    orcid = sess.one(orcid_model())
    sess.parse_content(e)
    if name.out is None:
        log(fc.MissingContent.issue(e, "Missing name"))
        return None
    return bp.Author(name.out, email.out, orcid.out)


class ProtoSectionBinder(ContentBinder[bp.ProtoSection]):
    def __init__(self, hypertext_model: Model[Element]):
        super().__init__(bp.ProtoSection)
        self.hypertext_model = hypertext_model

    def binds(self, sess: ArrayContentSession, target: bp.ProtoSection) -> None:
        p_level = p_level_model(self.hypertext_model)
        sess.bind(p_level, target.presection.append)
        sess.bind(SectionModel(self.hypertext_model), target.subsections.append)


def abstract_model(biblio: BiblioRefPool | None) -> kit.MonoModel[bp.ProtoSection]:
    """<abstract> Abstract

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/abstract.html
    """

    content = ProtoSectionBinder(base_hypertext_model(biblio))
    return ContentInElementModel('abstract', content)


class SectionModel(TagModelBase[bp.Section]):
    """<sec> Section
    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/sec.html
    """

    def __init__(self, hypertext_model: Model[Element]):
        super().__init__('sec')
        self._title_model = title_model(hypertext_model)
        self._proto = ProtoSectionBinder(hypertext_model)

    def load(self, log: Log, e: XmlElement) -> bp.Section | None:
        kit.check_no_attrib(log, e, ['id'])
        ret = bp.Section([], [], e.attrib.get('id'), MixedContent())
        sess = ArrayContentSession(log)
        self._proto.binds(sess, ret)
        sess.bind_mono(self._title_model, ret.title)
        sess.parse_content(e)
        title_element = e.find('title')
        if title_element is None:
            log(fc.MissingChild.issue(e, 'title'))
        elif ret.title.blank():
            log(fc.MissingContent.issue(title_element))
        return ret


class PersonGroupModel(TagModelBase[bp.PersonGroup]):
    """<person-group> Person Group for a Cited Publication
    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/person-group.html
    """

    def __init__(self, group_type: str) -> None:
        super().__init__(StartTag('person-group', {'person-group-type': group_type}))

    def load(self, log: Log, e: XmlElement) -> bp.PersonGroup | None:
        ret = bp.PersonGroup()
        k = 'person-group-type'
        kit.check_no_attrib(log, e, [k])
        sess = ArrayContentSession(log)
        sess.bind(tag_model('name', load_person_name), ret.persons.append)
        sess.bind(tag_model('string-name', kit.load_string), ret.persons.append)
        etal = sess.one(EmptyElementModel('etal'))
        sess.parse_content(e)
        ret.etal = bool(etal.out)
        return ret


def base_hypertext_model(biblio: BiblioRefPool | None = None) -> Model[Element]:
    """Base hypertext model"""

    only_formatted_text = UnionModel[Element]()
    only_formatted_text |= formatted_text_model(only_formatted_text)

    hypertext = UnionModel[Element]()
    if biblio:
        hypertext |= AutoCorrectCitationModel(biblio)
        hypertext |= CitationTupleModel(biblio)
    hypertext |= ExtLinkModel(only_formatted_text)
    hypertext |= CrossReferenceModel(only_formatted_text)
    hypertext |= inline_formula_model()
    hypertext |= formatted_text_model(hypertext)
    return hypertext


class CoreModels:
    def __init__(self, hypertext_model: Model[Element] | None) -> None:
        if hypertext_model is None:
            hypertext_model = base_hypertext_model()
        self.hypertext = hypertext_model
        self.block = UnionModel[Element]()
        self.p_child = self.hypertext | self.block
        self.block |= disp_formula_model()
        self.block |= TextElementModel({'code', 'preformat'}, self.hypertext)
        self.block |= ListModel(self.hypertext, self.block)
        self.block |= def_list_model(self.hypertext, self.block)
        self.block |= disp_quote_model(self.p_child)
        self.block |= table_wrap_model(self.p_child)


def p_child_model(hypertext: Model[Element] | None = None) -> Model[Element]:
    """Paragraph (child) elements (subset of Article Authoring JATS)
    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/p-elements.html
    """

    models = CoreModels(hypertext)
    return models.p_child


def p_level_model(hypertext: Model[Element]) -> Model[Element]:
    """Paragraph-level elements (subset of Article Authoring JATS)
    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/para-level.html
    """

    models = CoreModels(hypertext)
    return models.block | HtmlParagraphModel(hypertext, models.block)


CC_URLS = {
    'https://creativecommons.org/publicdomain/zero/': bp.CcLicenseType.CC0,
    'https://creativecommons.org/licenses/by/': bp.CcLicenseType.BY,
    'https://creativecommons.org/licenses/by-sa/': bp.CcLicenseType.BYSA,
    'https://creativecommons.org/licenses/by-nc/': bp.CcLicenseType.BYNC,
    'https://creativecommons.org/licenses/by-nc-sa/': bp.CcLicenseType.BYNCSA,
    'https://creativecommons.org/licenses/by-nd/': bp.CcLicenseType.BYND,
    'https://creativecommons.org/licenses/by-nc-nd/': bp.CcLicenseType.BYNCND,
}


class LicenseRefBinder(kit.TagBinderBase[bp.License]):
    TAG = "{http://www.niso.org/schemas/ali/1.0/}license_ref"

    def read(self, log: Log, xe: XmlElement, dest: bp.License) -> None:
        kit.check_no_attrib(log, xe, ['content-type'])
        dest.license_ref = kit.load_string_content(log, xe)
        got_license_type = kit.get_enum_value(log, xe, 'content-type', bp.CcLicenseType)
        for prefix, matching_type in CC_URLS.items():
            if dest.license_ref.startswith(prefix):
                if got_license_type and got_license_type != matching_type:
                    issue = fc.InvalidAttributeValue.issue
                    log(issue(xe, 'content-type', got_license_type))
                dest.cc_license_type = matching_type
                return
        dest.cc_license_type = got_license_type


class LicenseModel(kit.TagModelBase[bp.License]):
    TAG = 'license'

    def load(self, log: Log, e: XmlElement) -> bp.License | None:
        ret = bp.License(MixedContent(), "", None)
        kit.check_no_attrib(log, e)
        sess = ArrayContentSession(log)
        sess.bind_mono(hypertext_element_model('license-p'), ret.license_p)
        sess.bind_once(LicenseRefBinder(), ret)
        sess.parse_content(e)
        return None if ret.blank() else ret


class PermissionsModel(kit.TagModelBase[bp.Permissions]):
    TAG = 'permissions'

    def load(self, log: Log, e: XmlElement) -> bp.Permissions | None:
        kit.check_no_attrib(log, e)
        sess = ArrayContentSession(log)
        statement = sess.one(hypertext_element_model('copyright-statement'))
        license = sess.one(LicenseModel())
        sess.parse_content(e)
        if license.out is None:
            return None
        if statement.out and not statement.out.blank():
            copyright = bp.Copyright(statement.out)
        else:
            copyright = None
        return bp.Permissions(license.out, copyright)


class ArticleMetaBinder(kit.TagBinderBase[bp.Baseprint]):
    def __init__(self, biblio: BiblioRefPool | None):
        super().__init__('article-meta')
        self._abstract_model = abstract_model(biblio)

    def read(self, log: Log, xe: XmlElement, dest: bp.Baseprint) -> None:
        kit.check_no_attrib(log, xe)
        kit.check_required_child(log, xe, 'title-group')
        sess = ArrayContentSession(log)
        title = sess.one(title_group_model())
        authors = sess.one(tag_model('contrib-group', load_author_group))
        abstract = bp.ProtoSection()
        sess.bind_mono(self._abstract_model, abstract)
        permissions = sess.one(PermissionsModel())
        sess.parse_content(xe)
        if title.out:
            dest.title = title.out
        if authors.out is not None:
            dest.authors = authors.out
        if abstract.has_content():
            dest.abstract = abstract
        if permissions.out is not None:
            dest.permissions = permissions.out


class ArticleFrontBinder(kit.TagBinderBase[bp.Baseprint]):
    def __init__(self, biblio: BiblioRefPool | None):
        super().__init__('front')
        self._meta_model = ArticleMetaBinder(biblio)

    def read(self, log: Log, xe: XmlElement, dest: bp.Baseprint) -> None:
        kit.check_no_attrib(log, xe)
        kit.check_required_child(log, xe, 'article-meta')
        sess = ArrayContentSession(log)
        sess.bind_once(self._meta_model, dest)
        sess.parse_content(xe)


def body_model(biblio: BiblioRefPool | None) -> kit.MonoModel[bp.ProtoSection]:
    """<body> Body of the Document

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/body.html
    """

    hypertext = base_hypertext_model(biblio)
    content = ProtoSectionBinder(hypertext)
    return ContentInElementModel('body', content)


class PositiveIntModel(TagModelBase[int]):
    def __init__(self, tag: str, max_int: int, *, strip_trailing_period: bool = False):
        super().__init__(tag)
        self.max_int = max_int
        self.strip_trailing_period = strip_trailing_period

    def load(self, log: Log, e: XmlElement) -> int | None:
        kit.check_no_attrib(log, e)
        ret = kit.load_int(log, e, strip_trailing_period=self.strip_trailing_period)
        if ret and ret not in range(1, self.max_int + 1):
            log(fc.UnsupportedAttributeValue.issue(e, self.tag, str(ret)))
            ret = None
        return ret


class DateBuilder:
    def __init__(self, sess: ArrayContentSession):
        self.year = sess.one(tag_model('year', kit.load_int))
        self.month = sess.one(PositiveIntModel('month', 12))
        self.day = sess.one(PositiveIntModel('day', 31))

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

    def load(self, log: Log, xe: XmlElement) -> bp.Date | None:
        kit.check_no_attrib(log, xe, ['content-type'])
        if xe.attrib.get('content-type') != 'access-date':
            return None
        sess = ArrayContentSession(log)
        date = DateBuilder(sess)
        sess.parse_content(xe)
        return date.build()


class PubIdBinder(kit.TagBinderBase[dict[bp.PubIdType, str]]):
    """<pub-id> Publication Identifier for a Cited Publication

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/pub-id.html
    """

    TAG = 'pub-id'

    def read(self, log: Log, e: XmlElement, dest: dict[bp.PubIdType, str]) -> None:
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


def load_edition(log: Log, e: XmlElement) -> int | None:
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


class ElementCitationBinder(kit.TagBinderBase[bp.BiblioRefItem]):
    """<element-citation> Element Citation

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/element-citation.html
    """

    TAG = 'element-citation'

    def read(self, log: Log, e: XmlElement, dest: bp.BiblioRefItem) -> None:
        kit.check_no_attrib(log, e)
        sess = ArrayContentSession(log)
        source = sess.one(tag_model('source', kit.load_string))
        title = sess.one(tag_model('article-title', kit.load_string))
        authors = sess.one(PersonGroupModel('author'))
        editors = sess.one(PersonGroupModel('editor'))
        edition = sess.one(tag_model('edition', load_edition))
        date = DateBuilder(sess)
        access_date = sess.one(AccessDateModel())
        fields = {}
        for key in bp.BiblioRefItem.BIBLIO_FIELD_KEYS:
            fields[key] = sess.one(tag_model(key, kit.load_string))
        sess.bind(PubIdBinder(), dest.pub_ids)
        sess.parse_content(e)
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
        if 'elocation-id' in dest.biblio_fields and 'fpage' in dest.biblio_fields:
            msg = "fpage field might prevent display of elocation-id or vice-versa"
            log(fc.ElementFormatCondition.issue(e, msg))


class BiblioRefItemModel(TagModelBase[bp.BiblioRefItem]):
    """<ref> Reference Item

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/ref.html
    """

    def __init__(self) -> None:
        super().__init__('ref')

    def load(self, log: Log, xe: XmlElement) -> bp.BiblioRefItem | None:
        ret = bp.BiblioRefItem()
        kit.check_no_attrib(log, xe, ['id'])
        sess = ArrayContentSession(log)
        label = PositiveIntModel('label', 1048576, strip_trailing_period=True)
        sess.one(label)  # ignoring if it's a valid integer
        sess.bind_once(ElementCitationBinder(), ret)
        sess.parse_content(xe)
        ret.id = xe.attrib.get('id', "")
        return ret


class RefListModel(TagModelBase[bp.BiblioRefList]):
    def __init__(self) -> None:
        super().__init__('ref-list')

    def load(self, log: Log, e: XmlElement) -> bp.BiblioRefList | None:
        kit.check_no_attrib(log, e)
        sess = ArrayContentSession(log)
        title = sess.one(title_model())
        references = sess.every(BiblioRefItemModel())
        sess.parse_content(e)
        return bp.BiblioRefList(title.out, list(references))


def pop_load_sub_back(log: Log, xe: XmlElement) -> bp.BiblioRefList | None:
    back = xe.find("back")
    if back is None:
        return None
    kit.check_no_attrib(log, back)
    sess = ArrayContentSession(log)
    result = sess.one(RefListModel())
    sess.parse_content(back)
    xe.remove(back)  # type: ignore[arg-type]
    return result.out


def load_article(log: Log, e: XmlElement) -> bp.Baseprint | None:
    """Loader function for <article>

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/article.html
    """
    lang = '{http://www.w3.org/XML/1998/namespace}lang'
    kit.confirm_attrib_value(log, e, lang, ['en', None])
    kit.check_no_attrib(log, e, [lang])
    ret = bp.Baseprint()
    back_log = list[fc.FormatIssue]()
    ret.ref_list = pop_load_sub_back(back_log.append, e)
    biblio = BiblioRefPool(ret.ref_list.references) if ret.ref_list else None
    kit.check_required_child(log, e, 'front')
    sess = ArrayContentSession(log)
    sess.bind_once(ArticleFrontBinder(biblio), ret)
    sess.bind_mono(body_model(biblio), ret.body)
    sess.parse_content(e)
    if ret.ref_list:
        assert biblio
        ret.ref_list.references = biblio.used
    if ret.title.blank():
        log(fc.FormatIssue(fc.MissingContent('article-title', 'title-group')))
    if not ret.body.has_content():
        log(fc.FormatIssue(fc.MissingContent('body', 'article')))
    for issue in back_log:
        log(issue)
    return ret
