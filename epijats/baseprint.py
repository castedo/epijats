from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Tuple

from lxml import etree
from lxml.etree import QName


def ignore_issue(issue: FormatIssue) -> None:
    pass


def parse_baseprint(src: Path) -> Baseprint | None:
    b = BaseprintBuilder(ignore_issue)
    return b.build(src)


def parse_baseprint_root(root: etree._Element) -> Baseprint | None:
    b= BaseprintBuilder(ignore_issue)
    return b.build_from_root(root)


@dataclass(frozen=True)
class Orcid:
    isni: str

    @staticmethod
    def from_url(url: str) -> Orcid:
        url = url.removeprefix("http://orcid.org/")
        url = url.removeprefix("https://orcid.org/")
        isni = url.replace("-", "")
        ok = (
            len(isni) == 16
            and isni[:15].isdigit()
            and (isni[15].isdigit() or isni[15] == "X")
        )
        if not ok:
            raise ValueError()
        return Orcid(isni)

    def as_19chars(self) -> str:
        return "{}-{}-{}-{}".format(
            self.isni[0:4],
            self.isni[4:8],
            self.isni[8:12],
            self.isni[12:16],
        )

    def __str__(self) -> str:
        return "https://orcid.org/" + self.as_19chars()


@dataclass
class Author:
    surname: str | None
    given_names: str | None = None
    email: str | None = None
    orcid: Orcid | None = None

    def __post_init__(self) -> None:
        if not self.surname and not self.given_names:
            raise ValueError()


@dataclass
class ElementContent:
    text: str
    _subelements: list[SubElement]

    def __iter__(self) -> Iterator[SubElement]:
        return iter(self._subelements)

    def append(self, e: SubElement) -> None:
        self._subelements.append(e)

    def extend(self, es: Iterator[SubElement]) -> None:
        self._subelements.extend(es)

    def append_text(self, s: str | None) -> None:
        if s:
            if self._subelements:
                self._subelements[-1].tail += s
            else:
                self.text += s


@dataclass
class SubElement(ElementContent):
    """Common JATS/HTML element"""

    xml_tag: str
    html_tag: str
    tail: str

    @property
    def xml_attrib(self) -> dict[str, str]:
        return {}

    @property
    def html_attrib(self) -> dict[str, str]:
        return {}


@dataclass
class Hyperlink(SubElement):
    href: str

    def __init__(self, text: str, subs: list[SubElement], tail: str, href: str):
        super().__init__(text, subs, 'ext-link', 'a', tail)
        self.href = href

    @property
    def xml_attrib(self) -> dict[str, str]:
        return {"{http://www.w3.org/1999/xlink}href": self.href}

    @property
    def html_attrib(self) -> dict[str, str]:
        return {'href': self.href}


@dataclass
class Abstract:
    paragraphs: list[ElementContent]


@dataclass
class Baseprint:
    title: ElementContent
    authors: list[Author]
    abstract: Abstract | None = None
    body: ElementContent | None = None


BARELY_RICH_TEXT_TAGS = {
    'bold': 'strong',
    'ext-link': 'a',
    'italic': 'em',
    'sub': 'sub',
    'sup': 'sup',
}

FAIRLY_RICH_TEXT_TAGS = {
    **BARELY_RICH_TEXT_TAGS,
    'list': 'ul',
    'monospace': 'tt',
}

VERY_RICH_TEXT_TAGS = {
    **FAIRLY_RICH_TEXT_TAGS,
    'code': 'code',
    'preformat': 'pre',
}


class Parser:
    def __init__(self, issue_callback: Callable[[FormatIssue], None]):
        self._log = issue_callback

    def check_no_attrib(self, e: etree._Element, ignore: list[str] = []) -> None:
        for k in e.attrib.keys():
            if k not in ignore:
                self._log(UnsupportedAttribute.issue(e, k))

    def _simple_strings(self, e: etree._Element) -> list[str]:
        self.check_no_attrib(e)
        ret = []
        if e.text:
            ret.append(e.text)
        for s in e:
            self._log(UnsupportedElement.issue(s))
            ret += self._simple_strings(s)
            if s.tail:
                ret.append(s.tail)
        return ret

    def simple_string(self, e: etree._Element) -> str:
        return "".join(self._simple_strings(e))


