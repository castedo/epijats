from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING
from warnings import warn

from .biblio import csljson_refs_from_baseprint
from .condition import FormatIssue
from .xml.html import HtmlGenerator
from .parse import parse_baseprint
from .webstract import Webstract
from . import dom

if TYPE_CHECKING:
    from .typeshed import JsonData


def author_as_pod(self: dom.Author) -> JsonData:
    ret: dict[str, JsonData] = {'type': 'author'}
    if self.name.surname:
        ret['surname'] = self.name.surname
    if self.name.given_names:
        ret['given-names'] = self.name.given_names
    if self.name.suffix:
        ret['suffix'] = self.name.suffix
    if self.email:
        ret['email'] = [self.email]
    if self.orcid:
        ret['orcid'] = self.orcid.as_19chars()
    return ret


def webstract_from_jats(src: Path | str) -> Webstract:
    src = Path(src)
    jats_src = src / "article.xml" if src.is_dir() else src
    issues: list[FormatIssue] = []
    bp = parse_baseprint(jats_src, issues.append)
    if bp is None:
        raise ValueError()
    ret = webstract_from_baseprint(bp, html_refs=True)
    ret.set_source_from_path(src)
    ret['issues'] = [i.as_pod() for i in issues]
    return ret


def webstract_from_baseprint(
    bp: dom.Article, *, html_refs: bool | None = None,
) -> Webstract:
    if html_refs is None:
        warn("Set html_refs=True if references need to be in HTML", DeprecationWarning)
        html_refs = True
    gen = HtmlGenerator()
    ret = Webstract()
    ret['body'] = gen.html_body_content(bp)
    ret['bare_tex'] = gen.bare_tex
    if bp.ref_list:
        ret['csljson'] = csljson_refs_from_baseprint(bp)
        if html_refs:
            ret['references'] = gen.html_references(bp.ref_list)
            ret['references_abridged'] = gen.html_references(bp.ref_list, abridged=True)
    if bp.title is None:
        warn("Blank title")
        ret['title'] = ' '
    else:
        ret['title'] = gen.content_to_str(bp.title)
    ret['contributors'] = [author_as_pod(a) for a in bp.authors]
    if bp.abstract:
        ret['abstract'] = gen.abstract_to_str(bp.abstract)
    if bp.permissions:
        if bp.permissions.license:
            if bp.permissions.license.license_ref:
                ret['license_ref'] = bp.permissions.license.license_ref
            ret['license_p'] = gen.content_to_str(bp.permissions.license.license_p)
            if bp.permissions.license.cc_license_type:
                ret['cc_license_type'] = str(bp.permissions.license.cc_license_type)
        if bp.permissions.copyright:
            ret['copyright'] = gen.content_to_str(bp.permissions.copyright.statement)
    return ret


def webstract_pod_from_baseprint(bp: dom.Article) -> dict[str, Any]:
    return dict(webstract_from_baseprint(bp, html_refs=False))
