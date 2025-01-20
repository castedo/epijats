from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, TYPE_CHECKING, Tuple, TypeAlias

from lxml import etree
from lxml.etree import QName

from .baseprint import (
    Abstract,
    Author,
    Baseprint,
    ElementContent,
    Hyperlink,
    List,
    ListItem,
    Orcid,
    SubElement,
)


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


if TYPE_CHECKING:
    IssueCallback: TypeAlias = Callable[[FormatIssue], None]


def check_no_attrib(
    log: IssueCallback, e: etree._Element, ignore: list[str] = []
) -> None:
    for k in e.attrib.keys():
        if k not in ignore:
            log(UnsupportedAttribute.issue(e, k))


def parse_string(log: IssueCallback, e: etree._Element) -> str:
    check_no_attrib(log, e)
    frags = []
    if e.text:
        frags.append(e.text)
    for s in e:
        log(UnsupportedElement.issue(s))
        frags += parse_string(log, s)
        if s.tail:
            frags.append(s.tail)
    return "".join(frags)


class Validator(ABC):
    def __init__(self, log: IssueCallback):
        self._log = log

    @property
    def log(self) -> IssueCallback:
        return self._log

    def check_no_attrib(self, e: etree._Element, ignore: list[str] = []) -> None:
        check_no_attrib(self.log, e, ignore)


class Parser(Validator):
    @abstractmethod
    def parse_element(self, e: etree._Element) -> bool: ...


class ContentParser(Parser):
    def __init__(self, log: IssueCallback, dest: ElementContent):
        super().__init__(log)
        self.dest = dest

    def parse_content(self, e: etree._Element) -> bool:
        self.dest.append_text(e.text)
        for s in e:
            if not self.parse_element(s):
                self._log(UnsupportedElement.issue(s))
                self.parse_content(s)
                self.dest.append_text(s.tail)
        return True


class Model(ABC):
    @abstractmethod
    def parser(self, log: IssueCallback, dest: ElementContent) -> ContentParser: ...

    def parse_element(
        self, log: IssueCallback, e: etree._Element, dest: ElementContent
    ) -> bool:
        return self.parser(log, dest).parse_element(e)

    def parse_content(
        self, log: IssueCallback, e: etree._Element, dest: ElementContent
    ) -> bool:
        return self.parser(log, dest).parse_content(e)

    def __add__(self, other: Model) -> Model:
        union = self._models.copy() if isinstance(self, UnionModel) else [self]
        if isinstance(other, UnionModel):
            union.extend(other._models)
        elif isinstance(other, Model):
            union.append(other)
        else:
            raise TypeError()
        return UnionModel(union)


class UnionModel(Model):
    def __init__(self, models: Iterable[Model] | None = None):
        self._models = list(models) if models else []

    def parser(self, log: IssueCallback, dest: ElementContent) -> ContentParser:
        return UnionParser(log, dest, self._models)

    def __iadd__(self, other: Model) -> UnionModel:
        if isinstance(other, UnionModel):
            self._models.extend(other._models)
        elif isinstance(other, Model):
            self._models.append(other)
        else:
            raise TypeError()
        return self


class UnionParser(ContentParser):
    def __init__(
        self, log: IssueCallback, dest: ElementContent, models: Iterable[Model]
    ):
        super().__init__(log, dest)
        self._parsers = list(m.parser(log, dest) for m in models)

    def parse_element(self, e: etree._Element) -> bool:
        return any(p.parse_element(e) for p in self._parsers)


class ElementModel(Model):
    @abstractmethod
    def parse(self, log: IssueCallback, e: etree._Element) -> SubElement | None: ...

    def parser(self, log: IssueCallback, dest: ElementContent) -> ContentParser:
        return ElementParser(log, dest, self)


class ElementParser(ContentParser):
    def __init__(self, log: IssueCallback, dest: ElementContent, model: ElementModel):
        super().__init__(log, dest)
        self.model = model

    def parse_element(self, e: etree._Element) -> bool:
        if out := self.model.parse(self.log, e):
            if self.dest.hyperlinked:
                out.hyperlinked = True
            self.dest.append(out)
        return out is not None


