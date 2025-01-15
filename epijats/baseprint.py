from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Tuple

from lxml import etree
from lxml.etree import QName


def parse_baseprint(src: Path) -> Baseprint | None:
    def ignore(issue: FormatIssue) -> None:
        pass

    b = BaseprintBuilder(ignore)
    return b.build(src)


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

    tag: str  # HTML tag
    tail: str

    @property
    def html_attrib(self) -> dict[str, str]:
        return {}


@dataclass
class RichText(ElementContent):
    pass


@dataclass
class Hyperlink(SubElement):
    href: str

    def __init__(self, text: str, subs: list[SubElement], tail: str, href: str):
        super().__init__(text, subs, 'a', tail)
        self.href = href

    @property
    def html_attrib(self) -> dict[str, str]:
        return {'href': self.href}


@dataclass
class Abstract:
    paragraphs: list[RichText]


@dataclass
class Baseprint:
    title: RichText
    authors: list[Author]
    abstract: Abstract | None = None


BARELY_RICH_TEXT_TAGS = {
    'bold': 'strong',
    'ext-link': 'a',
    'italic': 'i',
    'sub': 'sub',
    'sup': 'sup',
}

FAIRLY_RICH_TEXT_TAGS = {
    **BARELY_RICH_TEXT_TAGS,
    'monospace': 'tt',
}


class Parser:
    def __init__(self, issue_callback: Callable[[FormatIssue], None]):
        self._log = issue_callback

    def check_no_attrib(self, e: etree._Element) -> None:
        for k in e.attrib.keys():
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

    def _copy_contents(self, src: etree._Element, dest: RichText) -> None:
        inner = self._content(src)
        dest.append_text(inner.text)
        dest.extend(iter(inner))
        dest.append_text(src.tail)

    def _ext_link(self, e: etree._Element, dest: RichText) -> None:
        k_href = "{http://www.w3.org/1999/xlink}href"
        href = e.attrib.get(k_href)
        link_type = e.attrib.get("ext-link-type")
        if link_type and link_type != "uri":
            cond = UnsupportedAttributeValue("ext-link", "ext-link-type", link_type)
            self._log(FormatIssue(cond, e.sourceline))
        for k, v in e.attrib.items():
            if k not in ["ext-link-type", k_href]:
                self._log(UnsupportedAttribute.issue(e, k))
        c = self._content(e)
        if href is None:
            self._log(MissingAttribute.issue(e, k_href))
            self._copy_contents(e, dest)
        else:
            dest.append(Hyperlink(c.text, list(c), e.tail or "", href))

    def _content(self, e: etree._Element) -> RichText:
        ret = RichText(e.text or "", [])
        for s in e:
            if isinstance(s.tag, str) and s.tag in self.tagmap:
                if s.tag == 'ext-link':
                    tagmap = self.tagmap.copy()
                    del tagmap['ext-link']
                    down = RichTextParser(self._log, tagmap)
                    down._ext_link(s, ret)
                else:
                    ret.append(self.subelement(s, self.tagmap[s.tag]))
            else:
                self._log(UnsupportedElement.issue(s))
                self._copy_contents(s, ret)
        return ret

    def content(self, e: etree._Element) -> RichText:
        for k in e.attrib.keys():
            self._log(UnsupportedAttribute.issue(e, k))
        return self._content(e)

    def subelement(self, e: etree._Element, html_tag: str) -> SubElement:
        c = self.content(e)
        return SubElement(c.text, list(c), html_tag, e.tail or "")


class AbstractParser(Parser):
    def parse(self, e: etree._Element) -> Abstract:
        for k in e.attrib.keys():
            self._log(UnsupportedAttribute.issue(e, k))
        txt_parser = RichTextParser(self._log, FAIRLY_RICH_TEXT_TAGS)
        ps = []
        for s in e:
            if s.tag == "p":
                ps.append(txt_parser.content(s))
            else:
                self._log(UnsupportedElement.issue(s))
        return Abstract(ps)


class AuthorGroupParser(Parser):
    def parse(self, e: Iterator[etree._Element]) -> list[Author]:
        ret = []
        for s in e:
            if s.tag == 'contrib':
                if a := self._contrib(s):
                    ret.append(a)
            else:
                self._log(UnsupportedElement.issue(s))
        return ret

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
        self.title: RichText | None = None
        self.authors: list[Author] = list()
        self.abstract: Abstract | None = None

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
        for pi in et.xpath("//processing-instruction()"):
            self._log(FormatIssue(ProcessingInstruction(pi.text), pi.sourceline))
            etree.strip_elements(et, pi.tag, with_tail=False)
        root = et.getroot()
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
                pass
            elif s.tag == "back":
                pass
            else:
                self._log(UnsupportedElement.issue(s))
        if self.title is None:
            cond = MissingElement('article-title', 'title-group')
            self._log(FormatIssue(cond, e.sourceline))
            return None
        return Baseprint(self.title, self.authors, self.abstract)

    def _front(self, e: etree._Element) -> None:
        self.check_no_attrib(e)
        for s in e:
            if s.tag == 'article-meta':
                self._article_meta(s)
            else:
                self._log(UnsupportedElement.issue(s))

    def _article_meta(self, e: etree._Element) -> None:
        self.check_no_attrib(e)
        for s in e:
            if s.tag == 'abstract':
                self._abstract(s)
            elif s.tag == 'contrib-group':
                self._contrib_group(s)
            elif s.tag == 'permissions':
                pass
            elif s.tag == 'title-group':
                self._title_group(s)
            else:
                self._log(UnsupportedElement.issue(s))

    def _abstract(self, e: etree._Element) -> None:
        p = AbstractParser(self._log)
        self.abstract = p.parse(e)

    def _title_group(self, e: etree._Element) -> None:
        title_parser = RichTextParser(self._log, BARELY_RICH_TEXT_TAGS)
        self.check_no_attrib(e)
        for s in e:
            if s.tag == 'article-title':
                self.title = title_parser.content(s)
            else:
                self._log(UnsupportedElement.issue(s))

    def _contrib_group(self, e: etree._Element) -> None:
        self.check_no_attrib(e)
        if self.authors:
            self._log(ExcessElement.issue(e))
        else:
            parser = AuthorGroupParser(self._log)
            self.authors = parser.parse(iter(e))


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
