from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, TYPE_CHECKING, Tuple, TypeAlias

from lxml import etree

from . import condition as fc
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


if TYPE_CHECKING:
    IssueCallback: TypeAlias = Callable[[fc.FormatIssue], None]


def check_no_attrib(
    log: IssueCallback, e: etree._Element, ignore: list[str] = []
) -> None:
    for k in e.attrib.keys():
        if k not in ignore:
            log(fc.UnsupportedAttribute.issue(e, k))


def parse_string(log: IssueCallback, e: etree._Element) -> str:
    check_no_attrib(log, e)
    frags = []
    if e.text:
        frags.append(e.text)
    for s in e:
        log(fc.UnsupportedElement.issue(s))
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

    def log_issue(self, 
        condition: fc.FormatCondition,
        sourceline: int | None = None,
        info: str | None = None,
    ) -> None:
        return self._log(fc.FormatIssue(condition, sourceline, info))

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
                self.log(fc.UnsupportedElement.issue(s))
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

    def __or__(self, other: Model) -> Model:
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

    def __ior__(self, other: Model) -> UnionModel:
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
class ExtLinkModel(ElementModel):
    content_model: Model

    def parse(self, log: IssueCallback, e: etree._Element) -> SubElement | None:
        if e.tag != 'ext-link':
            return None
        link_type = e.attrib.get("ext-link-type")
        if link_type and link_type != "uri":
            log(fc.UnsupportedAttributeValue.issue(e, "ext-link-type", link_type))
            return None
        k_href = "{http://www.w3.org/1999/xlink}href"
        href = e.attrib.get(k_href)
        check_no_attrib(log, e, ["ext-link-type", k_href])
        if href is None:
            log(fc.MissingAttribute.issue(e, k_href))
            return None
        else:
            ret = Hyperlink("", [], e.tail or "", href)
            self.content_model.parse_content(log, e, ret)
            return ret


@dataclass
class ListModel(ElementModel):
    content_model: Model

    def parse(self, log: IssueCallback, e: etree._Element) -> SubElement | None:
        if e.tag != 'list':
            return None
        list_type = e.attrib.get("list-type")
        if list_type and list_type != "bullet":
            log(fc.UnsupportedAttributeValue.issue(e, "list-type", list_type))
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
                log(fc.UnsupportedElement.issue(s))
        return ret


class BaseprintBuilder(Validator):
    def __init__(self, log: IssueCallback):
        super().__init__(log)
        self.title: ElementContent | None = None
        self.authors: list[Author] = []
        self.abstract: Abstract | None = None
        self.body : ElementContent | None = None

    def build(self) -> Baseprint | None:
        if self.title is None:
            self.log_issue(fc.MissingElement('article-title', 'title-group'))
            return None
        return Baseprint(self.title, self.authors, self.abstract)


class TitleGroupParser(Parser):
    def __init__(self, log: IssueCallback, dest: BaseprintBuilder):
        super().__init__(log)
        self.dest = dest
        self._txt_parser = RichTextParseHelper(log, base_hypertext_model())

    def parse_element(self, e: etree._Element) -> bool:
        if e.tag != 'title-group':
            return False
        self.check_no_attrib(e)
        for s in e:
            if s.tag == 'article-title':
                self.check_no_attrib(s)
                if self.dest.title:
                    self.log(fc.ExcessElement.issue(s))
                else:
                    self.dest.title = self._txt_parser.content(s)
            else:
                self.log(fc.UnsupportedElement.issue(s))
        return True


class AuthorGroupParser(Validator):
    def __init__(self, log: IssueCallback, dest: BaseprintBuilder):
        super().__init__(log)
        self.dest = dest

    def parse(self, e: etree._Element) -> bool:
        self.check_no_attrib(e)
        if self.dest.authors:
            self.log(fc.ExcessElement.issue(e))
            return False
        for s in e:
            if s.tag == 'contrib':
                if a := self._contrib(s):
                    self.dest.authors.append(a)
            else:
                self.log(fc.UnsupportedElement.issue(s))
        return True

    def _contrib(self, e: etree._Element) -> Author | None:
        for k, v in e.attrib.items():
            if k == 'contrib-type':
                if v != "author":
                    self.log(fc.UnsupportedAttributeValue.issue(e, k, v))
                    return None
            elif k == 'id':
                pass
            else:
                self.log(fc.UnsupportedAttribute.issue(e, k))
        surname = None
        given_names = None
        email = None
        orcid = None
        for s in e:
            if s.tag == 'name':
                (surname, given_names) = self._name(s)
            elif s.tag == 'email':
                email = parse_string(self.log, s)
            elif s.tag == 'contrib-id':
                k = 'contrib-id-type'
                if s.attrib.get(k) == 'orcid':
                    del s.attrib[k]
                    url = parse_string(self.log, s)
                    try:
                        orcid = Orcid.from_url(url)
                    except ValueError:
                        self.log_issue(fc.InvalidOrcid(), s.sourceline, url)
                elif k in s.attrib:
                    v = s.attrib[k]
                    self.log(fc.UnsupportedAttributeValue.issue(s, k, v))
                else:
                    self.log(fc.UnsupportedElement.issue(s))
            else:
                self.log(fc.UnsupportedElement.issue(s))
        if surname or given_names:
            return Author(surname, given_names, email, orcid)
        else:
            self.log_issue(fc.MissingName(), s.sourceline)
            return None

    def _name(self, e: etree._Element) -> Tuple[str | None, str | None]:
        self.check_no_attrib(e)
        surname = None
        given_names = None
        for s in e:
            if s.tag == 'surname':
                surname = parse_string(self.log, s)
            elif s.tag == 'given-names':
                given_names = parse_string(self.log, s)
            else:
                self.log(fc.UnsupportedElement.issue(s))
        return (surname, given_names)