class RichTextParser(Parser):
    def __init__(
        self,
        issue_callback: Callable[[FormatIssue], None],
        tagmap: dict[str, str],
    ):
        super().__init__(issue_callback)
        self.tagmap = tagmap

    def parse_content(self, e: etree._Element, out: ElementContent) -> None:
        out.append_text(e.text)
        for s in e:
            sub: SubElement | None = None
            if isinstance(s.tag, str) and s.tag in self.tagmap:
                if s.tag == 'ext-link':
                    xlp = ExtLinkParser(self._log, self.tagmap)
                    sub = xlp.parse(s)
                else:
                    sub = self.parse(s)
            if sub is not None:
                out.append(sub)
            else:
                self._log(UnsupportedElement.issue(s))
                self.parse_content(s, out)
                out.append_text(s.tail)

    def content(self, e: etree._Element) -> ElementContent:
        ret = ElementContent("", [])
        self.check_no_attrib(e)
        self.parse_content(e, ret)
        return ret

    def parse(self, e: etree._Element) -> SubElement | None:
        self.check_no_attrib(e)
        ret = None
        if isinstance(e.tag, str) and e.tag in self.tagmap:
            html_tag = self.tagmap[e.tag]
            ret = SubElement("", [], e.tag, html_tag, e.tail or "")
            self.parse_content(e, ret)
        return ret


class ExtLinkParser(Parser):
    def __init__(
        self,
        issue_callback: Callable[[FormatIssue], None],
        tagmap: dict[str, str],
    ):
        super().__init__(issue_callback)
        tagmap = tagmap.copy()
        if 'ext-link' in tagmap:
            tagmap.pop('ext-link')
        self._sub = RichTextParser(issue_callback, tagmap)

    def parse(self, e: etree._Element) -> SubElement | None:
        link_type = e.attrib.get("ext-link-type")
        if link_type and link_type != "uri":
            cond = UnsupportedAttributeValue(e.tag, "ext-link-type", link_type)
            self._log(FormatIssue(cond, e.sourceline))
            return None
        k_href = "{http://www.w3.org/1999/xlink}href"
        href = e.attrib.get(k_href)
        self.check_no_attrib(e, ["ext-link-type", k_href])
        if href is None:
            self._log(MissingAttribute.issue(e, k_href))
            return None
        else:
            ret = Hyperlink("", [], e.tail or "", href)
            self._sub.parse_content(e, ret)
            return ret


class AbstractParser(Parser):
    out: Abstract | None = None
    
    def parse(self, e: etree._Element) -> None:
        self.check_no_attrib(e)
        txt_parser = RichTextParser(self._log, FAIRLY_RICH_TEXT_TAGS)
        ps = []
        correction: ElementContent | None = None
        for s in e:
            if s.tag == "p":
                if correction:
                    ps.append(correction)
                    correction= None
                ps.append(txt_parser.content(s))
            else:
                self._log(UnsupportedElement.issue(s))
                if not correction:
                    correction = ElementContent("", [])
                if sub := txt_parser.parse(s):
                    correction.append(sub)
        if correction:
            ps.append(correction)
            correction= None
        if ps:
            self.out = Abstract(ps)


