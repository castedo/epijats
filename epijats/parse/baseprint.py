"""Parsing at the level of Baseprint."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .. import condition as fc
from ..baseprint import Baseprint
from ..xml import get_ET

from .kit import Log, issue, nolog
from .models import load_article

if TYPE_CHECKING:
    from ..xml import XmlElement
    import hidos


def parse_baseprint_root(root: XmlElement, log: Log = nolog) -> Baseprint | None:
    if root.tag != 'article':
        log(fc.UnsupportedElement.issue(root))
        return None
    return load_article(log, root)


def parse_baseprint(
    src: Path, log: Log = nolog, *, use_lxml: bool = True
) -> Baseprint | None:
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
        issue(log, fc.XMLSyntaxError(), ex.lineno, ex.msg)
        return None

    if hasattr(et, 'docinfo'):
        if bool(et.docinfo.doctype):
            issue(log, fc.DoctypeDeclaration())
        if et.docinfo.encoding.lower() != "utf-8":
            issue(log, fc.EncodingNotUtf8(et.docinfo.encoding))

    return parse_baseprint_root(et.getroot(), log)


def baseprint_from_edition(ed: hidos.Edition) -> Baseprint | None:
    if not ed.snapshot:
        raise ValueError(f"Edition {ed} is not a snapshot edition")
    with tempfile.TemporaryDirectory() as tempdir:
        snapshot = Path(tempdir) / "snapshot"
        ed.snapshot.copy(snapshot)
        article_xml = snapshot / "article.xml"
        return parse_baseprint(article_xml, use_lxml=False)
