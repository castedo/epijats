from __future__ import annotations

from typing import TYPE_CHECKING

from .. import baseprint as bp
from .. import condition as fc
from .. import dom
from ..tree import Element, MixedContent

from . import kit
from .kit import Log, Model, tag_model

from .content import (
    ArrayContentSession,
    ContentInElementModel,
    MergedElementsContentBinder,
)
from .htmlish import (
    ext_link_model,
    formatted_text_model,
    hypotext_model,
    minimally_formatted_text_model,
)
from .back import load_person_name
from .tree import MixedContentModel

if TYPE_CHECKING:
    from ..xml import XmlElement


def copytext_model() -> Model[Element]:
    # Corresponds to {COPYTEXT} in BpDF spec ed.2
    ret = kit.UnionModel[Element]()
    ret |= formatted_text_model(ret)
    ret |= ext_link_model(hypotext_model())
    return ret


def copytext_element_model(tag: str) -> kit.MonoModel[MixedContent]:
    return MixedContentModel(tag, copytext_model())


def article_title_model() -> kit.MonoModel[MixedContent]:
    # Contents corresponds to {MINITEXT} in BpDF spec ed.2
    # https://perm.pub/DPRkAz3vwSj85mBCgG49DeyndaE/2
    minitext_model = kit.UnionModel[Element]()
    minitext_model |= minimally_formatted_text_model(minitext_model)
    return MixedContentModel('article-title', minitext_model)


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


class ArticleMetaBinder(kit.TagBinderBase[dom.Article]):
    def __init__(self, abstract_model: Model[bp.Abstract]):
        super().__init__('article-meta')
        self._abstract_model = abstract_model

    def read(self, log: Log, xe: XmlElement, dest: dom.Article) -> None:
        kit.check_no_attrib(log, xe)
        kit.check_required_child(log, xe, 'title-group')
        sess = ArrayContentSession(log)
        title = sess.one(title_group_model())
        authors = sess.one(tag_model('contrib-group', load_author_group))
        abstract = sess.one(self._abstract_model)
        permissions = sess.one(PermissionsModel())
        sess.parse_content(xe)
        if title.out and not title.out.blank():
            dest.title = title.out
        if authors.out is not None:
            dest.authors = authors.out
        if abstract.out:
            dest.abstract = abstract.out
        if permissions.out is not None:
            dest.permissions = permissions.out


class ArticleFrontBinder(kit.TagBinderBase[dom.Article]):
    def __init__(self, abstract_model: Model[bp.Abstract]):
        super().__init__('front')
        self._meta_model = ArticleMetaBinder(abstract_model)

    def read(self, log: Log, xe: XmlElement, dest: dom.Article) -> None:
        kit.check_no_attrib(log, xe)
        kit.check_required_child(log, xe, 'article-meta')
        sess = ArrayContentSession(log)
        sess.bind_once(self._meta_model, dest)
        sess.parse_content(xe)