class AuthorGroupParser(Parser):
    out: list[Author] = []

    def parse(self, e: etree._Element) -> None:
        self.check_no_attrib(e)
        if self.out:
            self._log(ExcessElement.issue(e))
            return
        self.out = []
        for s in e:
            if s.tag == 'contrib':
                if a := self._contrib(s):
                    self.out.append(a)
            else:
                self._log(UnsupportedElement.issue(s))

    def _contrib(self, e: etree._Element) -> Author | None:
        for k, v in e.attrib.items():
            if k == 'contrib-type':
                if v != "author":
                    self._log(UnsupportedAttributeValue.issue(e, k, v))
                    return None
            elif k == 'id':
                pass
            else:
                self._log(UnsupportedAttribute.issue(e, k))
        surname = None
        given_names = None
        email = None
        orcid = None
        for s in e:
            if s.tag == 'name':
                (surname, given_names) = self._name(s)
            elif s.tag == 'email':
                email = self.simple_string(s)
            elif s.tag == 'contrib-id':
                k = 'contrib-id-type'
                if s.attrib.get(k) == 'orcid':
                    del s.attrib[k]
                    url = self.simple_string(s)
                    try:
                        orcid = Orcid.from_url(url)
                    except ValueError:
                        self._log(FormatIssue(InvalidOrcid(), s.sourceline, url))
                elif k in s.attrib:
                    v = s.attrib[k]
                    self._log(UnsupportedAttributeValue.issue(s, k, v))
                else:
                    self._log(UnsupportedElement.issue(s))
            else:
                self._log(UnsupportedElement.issue(s))
        if surname or given_names:
            return Author(surname, given_names, email, orcid)
        else:
            self._log(FormatIssue(MissingName(), s.sourceline))
            return None

    def _name(self, e: etree._Element) -> Tuple[str | None, str | None]:
        self.check_no_attrib(e)
        surname = None
        given_names = None
        for s in e:
            if s.tag == 'surname':
                surname = self.simple_string(s)
            elif s.tag == 'given-names':
                given_names = self.simple_string(s)
            else:
                self._log(UnsupportedElement.issue(s))
        return (surname, given_names)


@dataclass(frozen=True)
class FormatCondition:
    def __str__(self) -> str:
        return self.__doc__ or type(self).__name__


@dataclass(frozen=True)
class FormatIssue:
    condition: FormatCondition
    sourceline: int | None = None
    info: str | None = None

    def __str__(self) -> str:
        msg = str(self.condition)
        if self.sourceline:
            msg += f" (line {self.sourceline})"
        if self.info:
            msg += f": {self.info}"
        return msg


class BaseprintBuilder(Parser):
    def __init__(self, issue_callback: Callable[[FormatIssue], None]):
        super().__init__(issue_callback)
        self.title: ElementContent | None = None
        self.authors = AuthorGroupParser(issue_callback)
        self.abstract = AbstractParser(issue_callback)

    def build(self, path: Path) -> Baseprint | None:
        path = Path(path)
        if path.is_dir():
            xml_path = path / "article.xml"
        else:
            xml_path = path
        xml_parser = etree.XMLParser(remove_comments=True, load_dtd=False)
        try:
            et = etree.parse(xml_path, parser=xml_parser)
        except etree.XMLSyntaxError as ex:
            self._log(FormatIssue(XMLSyntaxError(), ex.lineno, ex.msg))
            return None
        if bool(et.docinfo.doctype):
            self._log(FormatIssue(DoctypeDeclaration()))
        if et.docinfo.encoding.lower() != "utf-8":
            self._log(FormatIssue(EncodingNotUtf8(et.docinfo.encoding)))
        return self.build_from_root(et.getroot())

    def build_from_root(self, root: etree._Element) -> Baseprint | None:
        for pi in root.xpath("//processing-instruction()"):
            self._log(FormatIssue(ProcessingInstruction(pi.text), pi.sourceline))
            etree.strip_elements(root, pi.tag, with_tail=False)
        if root.tag == 'article':
            return self._article(root)
        else:
            self._log(UnsupportedElement.issue(root))
            return None

    def _article(self, e: etree._Element) -> Baseprint | None:
        for k, v in e.attrib.items():
            if k == '{http://www.w3.org/XML/1998/namespace}lang':
                if v != "en":
                    self._log(UnsupportedAttributeValue.issue(e, k, v))
            else:
                self._log(UnsupportedAttribute.issue(e, k))
        for s in e:
            if s.tag == "front":
                self._front(s)
            elif s.tag == "body":
                pass  # ; self._body(s)
            elif s.tag == "back":
                pass
            else:
                self._log(UnsupportedElement.issue(s))
        if self.title is None:
            cond = MissingElement('article-title', 'title-group')
            self._log(FormatIssue(cond, e.sourceline))
            return None
        return Baseprint(self.title, self.authors.out, self.abstract.out)

    def _front(self, e: etree._Element) -> None:
        self.check_no_attrib(e)
        for s in e:
            if s.tag == 'article-meta':
                self._article_meta(s)
            else:
                self._log(UnsupportedElement.issue(s))

    def _body(self, e: etree._Element) -> None:
        txt_parser = RichTextParser(self._log, VERY_RICH_TEXT_TAGS)
        self.body = txt_parser.content(e)

    def _article_meta(self, e: etree._Element) -> None:
        self.check_no_attrib(e)
        for s in e:
            if s.tag == 'abstract':
                self.abstract.parse(s)
            elif s.tag == 'contrib-group':
                self.authors.parse(s)
            elif s.tag == 'permissions':
                pass
            elif s.tag == 'title-group':
                self._title_group(s)
            else:
                self._log(UnsupportedElement.issue(s))

    def _title_group(self, e: etree._Element) -> None:
        title_parser = RichTextParser(self._log, BARELY_RICH_TEXT_TAGS)
        self.check_no_attrib(e)
        for s in e:
            if s.tag == 'article-title':
                self.title = title_parser.content(s)
            else:
                self._log(UnsupportedElement.issue(s))


