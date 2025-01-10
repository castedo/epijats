from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Tuple

from lxml import etree
from lxml.etree import QName


@dataclass(frozen=True)
class Orcid:
    isni: str

    @staticmethod
    def from_url(url: str) -> Orcid:
        url = url.removeprefix("http://orcid.org/")
        url = url.removeprefix("https://orcid.org/")
        isni = url.replace("-", "")
        ok = len(isni) == 16
        ok = ok and isni[:15].isdigit()
        ok = ok and (isni[15].isdigit() or isni[15] == "X")
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


@dataclass(frozen=True)
class Author:
    surname: str | None
    given_names: str | None
    email: str | None
    orcid: Orcid | None


@dataclass
class Element:
    """Common JATS/HTML element"""

    tag: str
    text: str
    _subelements: list[Element]
    tail: str

    def __iter__(self) -> Iterator[Element]:
        return iter(self._subelements)

    def _inner_html_strs(self) -> list[str]:
        ret = [self.text]
        for sub in self:
            ret += sub._outer_html_strs()
            ret.append(sub.tail)
        return ret

    def _outer_html_strs(self) -> list[str]:
        return ['<', self.tag, '>', *self._inner_html_strs(), '</', self.tag, '>']

    def inner_html(self) -> str:
        return "".join(self._inner_html_strs())

    def outer_html(self) -> str:
        return "".join(self._outer_html_strs())


@dataclass(frozen=True)
class Baseprint:
    authors: list[Author]
    title: Element


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


class ElementParser:
    def __init__(
        self, subtags: list[str], issue_callback: Callable[[FormatIssue], None]
    ):
        self.subtags = subtags
        self._issue = issue_callback

    def parse(self, e: etree._Element, new_tag: str | None = None) -> Element:
        for k in e.attrib.keys():
            self._issue(UnsupportedAttribute.issue(e, k))
        tag = new_tag or e.tag
        assert isinstance(tag, str)
        subs = []
        for s in e:
            if s.tag in self.subtags:
                subs.append(self.parse(s))
            else:
                self._issue(UnsupportedElement.issue(s))
        return Element(tag, e.text or "", subs, e.tail or "")