class TextElementModel(ElementModel):
    def __init__(self, tagmap: dict[str, str], content_model: Model | bool = True):
        self.tagmap = tagmap
        self.content_model: Model | None = None
        if content_model:
            self.content_model = self if content_model == True else content_model

    def parse(self, log: IssueCallback, e: etree._Element) -> SubElement | None:
        ret = None
        if isinstance(e.tag, str) and e.tag in self.tagmap:
            check_no_attrib(log, e)
            html_tag = self.tagmap[e.tag]
            ret = SubElement("", [], e.tag, html_tag, e.tail or "")
            if self.content_model:
                self.content_model.parse_content(log, e, ret)
        return ret


@dataclass
class ExtLinkModel(Model):
    content_model: Model

    def parser(self, log: IssueCallback, dest: ElementContent) -> ContentParser:
        return ExtLinkParser(log, dest, self.content_model)


class ExtLinkParser(ContentParser):
    def __init__(self, log: IssueCallback, dest: ElementContent, content_model: Model):
        super().__init__(log, dest)
        self.content_model = content_model

    def parse_element(self, e: etree._Element) -> bool:
        if e.tag != 'ext-link':
            return False
        link_type = e.attrib.get("ext-link-type")
        if link_type and link_type != "uri":
            cond = UnsupportedAttributeValue(e.tag, "ext-link-type", link_type)
            self.log(FormatIssue(cond, e.sourceline))
            return False
        k_href = "{http://www.w3.org/1999/xlink}href"
        href = e.attrib.get(k_href)
        self.check_no_attrib(e, ["ext-link-type", k_href])
        ret = None
        if href is None:
            self.log(MissingAttribute.issue(e, k_href))
        elif self.dest.hyperlinked:
            self.log(NestedHyperlinkElement.issue(e))
        else:
            ret = Hyperlink("", [], e.tail or "", href)
            self.content_model.parse_content(self.log, e, ret)
            self.dest.append(ret)
        return ret is not None


@dataclass
class ListModel(ElementModel):
    content_model: Model

    def parse(self, log: IssueCallback, e: etree._Element) -> SubElement | None:
        if e.tag != 'list':
            return None
        list_type = e.attrib.get("list-type")
        if list_type and list_type != "bullet":
            cond = UnsupportedAttributeValue(e.tag, "list-type", list_type)
            log(FormatIssue(cond, e.sourceline))
            return None
        check_no_attrib(log, e, ['list-type'])
        # e.text silently ignored
        ret = List([], e.tail or "")
        for s in e:
            if s.tag == 'list-item':
                item = ListItem("", [])
                self.content_model.parse_content(log, s, item)
                ret.append(item)
            else:
                log(UnsupportedElement.issue(s))
        return ret


class TitleGroupParser(Parser):
    def __init__(self, log: IssueCallback):
        super().__init__(log)
        self.out: ElementContent | None = None
        model = hypertext(TextElementModel(BARELY_RICH_TEXT_TAGS))
        self._txt_parser = RichTextParseHelper(log, model)

    def parse_element(self, e: etree._Element) -> bool:
        if e.tag != 'title-group':
            return False
        self.check_no_attrib(e)
        for s in e:
            if s.tag == 'article-title':
                self.check_no_attrib(s)
                if self.out:
                    self._log(ExcessElement.issue(s))
                else:
                    self.out = self._txt_parser.content(s)
            else:
                self._log(UnsupportedElement.issue(s))
        return True


class AuthorGroupParser(Validator):
    out: list[Author] = []

    def parse(self, e: etree._Element) -> bool:
        self.check_no_attrib(e)
        if self.out:
            self._log(ExcessElement.issue(e))
            return False
        self.out = []
        for s in e:
            if s.tag == 'contrib':
                if a := self._contrib(s):
                    self.out.append(a)
            else:
                self._log(UnsupportedElement.issue(s))
        return True

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
                email = parse_string(self._log, s)
            elif s.tag == 'contrib-id':
                k = 'contrib-id-type'
                if s.attrib.get(k) == 'orcid':
                    del s.attrib[k]
                    url = parse_string(self._log, s)
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
                surname = parse_string(self._log, s)
            elif s.tag == 'given-names':
                given_names = parse_string(self._log, s)
            else:
                self._log(UnsupportedElement.issue(s))
        return (surname, given_names)