class AbstractParser(Validator):
    def __init__(self, log: IssueCallback, dest: BaseprintBuilder, p_elements: Model):
        super().__init__(log)
        self.dest = dest
        self.p_elements = p_elements

    def parse(self, e: etree._Element) -> bool:
        self.check_no_attrib(e)
        txt_parser = RichTextParseHelper(self.log, self.p_elements)
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
                self.log(fc.UnsupportedElement.issue(s))
                if not correction:
                    correction = ElementContent(text, [])
                    text = ""
                self.p_elements.parse_element(self.log, s, correction)
        if correction:
            ps.append(correction)
            correction = None
        if ps:
            self.dest.abstract = Abstract(ps)
        return bool(ps)


class ArticleParser(Parser):
    def __init__(self, log: IssueCallback, dest: BaseprintBuilder):
        super().__init__(log)
        self.dest = dest

        p_elements = p_elements_model()
        p = TextElementModel({'p': 'p'}, p_elements) 
        model = UnionModel()
        model |= p
        model |= TextElementModel({'sec': 'div'}, model)
        self.body_model = model

        self.title = TitleGroupParser(log, dest)
        self.authors = AuthorGroupParser(log, dest)
        self.abstract = AbstractParser(log, dest, p_elements)

    def parse_element(self, e: etree._Element) -> bool:
        if e.tag != 'article':
            return False
        for k, v in e.attrib.items():
            if k == '{http://www.w3.org/XML/1998/namespace}lang':
                if v != "en":
                    self.log(fc.UnsupportedAttributeValue.issue(e, k, v))
            else:
                self.log(fc.UnsupportedAttribute.issue(e, k))
        for s in e:
            if s.tag == "front":
                self._front(s)
            elif s.tag == "body":
                self._body(s)
            elif s.tag == "back":
                pass
            else:
                self.log(fc.UnsupportedElement.issue(s))
        return True

    def _front(self, e: etree._Element) -> None:
        self.check_no_attrib(e)
        for s in e:
            if s.tag == 'article-meta':
                self._article_meta(s)
            else:
                self.log(fc.UnsupportedElement.issue(s))

    def _body(self, e: etree._Element) -> None:
        self.check_no_attrib(e)
        if self.dest.body is None:
            self.dest.body = ElementContent("", [])
            self.body_model.parse_content(self.log, e, self.dest.body)
        else:
            self.log(fc.ExcessElement.issue(e))

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
                self.log(fc.UnsupportedElement.issue(s))


class BaseprintParser(Validator):
    def __init__(self, log: IssueCallback):
        super().__init__(log)
        self.out = BaseprintBuilder(log)
        self.article = ArticleParser(log, self.out)

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
            self.log_issue(fc.XMLSyntaxError(), ex.lineno, ex.msg)
            return None
        if bool(et.docinfo.doctype):
            self.log_issue(fc.DoctypeDeclaration())
        if et.docinfo.encoding.lower() != "utf-8":
            self.log_issue(fc.EncodingNotUtf8(et.docinfo.encoding))
        return self.parse_from_root(et.getroot())

    def parse_from_root(self, root: etree._Element) -> Baseprint | None:
        if root.tag != 'article':
            self.log(fc.UnsupportedElement.issue(root))
            return None
        for pi in root.xpath("//processing-instruction()"):
            self.log(fc.ProcessingInstruction.issue(pi))
            etree.strip_elements(root, pi.tag, with_tail=False)
        self.article.parse_element(root)
        return self.out.build()


def formatted_text_model(sub_model: Model | None = None) -> Model:
    formatted_text_tags = {
        'bold': 'strong',
        'italic': 'em',
        'monospace': 'tt',
        'sub': 'sub',
        'sup': 'sup',
    }
    content_model = True if sub_model is None else sub_model
    return TextElementModel(formatted_text_tags, content_model)


def base_hypertext_model() -> Model:
    """Base hypertext model"""
    hypertext = UnionModel()
    hypertext |= ExtLinkModel(formatted_text_model())
    hypertext |= formatted_text_model(hypertext)
    return hypertext


def p_elements_model() -> Model:
    """Paragraph Elements

    Similar to JATS def, but using more restrictive base hypertext model.
    """
    p_elements = UnionModel()

    # https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/list-item-model.html
    # %list-item-model
    list_item_content = UnionModel()
    list_item_content |= TextElementModel({'p': 'p'}, p_elements)
    list_item_content |= ListModel(list_item_content)

    hypertext = base_hypertext_model() #TODO: add xref as hyperlink element
    #NOTE: open issue whether xref should be allowed in preformatted
    preformatted = TextElementModel({'code': 'pre', 'preformat': 'pre'}, hypertext)

    # https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/p-elements.html
    # %p-elements
    p_elements |= hypertext
    p_elements |= preformatted
    p_elements |= ListModel(list_item_content)
    return p_elements


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


def ignore_issue(issue: fc.FormatIssue) -> None:
    pass


def parse_baseprint(
    src: Path, log: IssueCallback = ignore_issue
) -> Baseprint | None:
    return BaseprintParser(log).parse(src)


def parse_baseprint_root(
    root: etree._Element, log: IssueCallback = ignore_issue
) -> Baseprint | None:
    return BaseprintParser(log).parse_from_root(root)