class BaseprintParse:
    def __init__(self) -> None:
        self.issues: list[FormatIssue] = list()
        self.issue = self.issues.append
        self.title: Element
        self.authors: list[Author] = list()

    def baseprint(self, path: Path) -> Baseprint | None:
        path = Path(path)
        if path.is_dir():
            xml_path = path / "article.xml"
        else:
            xml_path = path
        xml_parser = etree.XMLParser(remove_comments=True, load_dtd=False)
        try:
            et = etree.parse(xml_path, parser=xml_parser)
        except etree.XMLSyntaxError as ex:
            self._issue(XMLSyntaxError(), ex.lineno, ex.msg)
            return None
        if bool(et.docinfo.doctype):
            self._issue(DoctypeDeclaration())
        if et.docinfo.encoding.lower() != "utf-8":
            self._issue(EncodingNotUtf8(et.docinfo.encoding))
        for pi in et.xpath("//processing-instruction()"):
            self._issue(ProcessingInstruction(pi.text), pi.sourceline)
            etree.strip_elements(et, pi.tag, with_tail=False)
        root = et.getroot()
        if root.tag == 'article':
            return self._article(root)
        else:
            self.issue(UnsupportedElement.issue(root))
            return None

    def _issue(
        self,
        condition: FormatCondition,
        sourceline: int | None = None,
        info: str | None = None,
    ) -> None:
        self.issues.append(FormatIssue(condition, sourceline))

    def _check_no_attrib(self, e: etree._Element) -> None:
        for k in e.attrib.keys():
            self._issue(UnsupportedAttribute(e.tag, k))

    def _article(self, e: etree._Element) -> Baseprint:
        for k, v in e.attrib.items():
            if k == '{http://www.w3.org/XML/1998/namespace}lang':
                if v != "en":
                    self._issue(UnsupportedAttributeValue(e.tag, k, v))
            else:
                self._issue(UnsupportedAttribute(e.tag, k))
        for s in e:
            if s.tag == "front":
                self._front(s)
            elif s.tag == "body":
                pass
            elif s.tag == "back":
                pass
            else:
                self.issue(UnsupportedElement.issue(s))
        return Baseprint(self.authors, self.title)

    def _front(self, e: etree._Element) -> None:
        self._check_no_attrib(e)
        for s in e:
            if s.tag == 'article-meta':
                self._article_meta(s)
            else:
                self.issue(UnsupportedElement.issue(s))

    def _article_meta(self, e: etree._Element) -> None:
        self._check_no_attrib(e)
        for s in e:
            if s.tag == 'abstract':
                pass
            elif s.tag == 'contrib-group':
                self._contrib_group(s)
            elif s.tag == 'permissions':
                pass
            elif s.tag == 'title-group':
                self._title_group(s)
            else:
                self.issue(UnsupportedElement.issue(s))

    def _title_group(self, e: etree._Element) -> None:
        title_parser = ElementParser(['sub', 'sup'], self.issues.append)
        self._check_no_attrib(e)
        for s in e:
            if s.tag == 'article-title':
                self.title = title_parser.parse(s, 'title')
            else:
                self.issue(UnsupportedElement.issue(s))

    def _contrib_group(self, e: etree._Element) -> None:
        self._check_no_attrib(e)
        self.authors = []
        for s in e:
            if s.tag == 'contrib':
                try:
                    self.authors.append(self._contrib(s))
                except ValueError:
                    pass
            else:
                self.issue(UnsupportedElement.issue(s))

    def _contrib(self, e: etree._Element) -> Author:
        for k, v in e.attrib.items():
            if k == 'contrib-type':
                if v != "author":
                    self._issue(UnsupportedAttributeValue(e.tag, k, v))
                    raise ValueError
            elif k == 'id':
                pass
            else:
                self._issue(UnsupportedAttribute(e.tag, k))
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
                        self._issue(InvalidOrcid(), s.sourceline, url)
                elif k in s.attrib:
                    v = s.attrib[k]
                    self._issue(UnsupportedAttributeValue(s.tag, k, v))
                else:
                    self.issue(UnsupportedElement.issue(s))
            else:
                self.issue(UnsupportedElement.issue(s))
        return Author(surname, given_names, email, orcid)

    def _name(self, e: etree._Element) -> Tuple[str | None, str | None]:
        self._check_no_attrib(e)
        surname = None
        given_names = None
        for s in e:
            if s.tag == 'surname':
                surname = self.simple_string(s)
            elif s.tag == 'given-names':
                given_names = self.simple_string(s)
            else:
                self.issue(UnsupportedElement.issue(s))
        return (surname, given_names)

    def _simple_strings(self, e: etree._Element) -> list[str]:
        self._check_no_attrib(e)
        ret = []
        if e.text:
            ret.append(e.text)
        for s in e:
            self.issue(UnsupportedElement.issue(s))
            ret += self._simple_strings(s)
            if s.tail:
                ret.append(s.tail)
        return ret

    def simple_string(self, e: etree._Element) -> str:
        return "".join(self._simple_strings(e))


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
class UnsupportedElement(FormatCondition):
    """Unsupported XML element"""

    tag: str | bytes | bytearray | QName
    parent: str | bytes | bytearray | QName | None

    def __str__(self) -> str:
        parent = "" if self.parent is None else repr(self.parent)
        return "{} {}/{!r}".format(self.__doc__, parent, self.tag)

    @staticmethod
    def issue(e: etree._Element) -> FormatIssue:
        parent = e.getparent()
        ptag = None if parent is None else parent.tag
        return FormatIssue(UnsupportedElement(e.tag, ptag), e.sourceline)


class InvalidOrcid(FormatCondition):
    """Invalid ORCID"""


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
