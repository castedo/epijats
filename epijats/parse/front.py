from __future__ import annotations

from typing import TYPE_CHECKING

from .. import condition as fc
from .. import dom
from .. import metadata as bp
from ..biblio import BiblioRefPool
from ..document import Abstract
from ..tree import Element, MixedContent, MutableMixedContent

from . import kit
from .kit import Log, Model, LoaderTagModel as tag_model

from .body import roll_model
from .content import ArrayContentSession, MixedModel, UnionMixedModel
from .htmlish import (
    ext_link_model,
    formatted_text_model,
    hypotext_model,
    minimally_formatted_text_model,
)
from .back import load_person_name
from .tree import MixedContentInElementParser

if TYPE_CHECKING:
    from ..typeshed import XmlElement


def copytext_model() -> MixedModel:
    # Corresponds to {COPYTEXT} in BpDF spec ed.2
    ret = UnionMixedModel()
    ret |= formatted_text_model(ret)
    ret |= ext_link_model(hypotext_model())
    return ret


def copytext_element_model(tag: str) -> Model[str | Element]:
    return MixedContentInElementParser(tag, copytext_model())


def article_title_model() -> Model[str | Element]:
    # Contents corresponds to {MINITEXT} in BpDF spec ed.2
    # https://perm.pub/DPRkAz3vwSj85mBCgG49DeyndaE/2
    minitext_model = UnionMixedModel()
    minitext_model |= minimally_formatted_text_model(minitext_model)
    return MixedContentInElementParser('article-title', minitext_model)


class TitleGroupModel(kit.LoadModelBase[MixedContent]):
    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'title-group'

    def load(self, log: Log, xe: XmlElement) -> dom.MixedContent | None:
        kit.check_no_attrib(log, xe)
        sess = ArrayContentSession()
        title = MutableMixedContent()
        sess.bind_once(article_title_model(), title)
        sess.parse_content(log, xe)
        return None if title.blank() else title


class OrcidModel(kit.LoadModelBase[bp.Orcid]):
    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'contrib-id'

    def load(self, log: Log, xe: XmlElement) -> bp.Orcid | None:
        kit.check_no_attrib(log, xe, ['contrib-id-type'])
        kit.check_no_children(log, xe)
        ret = None
        url = xe.text or ""
        if xe.attrib.get('contrib-id-type') == 'orcid':
            try:
                ret = bp.Orcid.from_url(url)
            except ValueError:
                pass
        if ret is None:
            log(fc.InvalidOrcid.issue(xe, url))
        return ret


def load_author_group(log: Log, e: XmlElement) -> list[bp.Author] | None:
    ret: list[bp.Author] = []
    kit.check_no_attrib(log, e)
    kit.check_required_child(log, e, 'contrib')
    sess = ArrayContentSession()
    sess.bind(tag_model('contrib', load_author), ret.append)
    sess.parse_content(log, e)
    return ret


def person_name_model() -> Model[bp.PersonName]:
    return tag_model('name', load_person_name)


def load_author(log: Log, e: XmlElement) -> bp.Author | None:
    if e.tag != 'contrib':
        return None
    if not kit.confirm_attrib_value(log, e, 'contrib-type', ['author']):
        return None
    kit.check_no_attrib(log, e, ['contrib-type'])
    sess = ArrayContentSession()
    name = sess.one(person_name_model())
    email = sess.one(tag_model('email', kit.load_string))
    orcid = sess.one(OrcidModel())
    sess.parse_content(log, e)
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

    def parse(self, log: Log, xe: XmlElement, dest: dom.License) -> bool:
        kit.check_no_attrib(log, xe, ['content-type'])
        dest.license_ref = kit.load_string_content(log, xe)
        from_attribute = kit.get_enum_value(log, xe, 'content-type', dom.CcLicenseType)
        if from_url := dom.CcLicenseType.from_url(dest.license_ref):
            if from_attribute and from_attribute != from_url:
                log(fc.InvalidAttributeValue.issue(xe, 'content-type', from_attribute))
            dest.cc_license_type = from_url
        else:
            dest.cc_license_type = from_attribute
        return True


class LicenseModel(kit.LoadModelBase[dom.License]):
    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'license'

    def load(self, log: Log, e: XmlElement) -> dom.License | None:
        ret = dom.License()
        kit.check_no_attrib(log, e)
        sess = ArrayContentSession()
        sess.bind_once(copytext_element_model('license-p'), ret.license_p)
        sess.bind_once(LicenseRefParser(), ret)
        sess.parse_content(log, e)
        return None if ret.blank() else ret


class PermissionsModel(kit.LoadModelBase[dom.Permissions]):
    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'permissions'

    def load(self, log: Log, e: XmlElement) -> dom.Permissions | None:
        kit.check_no_attrib(log, e)
        sess = ArrayContentSession()
        statement = MutableMixedContent()
        sess.bind_once(copytext_element_model('copyright-statement'), statement)
        license = sess.one(LicenseModel())
        sess.parse_content(log, e)
        if license.out is None:
            return None
        copyright = None if statement.blank() else dom.Copyright(statement)
        return dom.Permissions(license.out, copyright)


class AbstractModel(kit.TagModelBase[Abstract]):
    def __init__(self, biblio: BiblioRefPool | None):
        super().__init__('abstract')
        self.content_model = roll_model(biblio)

    def load(self, log: Log, xe: XmlElement) -> Abstract | None:
        kit.check_no_attrib(log, xe)
        a = Abstract()
        self.content_model.parse_content(log, xe, a.content.append)
        return a if len(a.content) else None


class ArticleMetaParser(kit.Parser[dom.Article]):
    def __init__(self, abstract_model: Model[Abstract]):
        self._abstract_model = abstract_model

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'article-meta'

    def parse(self, log: Log, xe: XmlElement, dest: dom.Article) -> bool:
        kit.check_no_attrib(log, xe)
        kit.check_required_child(log, xe, 'title-group')
        sess = ArrayContentSession()
        title = sess.one(TitleGroupModel())
        authors = sess.one(tag_model('contrib-group', load_author_group))
        abstract = sess.one(self._abstract_model)
        permissions = sess.one(PermissionsModel())
        sess.parse_content(log, xe)
        dest.title = title.out
        if authors.out is not None:
            dest.authors = authors.out
        dest.abstract = abstract.out
        dest.permissions = permissions.out
        return True


class ArticleFrontParser(kit.Parser[dom.Article]):
    def __init__(self, abstract_model: Model[Abstract]):
        self._meta_model = ArticleMetaParser(abstract_model)

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'front'

    def parse(self, log: Log, xe: XmlElement, dest: dom.Article) -> bool:
        kit.check_no_attrib(log, xe)
        kit.check_required_child(log, xe, 'article-meta')
        sess = ArrayContentSession()
        sess.bind_once(self._meta_model, dest)
        sess.parse_content(log, xe)
        return True