class AbstractParser(Validator):
    out: Abstract | None = None

    def parse(self, e: etree._Element) -> bool:
        self.check_no_attrib(e)
        core_model = TextElementModel(FAIRLY_RICH_TEXT_TAGS)
        content_model = hypertext(core_model + ListModel(core_model))
        txt_parser = RichTextParseHelper(self._log, content_model)
        ps = []
        correction: ElementContent | None = None
        text = e.text or ""
        if text.strip():
            correction = ElementContent(text, [])
            text = ""
        for s in e:
            if s.tag == "p":
                if correction:
                    ps.append(correction)
                    correction = None
                ps.append(txt_parser.content(s))
                text = s.tail or ""
                if text.strip():
                    correction = ElementContent(text, [])
                    text = ""
            else:
                self._log(UnsupportedElement.issue(s))
                if not correction:
                    correction = ElementContent(text, [])
                    text = ""
                content_model.parse_element(self._log, s, correction)
        if correction:
            ps.append(correction)
            correction = None
        if ps:
            self.out = Abstract(ps)
        return bool(self.out)


class BaseprintParser(Validator):
    def __init__(self, log: IssueCallback):
        super().__init__(log)
        self.title = TitleGroupParser(log)
        self.authors = AuthorGroupParser(log)
        self.abstract = AbstractParser(log)
        self.body: ElementContent | None = None

    def parse(self, path: Path) -> Baseprint | None:
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
        return self.parse_from_root(et.getroot())

    def parse_from_root(self, root: etree._Element) -> Baseprint | None:
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
                self._body(s)
            elif s.tag == "back":
                pass
            else:
                self._log(UnsupportedElement.issue(s))
        if self.title.out is None:
            cond = MissingElement('article-title', 'title-group')
            self._log(FormatIssue(cond, e.sourceline))
            return None
        return Baseprint(self.title.out, self.authors.out, self.abstract.out)

    def _front(self, e: etree._Element) -> None:
        self.check_no_attrib(e)
        for s in e:
            if s.tag == 'article-meta':
                self._article_meta(s)
            else:
                self._log(UnsupportedElement.issue(s))

    def _body(self, e: etree._Element) -> None:
        self.check_no_attrib(e)
        if self.body is None:
            self.body = ElementContent("", [])
            core_model = hypertext(TextElementModel(VERY_RICH_TEXT_TAGS))
            model = ListModel(core_model) + core_model
            model.parse_content(self.log, e, self.body)
        else:
            self._log(ExcessElement.issue(e))

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
                self.title.parse_element(s)
            else:
                self._log(UnsupportedElement.issue(s))


SUBSUP_TAGS = {
    'sub': 'sub',
    'sup': 'sup',
}

EMPHASIS_TAGS = {
    'bold': 'strong',
    'italic': 'em',
    'monospace': 'tt',
}
# subset of JATS emphasis class elements
# https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/emphasis.class.html

BARELY_RICH_TEXT_TAGS = {
    **SUBSUP_TAGS,
    **EMPHASIS_TAGS,
}

FAIRLY_RICH_TEXT_TAGS = {
    **BARELY_RICH_TEXT_TAGS,
    'p': 'p',
}

VERY_RICH_TEXT_TAGS = {
    **FAIRLY_RICH_TEXT_TAGS,
    'code': 'code',
    'preformat': 'pre',
}

def emphasized_text_model() -> Model:
    """Emphasis Mix Elements (subset of JATS def).

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/emphasized-text.html
    """
    union = UnionModel()
    tags = {
        **EMPHASIS_TAGS,
        **SUBSUP_TAGS,
    }
    union += TextElementModel(tags, union)
    return union


def hypertext(non_hypertext_model: Model) -> Model:
    ret = UnionModel()
    ret += ExtLinkModel(ret)
    ret += non_hypertext_model
    return ret


@dataclass
class RichTextParseHelper:
    log: IssueCallback
    content_model: Model

    def content(self, e: etree._Element) -> ElementContent:
        ret = ElementContent("", [])
        parser = self.content_model.parser(self.log, ret)
        parser.check_no_attrib(e)
        parser.parse_content(e)
        return ret


def parse_text_content(
    log: IssueCallback, e: etree._Element, model: Model
) -> ElementContent:
    return RichTextParseHelper(log, model).content(e)


def ignore_issue(issue: FormatIssue) -> None:
    pass


def parse_baseprint(src: Path) -> Baseprint | None:
    b = BaseprintParser(ignore_issue)
    return b.parse(src)


def parse_baseprint_root(root: etree._Element) -> Baseprint | None:
    b = BaseprintParser(ignore_issue)
    return b.parse_from_root(root)


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


@dataclass(frozen=True)
class NestedHyperlinkElement(ElementFormatCondition):
    """Nested Hyperlinking XML element"""


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
