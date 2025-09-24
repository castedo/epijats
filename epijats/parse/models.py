from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING

from .. import baseprint as bp
from .. import condition as fc
from ..tree import (
    Citation,
    CitationTuple,
    Element,
    MixedContent,
)

from . import kit
from .content import (
    ArrayContentSession,
    ContentBinder,
    ContentInElementModel,
    ContentInElementModelBase,
    MergedElementsContentBinder,
)
from .kit import Log, Model, tag_model
from .htmlish import (
    HtmlParagraphModel,
    ListModel,
    break_model,
    def_list_model,
    blockquote_model,
    ext_link_model,
    formatted_text_model,
    minimally_formatted_text_model,
    table_wrap_model,
)
from .references import RefListModel, load_person_name
from .tree import (
    MixedContentModel,
    MixedContentModelBase,
    TextElementModel,
    parse_mixed_content,
)
from .math import disp_formula_model, inline_formula_model


if TYPE_CHECKING:
    from ..xml import XmlElement


def hypotext_model() -> Model[Element]:
    # Corresponds to {HYPOTEXT} in BpDF spec ed.2
    # https://perm.pub/DPRkAz3vwSj85mBCgG49DeyndaE/2
    ret = kit.UnionModel[Element]()
    ret |= formatted_text_model(ret)
    return ret


def copytext_model() -> Model[Element]:
    # Corresponds to {COPYTEXT} in BpDF spec ed.2
    ret = kit.UnionModel[Element]()
    ret |= formatted_text_model(ret)
    ret |= ext_link_model(hypotext_model())
    return ret


def copytext_element_model(tag: str) -> kit.MonoModel[MixedContent]:
    return MixedContentModel(tag, copytext_model())


def hypertext_model(biblio: BiblioRefPool | None) -> Model[Element]:
    # Corresponds to {HYPERTEXT} in BpDF spec ed.2
    # but with experimental inline math element too
    hypotext = hypotext_model()
    hypertext = kit.UnionModel[Element]()
    if biblio:
        # model for <sup>~CITE must preempt regular <sup> model
        hypertext |= AutoCorrectCitationModel(biblio)
        hypertext |= CitationTupleModel(biblio)
    hypertext |= formatted_text_model(hypertext)
    hypertext |= ext_link_model(hypotext)
    hypertext |= cross_reference_model(hypotext, biblio)
    hypertext |= inline_formula_model()
    return hypertext


class CoreModels:
    def __init__(self, biblio: BiblioRefPool | None) -> None:
        self.hypertext = hypertext_model(biblio)
        self.heading_text = self.hypertext | break_model()
        block = kit.UnionModel[Element]()
        p = HtmlParagraphModel(self.hypertext, block)
        self.p_level = block | p
        self.p_child = self.hypertext | block
        block |= disp_formula_model()
        block |= TextElementModel('code', self.hypertext)
        block |= TextElementModel('pre', self.hypertext, jats_tag='preformat')
        block |= ListModel(self.p_level)
        block |= def_list_model(self.hypertext, self.p_level)
        block |= blockquote_model(self.p_child)
        block |= table_wrap_model(self.p_child)


class BiblioRefPool:
    def __init__(self, orig: Iterable[bp.BiblioRefItem]):
        self._orig = list(orig)
        self.used: list[bp.BiblioRefItem] = []
        self._orig_order = True

    def is_bibr_rid(self, rid: str | None) -> bool:
        return bool(rid) and any(rid == ref.id for ref in self._orig)

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


class CitationModel(kit.LoadModel[Citation]):
    def __init__(self, biblio: BiblioRefPool):
        self.biblio = biblio

    def match(self, xe: XmlElement) -> bool:
        # JatsCrossReferenceModel is the opposing <xref> model to CitationModel
        if xe.tag != 'xref':
            return False
        if xe.attrib.get('ref-type') == 'bibr':
            return True
        return self.biblio.is_bibr_rid(xe.attrib.get("rid"))

    def load(self, log: Log, e: XmlElement) -> Citation | None:
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


class AutoCorrectCitationModel(kit.LoadModel[Element]):
    def __init__(self, biblio: BiblioRefPool):
        submodel = CitationModel(biblio)
        self._submodel = submodel

    def match(self, xe: XmlElement) -> bool:
        return self._submodel.match(xe)

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
        # Minor break of backwards compat to BpDF ed.1 where
        # xref inside sup might be what is now <a href="#...">
        # But no known archived baseprint did this.
        return xe.tag == 'sup' and any(c.tag == 'xref' for c in xe)

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