class XMLSyntaxError(FormatCondition):
    """XML syntax error"""


class DoctypeDeclaration(FormatCondition):
    """XML DOCTYPE declaration"""


@dataclass(frozen=True)
class EncodingNotUtf8(FormatCondition):
    encoding: str | None


@dataclass(frozen=True)
class ProcessingInstruction(FormatCondition):
    """XML processing instruction"""

    text: str

    def __str__(self) -> str:
        return "{} {}".format(self.__doc__, repr(self.text))


@dataclass(frozen=True)
class ElementFormatCondition(FormatCondition):
    tag: str | bytes | bytearray | QName
    parent: str | bytes | bytearray | QName | None

    def __str__(self) -> str:
        parent = "" if self.parent is None else repr(self.parent)
        return "{} {}/{!r}".format(self.__doc__, parent, self.tag)

    @classmethod
    def issue(klas, e: etree._Element) -> FormatIssue:
        parent = e.getparent()
        ptag = None if parent is None else parent.tag
        return FormatIssue(klas(e.tag, ptag), e.sourceline)


@dataclass(frozen=True)
class UnsupportedElement(ElementFormatCondition):
    """Unsupported XML element"""


@dataclass(frozen=True)
class ExcessElement(ElementFormatCondition):
    """Excess XML element"""


class InvalidOrcid(FormatCondition):
    """Invalid ORCID"""


class MissingName(FormatCondition):
    """Missing name"""


@dataclass(frozen=True)
class UnsupportedAttribute(FormatCondition):
    """Unsupported XML attribute"""

    tag: str | bytes | bytearray | QName
    attribute: str

    def __str__(self) -> str:
        return f"{self.__doc__} {self.tag!r}@{self.attribute!r}"

    @staticmethod
    def issue(e: etree._Element, key: str) -> FormatIssue:
        return FormatIssue(UnsupportedAttribute(e.tag, key), e.sourceline)


@dataclass(frozen=True)
class UnsupportedAttributeValue(FormatCondition):
    """Unsupported XML attribute value"""

    tag: str | bytes | bytearray | QName
    attribute: str
    value: str

    def __str__(self) -> str:
        msg = "{} {!r}@{!r} = {!r}"
        return msg.format(self.__doc__, self.tag, self.attribute, self.value)

    @staticmethod
    def issue(e: etree._Element, key: str, value: str) -> FormatIssue:
        return FormatIssue(UnsupportedAttributeValue(e.tag, key, value), e.sourceline)


@dataclass(frozen=True)
class MissingElement(FormatCondition):
    """Missing XML element"""

    tag: str
    parent: str

    def __str__(self) -> str:
        return "{} {!r}/{!r}".format(self.__doc__, self.parent, self.tag)


@dataclass(frozen=True)
class MissingAttribute(FormatCondition):
    """Missing XML attribute"""

    tag: str | bytes | bytearray | QName
    attribute: str

    def __str__(self) -> str:
        return f"{self.__doc__} {self.tag!r}@{self.attribute!r}"

    @staticmethod
    def issue(e: etree._Element, key: str) -> FormatIssue:
        return FormatIssue(MissingAttribute(e.tag, key), e.sourceline)
