from __future__ import annotations

from typing import TYPE_CHECKING

from .. import condition as fc
from .. import dom
from .. import metadata as bp
from ..document import Abstract
from ..tree import Element, Inline, MixedContent, MutableMixedContent

from . import kit
from .kit import Log, Model, LoaderTagModel as tag_model

from .content import ArrayContentSession, MixedModel, UnionMixedModel
from .htmlish import (
    ext_link_model,
    formatted_text_model,
    hypotext_model,
    minimally_formatted_text_model,
)
from .back import load_person_name
from .content import RollContentModel
from .tree import MixedContentBinder

if TYPE_CHECKING:
    from ..typeshed import XmlElement


def copytext_model() -> MixedModel:
    # Corresponds to {COPYTEXT} in BpDF spec ed.2
    ret = UnionMixedModel()
    ret |= formatted_text_model(ret)
    ret |= ext_link_model(hypotext_model())
    return ret


def copytext_element_model(tag: str) -> Model[str | Inline]:
    return MixedContentBinder(tag, copytext_model())


def article_title_model() -> Model[str | Inline]:
    # Contents corresponds to {MINITEXT} in BpDF spec ed.2
    # https://perm.pub/DPRkAz3vwSj85mBCgG49DeyndaE/2
    minitext_model = UnionMixedModel()
    minitext_model |= minimally_formatted_text_model(minitext_model)
    return MixedContentBinder('article-title', minitext_model)


class TitleGroupModel(kit.LoadModelBase[MixedContent]):
    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'title-group'

    def load(self, log: Log, xe: XmlElement) -> dom.MixedContent | None:
        kit.check_no_attrib(log, xe)
        sess = ArrayContentSession(log)
        title = MutableMixedContent()
        sess.bind_once(article_title_model(), title)
        sess.parse_content(xe)
        return None if title.blank() else title


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
    ret: list[bp.Author] = []
    kit.check_no_attrib(log, e)
    kit.check_required_child(log, e, 'contrib')
    sess = ArrayContentSession(log)
    sess.bind(tag_model('contrib', load_author), ret.append)
    sess.parse_content(e)
    return ret


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


class LicenseRefParser(kit.Parser[dom.License]):
    def match(self, xe: XmlElement) -> bool:
        return xe.tag in [
            "license-ref",
            "license_ref",
            "{http://www.niso.org/schemas/ali/1.0/}license_ref",
        ]

    def parse(self, log: Log, xe: XmlElement, dest: dom.License) -> None:
        kit.check_no_attrib(log, xe, ['content-type'])
        dest.license_ref = kit.load_string_content(log, xe)
        from_attribute = kit.get_enum_value(log, xe, 'content-type', dom.CcLicenseType)
        if from_url := dom.CcLicenseType.from_url(dest.license_ref):
            if from_attribute and from_attribute != from_url:
                issue = fc.InvalidAttributeValue.issue
                log(issue(xe, 'content-type', from_attribute))
            dest.cc_license_type = from_url
        else:
            dest.cc_license_type = from_attribute


class LicenseModel(kit.LoadModelBase[dom.License]):
    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'license'

    def load(self, log: Log, e: XmlElement) -> dom.License | None:
        ret = dom.License()
        kit.check_no_attrib(log, e)
        sess = ArrayContentSession(log)
        sess.bind_once(copytext_element_model('license-p'), ret.license_p)
        sess.bind_once(LicenseRefParser(), ret)
        sess.parse_content(e)
        return None if ret.blank() else ret


class PermissionsModel(kit.LoadModelBase[dom.Permissions]):
    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'permissions'

    def load(self, log: Log, e: XmlElement) -> dom.Permissions | None:
        kit.check_no_attrib(log, e)
        sess = ArrayContentSession(log)
        statement = MutableMixedContent()
        sess.bind_once(copytext_element_model('copyright-statement'), statement)
        license = sess.one(LicenseModel())
        sess.parse_content(e)
        if license.out is None:
            return None
        copyright = None if statement.blank() else dom.Copyright(statement)
        return dom.Permissions(license.out, copyright)


class AbstractModel(kit.TagModelBase[Abstract]):
    def __init__(self, block: Model[Element], inline: MixedModel):
        super().__init__('abstract')
        self._roll = RollContentModel(block, inline)

    def load(self, log: Log, xe: XmlElement) -> Abstract | None:
        kit.check_no_attrib(log, xe)
        a = Abstract()
        self._roll.parse_content(log, xe, a.content.append)
        return a if len(a.content) else None


class ArticleMetaParser(kit.Parser[dom.Article]):
    def __init__(self, abstract_model: Model[Abstract]):
        self._abstract_model = abstract_model

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'article-meta'

    def parse(self, log: Log, xe: XmlElement, dest: dom.Article) -> None:
        kit.check_no_attrib(log, xe)
        kit.check_required_child(log, xe, 'title-group')
        sess = ArrayContentSession(log)
        title = sess.one(TitleGroupModel())
        authors = sess.one(tag_model('contrib-group', load_author_group))
        abstract = sess.one(self._abstract_model)
        permissions = sess.one(PermissionsModel())
        sess.parse_content(xe)
        dest.title = title.out
        if authors.out is not None:
            dest.authors = authors.out
        dest.abstract = abstract.out
        dest.permissions = permissions.out


class ArticleFrontParser(kit.Parser[dom.Article]):
    def __init__(self, abstract_model: Model[Abstract]):
        self._meta_model = ArticleMetaParser(abstract_model)

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'front'

    def parse(self, log: Log, xe: XmlElement, dest: dom.Article) -> None:
        kit.check_no_attrib(log, xe)
        kit.check_required_child(log, xe, 'article-meta')
        sess = ArrayContentSession(log)
        sess.bind_once(self._meta_model, dest)
        sess.parse_content(xe)