class JatsCrossReferenceModel(kit.LoadModel[Element]):
    def __init__(self, content_model: Model[Element], biblio: BiblioRefPool | None):
        self.content_model = content_model
        self.biblio = biblio

    def match(self, xe: XmlElement) -> bool:
        # CitationModel is the opposing <xref> model to JatsCrossReferenceModel
        if xe.tag != 'xref':
            return False
        if xe.attrib.get('ref-type') == 'bibr':
            return False
        return not (self.biblio and self.biblio.is_bibr_rid(xe.attrib.get("rid")))

    def load(self, log: Log, e: XmlElement) -> Element | None:
        alt = e.attrib.get("alt")
        if alt and alt == e.text and not len(e):
            del e.attrib["alt"]
        kit.check_no_attrib(log, e, ["rid"])
        rid = e.attrib.get("rid")
        if rid is None:
            log(fc.MissingAttribute.issue(e, "rid"))
            return None
        ret = bp.CrossReference(rid)
        parse_mixed_content(log, e, self.content_model, ret.content)
        return ret


class HtmlCrossReferenceModel(kit.LoadModel[Element]):
    def __init__(self, content_model: Model[Element]):
        self.content_model = content_model

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'a' and 'rel' not in xe.attrib

    def load(self, log: Log, xe: XmlElement) -> Element | None:
        kit.check_no_attrib(log, xe, ['href'])
        href = xe.attrib.get("href")
        if href is None:
            log(fc.MissingAttribute.issue(xe, "href"))
            return None
        href = href.strip()
        if not href.startswith("#"):
            log(fc.InvalidAttributeValue.issue(xe, 'href', href))
            return None
        ret = bp.CrossReference(href[1:])
        parse_mixed_content(log, xe, self.content_model, ret.content)
        return ret


def cross_reference_model(
    content_model: Model[Element], biblio: BiblioRefPool | None
) -> Model[Element]:
    jats_xref = JatsCrossReferenceModel(content_model, biblio)
    return jats_xref | HtmlCrossReferenceModel(content_model)


def article_title_model() -> kit.MonoModel[MixedContent]:
    # Contents corresponds to {MINITEXT} in BpDF spec ed.2
    # https://perm.pub/DPRkAz3vwSj85mBCgG49DeyndaE/2
    minitext_model = kit.UnionModel[Element]()
    minitext_model |= minimally_formatted_text_model(minitext_model)
    return MixedContentModel('article-title', minitext_model)


class SectionTitleMonoModel(MixedContentModelBase):
    def __init__(self, child_model: Model[Element]):
        super().__init__(child_model)

    def match(self, xe: XmlElement) -> bool:
        return xe.tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'title']


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
    def __init__(self, models: CoreModels):
        super().__init__(bp.ProtoSection)
        self._models = models

    def binds(self, sess: ArrayContentSession, target: bp.ProtoSection) -> None:
        sess.bind(self._models.p_level, target.presection.append)
        sess.bind(SectionModel(self._models), target.subsections.append)


class SectionModel(kit.LoadModel[bp.Section]):
    """<sec> Section
    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/sec.html
    """

    def __init__(self, models: CoreModels):
        self._title_model = SectionTitleMonoModel(models.heading_text)
        self._proto = ProtoSectionBinder(models)

    def match(self, xe: XmlElement) -> bool:
        return xe.tag in ['section', 'sec']

    def load(self, log: Log, e: XmlElement) -> bp.Section | None:
        kit.check_no_attrib(log, e, ['id'])
        ret = bp.Section([], [], e.attrib.get('id'), MixedContent())
        sess = ArrayContentSession(log)
        self._proto.binds(sess, ret)
        sess.bind_mono(self._title_model, ret.title)
        sess.parse_content(e)
        if ret.title.blank():
            log(fc.MissingSectionHeading.issue(e))
        return ret


CC_URLS = {
    'https://creativecommons.org/publicdomain/zero/': bp.CcLicenseType.CC0,
    'https://creativecommons.org/licenses/by/': bp.CcLicenseType.BY,
    'https://creativecommons.org/licenses/by-sa/': bp.CcLicenseType.BYSA,
    'https://creativecommons.org/licenses/by-nc/': bp.CcLicenseType.BYNC,
    'https://creativecommons.org/licenses/by-nc-sa/': bp.CcLicenseType.BYNCSA,
    'https://creativecommons.org/licenses/by-nd/': bp.CcLicenseType.BYND,
    'https://creativecommons.org/licenses/by-nc-nd/': bp.CcLicenseType.BYNCND,
}


