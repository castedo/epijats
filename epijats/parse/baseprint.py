from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from lxml import etree

from .. import condition as fc
from ..baseprint import Baseprint

from .kit import IssueCallback, issue
from .jats import load_article

if TYPE_CHECKING:
    from ..xml import XmlElement

def ignore_issue(issue: fc.FormatIssue) -> None:
    pass


def parse_baseprint_root(
    root: XmlElement, log: IssueCallback = ignore_issue
) -> Baseprint | None:
    if root.tag != 'article':
        log(fc.UnsupportedElement.issue(root))
        return None
    return load_article(log, root)


def parse_baseprint(src: Path, log: IssueCallback = ignore_issue) -> Baseprint | None:
    path = Path(src)
    if path.is_dir():
        xml_path = path / "article.xml"
    else:
        xml_path = path
    xml_parser = etree.XMLParser(remove_comments=True, remove_pis=True)
    try:
        et = etree.parse(xml_path, parser=xml_parser)
    except etree.XMLSyntaxError as ex:
        issue(log, fc.XMLSyntaxError(), ex.lineno, ex.msg)
        return None
    if bool(et.docinfo.doctype):
        issue(log, fc.DoctypeDeclaration())
    if et.docinfo.encoding.lower() != "utf-8":
        issue(log, fc.EncodingNotUtf8(et.docinfo.encoding))
    return parse_baseprint_root(et.getroot(), log)
