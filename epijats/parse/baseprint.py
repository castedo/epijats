"""Parsing at the level of Baseprint."""

from __future__ import annotations

import tempfile
import xml.etree.ElementTree
from pathlib import Path
from typing import TYPE_CHECKING

from .. import dom
from .. import condition as fc
from ..biblio import BiblioRefPool

from . import kit
from .back import RefListModel
from .body import BodyModel, CoreModels
from .content import ArrayContentSession
from .front import AbstractModel, ArticleFrontBinder
from .kit import Log, nolog

if TYPE_CHECKING:
    from types import ModuleType
    from ..typeshed import XmlElement
    import hidos


NAMESPACE_MAP = {
    'ali': "http://www.niso.org/schemas/ali/1.0/",
    'mml': "http://www.w3.org/1998/Math/MathML",
    'xlink': "http://www.w3.org/1999/xlink",
}


# key is (use_lxml: bool)
_NAMESPACES_REGISTERED = {False: False, True: False}


def get_ET(*, use_lxml: bool) -> ModuleType:
    ret: ModuleType
    if use_lxml:
        import lxml.etree

        ret = lxml.etree
    else:
        ret = xml.etree.ElementTree

    if not _NAMESPACES_REGISTERED[use_lxml]:
        for prefix, name in NAMESPACE_MAP.items():
            ret.register_namespace(prefix, name)
        _NAMESPACES_REGISTERED[use_lxml] = True
    return ret


def pop_load_sub_back(log: Log, xe: XmlElement) -> dom.BiblioRefList | None:
    back = xe.find("back")
    if back is None:
        return None
    kit.check_no_attrib(log, back)
    sess = ArrayContentSession(log)
    result = sess.one(RefListModel())
    sess.parse_content(back)
    xe.remove(back)  # type: ignore[arg-type]
    return result.out


def load_article(log: Log, e: XmlElement) -> dom.Article | None:
    """Loader function for <article>

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/article.html
    """
    lang = '{http://www.w3.org/XML/1998/namespace}lang'
    kit.confirm_attrib_value(log, e, lang, ['en', None])
    kit.check_no_attrib(log, e, [lang])
    ret = dom.Article()
    back_log = list[fc.FormatIssue]()
    ret.ref_list = pop_load_sub_back(back_log.append, e)
    biblio = BiblioRefPool(ret.ref_list.references) if ret.ref_list else None
    models = CoreModels(biblio)
    abstract_model = AbstractModel(models.block)
    kit.check_required_child(log, e, 'front')
    sess = ArrayContentSession(log)
    sess.bind_once(ArticleFrontBinder(abstract_model), ret)
    sess.bind_mono(BodyModel(models), ret.body)
    sess.parse_content(e)
    if ret.ref_list:
        assert biblio
        ret.ref_list.references = biblio.used
    if not ret.title or ret.title.blank():
        log(fc.FormatIssue(fc.MissingContent('article-title', 'title-group')))
    if not ret.body.has_content():
        log(fc.FormatIssue(fc.MissingContent('article-body', 'article')))
    for issue in back_log:
        log(issue)
    return ret


def parse_baseprint_root(root: XmlElement, log: Log = nolog) -> dom.Article | None:
    if root.tag != 'article':
        log(fc.UnsupportedElement.issue(root))
        return None
    return load_article(log, root)


def parse_baseprint(
    src: Path, log: Log = nolog, *, use_lxml: bool = True
) -> dom.Article | None:
    path = Path(src)
    if path.is_dir():
        xml_path = path / "article.xml"
    else:
        xml_path = path

    ET = get_ET(use_lxml=use_lxml)
    if use_lxml:
        xml_parser = ET.XMLParser(remove_comments=True, remove_pis=True)
    else:
        xml_parser = ET.XMLParser()
    try:
        et = ET.parse(xml_path, parser=xml_parser)
    except ET.ParseError as ex:
        kit.issue(log, fc.XMLSyntaxError(), ex.lineno, ex.msg)
        return None

    if hasattr(et, 'docinfo'):
        if bool(et.docinfo.doctype):
            kit.issue(log, fc.DoctypeDeclaration())
        if et.docinfo.encoding.lower() != "utf-8":
            kit.issue(log, fc.EncodingNotUtf8(et.docinfo.encoding))

    return parse_baseprint_root(et.getroot(), log)


def baseprint_from_edition(ed: hidos.Edition) -> dom.Article | None:
    if not ed.snapshot:
        raise ValueError(f"Edition {ed} is not a snapshot edition")
    with tempfile.TemporaryDirectory() as tempdir:
        snapshot = Path(tempdir) / "snapshot"
        ed.snapshot.copy(snapshot)
        article_xml = snapshot / "article.xml"
        return parse_baseprint(article_xml, use_lxml=False)