class LicenseRefBinder(kit.BinderBase[bp.License]):
    def match(self, xe: XmlElement) -> bool:
        return xe.tag in [
            "license-ref",
            "license_ref",
            "{http://www.niso.org/schemas/ali/1.0/}license_ref",
        ]

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
        sess.bind_mono(copytext_element_model('license-p'), ret.license_p)
        sess.bind_once(LicenseRefBinder(), ret)
        sess.parse_content(e)
        return None if ret.blank() else ret


class PermissionsModel(kit.TagModelBase[bp.Permissions]):
    TAG = 'permissions'

    def load(self, log: Log, e: XmlElement) -> bp.Permissions | None:
        kit.check_no_attrib(log, e)
        sess = ArrayContentSession(log)
        statement = sess.one(copytext_element_model('copyright-statement'))
        license = sess.one(LicenseModel())
        sess.parse_content(e)
        if license.out is None:
            return None
        if statement.out and not statement.out.blank():
            copyright = bp.Copyright(statement.out)
        else:
            copyright = None
        return bp.Permissions(license.out, copyright)


class AbstractModel(kit.TagModelBase[bp.Abstract]):
    def __init__(self, p_level: Model[Element]):
        super().__init__('abstract')
        self._p_level = p_level

    def load(self, log: Log, e: XmlElement) -> bp.Abstract | None:
        kit.check_no_attrib(log, e)
        sess = ArrayContentSession(log)
        blocks = sess.every(self._p_level)
        sess.parse_content(e)
        return bp.Abstract(list(blocks)) if blocks else None


class ArticleMetaBinder(kit.TagBinderBase[bp.Baseprint]):
    def __init__(self, abstract_model: AbstractModel):
        super().__init__('article-meta')
        self._abstract_model = abstract_model

    def read(self, log: Log, xe: XmlElement, dest: bp.Baseprint) -> None:
        kit.check_no_attrib(log, xe)
        kit.check_required_child(log, xe, 'title-group')
        sess = ArrayContentSession(log)
        title = sess.one(title_group_model())
        authors = sess.one(tag_model('contrib-group', load_author_group))
        abstract = sess.one(self._abstract_model)
        permissions = sess.one(PermissionsModel())
        sess.parse_content(xe)
        if title.out:
            dest.title = title.out
        if authors.out is not None:
            dest.authors = authors.out
        if abstract.out:
            dest.abstract = abstract.out
        if permissions.out is not None:
            dest.permissions = permissions.out


class ArticleFrontBinder(kit.TagBinderBase[bp.Baseprint]):
    def __init__(self, abstract_model: AbstractModel):
        super().__init__('front')
        self._meta_model = ArticleMetaBinder(abstract_model)

    def read(self, log: Log, xe: XmlElement, dest: bp.Baseprint) -> None:
        kit.check_no_attrib(log, xe)
        kit.check_required_child(log, xe, 'article-meta')
        sess = ArrayContentSession(log)
        sess.bind_once(self._meta_model, dest)
        sess.parse_content(xe)


class BodyModel(ContentInElementModelBase[bp.ProtoSection]):
    def __init__(self, models: CoreModels):
        self.content = ProtoSectionBinder(models)

    def match(self, xe: XmlElement) -> bool:
        # JATS and HTML conflict in use of <body> tag
        # DOMParser moves <body> position when parsed as HTML
        return xe.tag in ['article-body', 'body']


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
    models = CoreModels(biblio)
    abstract_model = AbstractModel(models.p_level)
    kit.check_required_child(log, e, 'front')
    sess = ArrayContentSession(log)
    sess.bind_once(ArticleFrontBinder(abstract_model), ret)
    sess.bind_mono(BodyModel(models), ret.body)
    sess.parse_content(e)
    if ret.ref_list:
        assert biblio
        ret.ref_list.references = biblio.used
    if ret.title.blank():
        log(fc.FormatIssue(fc.MissingContent('article-title', 'title-group')))
    if not ret.body.has_content():
        log(fc.FormatIssue(fc.MissingContent('article-body', 'article')))
    for issue in back_log:
        log(issue)
    return ret
