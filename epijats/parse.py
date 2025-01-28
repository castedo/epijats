from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, TYPE_CHECKING, Tuple, TypeAlias

from lxml import etree

from . import condition as fc
from .baseprint import (
    Author,
    Baseprint,
    Hyperlink,
    List,
    ListItem,
    Orcid,
    ProtoSection,
    Section,
)
from .tree import Element, MarkupElement, MixedContent, StartTag, make_paragraph


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

    def log_issue(
        self,
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


if TYPE_CHECKING:
    ElementHandler: TypeAlias = Callable[[Element], None]


class ArrayParser(Parser):
    def __init__(self, log: IssueCallback, dest: ElementHandler):
        super().__init__(log)
        self.dest = dest

    def parse_array(self, e: etree._Element) -> None:
        if e.text and e.text.strip():
            self.log(fc.IgnoredText.issue(e))
        for s in e:
            if s.tail and s.tail.strip():
                self.log(fc.IgnoredText.issue(e))
            s.tail = None
            if not self.parse_element(s):
                self.log(fc.UnsupportedElement.issue(s))


class MixedContentParser(Parser):
    def __init__(self, log: IssueCallback, dest: MixedContent, model: Model):
        super().__init__(log)
        self._parser = model.parser(log, dest.append)
        self.dest = dest

    def parse_element(self, e: etree._Element) -> bool:
        return self._parser.parse_element(e)

    def parse_content(self, e: etree._Element) -> None:
        self.dest.append_text(e.text)
        for s in e:
            if not self.parse_element(s):
                self.log(fc.UnsupportedElement.issue(s))
                self.parse_content(s)
                self.dest.append_text(s.tail)


class Model(ABC):
    @abstractmethod
    def parser(self, log: IssueCallback, dest: ElementHandler) -> ArrayParser: ...

    def parse_element(
        self, log: IssueCallback, e: etree._Element, dest: MixedContent
    ) -> bool:
        return MixedContentParser(log, dest, self).parse_element(e)

    def parse_array(
        self, log: IssueCallback, e: etree._Element, dest: ElementHandler
    ) -> None:
        pass
        self.parser(log, dest).parse_array(e)

    def parse_content(
        self, log: IssueCallback, e: etree._Element, dest: MixedContent
    ) -> None:
        return MixedContentParser(log, dest, self).parse_content(e)

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

    def parser(self, log: IssueCallback, dest: ElementHandler) -> ArrayParser:
        return UnionParser(log, dest, self._models)

    def __ior__(self, other: Model) -> UnionModel:
        if isinstance(other, UnionModel):
            self._models.extend(other._models)
        elif isinstance(other, Model):
            self._models.append(other)
        else:
            raise TypeError()
        return self


class UnionParser(ArrayParser):
    def __init__(
        self, log: IssueCallback, dest: ElementHandler, models: Iterable[Model]
    ):
        super().__init__(log, dest)
        self._parsers = list(m.parser(log, dest) for m in models)

    def parse_element(self, e: etree._Element) -> bool:
        return any(p.parse_element(e) for p in self._parsers)


class ElementModel(Model):
    @abstractmethod
    def parse(self, log: IssueCallback, e: etree._Element) -> Element | None: ...

    def parser(self, log: IssueCallback, dest: ElementHandler) -> ArrayParser:
        return ElementParser(log, dest, self)


class ElementParser(ArrayParser):
    def __init__(self, log: IssueCallback, dest: ElementHandler, model: ElementModel):
        super().__init__(log, dest)
        self.model = model

    def parse_element(self, e: etree._Element) -> bool:
        if out := self.model.parse(self.log, e):
            if e.tail:
                out.tail = e.tail
            self.dest(out)
        return out is not None


class TextElementModel(ElementModel):
    def __init__(self, tagmap: dict[str, str], content_model: Model | bool = True):
        self.tagmap = tagmap
        self.content_model: Model | None = None
        if content_model:
            self.content_model = self if content_model == True else content_model

    def parse(self, log: IssueCallback, e: etree._Element) -> Element | None:
        ret = None
        if isinstance(e.tag, str) and e.tag in self.tagmap:
            check_no_attrib(log, e)
            html_tag = self.tagmap[e.tag]
            ret = MarkupElement(e.tag)
            if e.tag == 'p':
                ret.block_level = True
            ret.html = StartTag(html_tag)
            if self.content_model:
                self.content_model.parse_content(log, e, ret.content)
        return ret


@dataclass
class ExtLinkModel(ElementModel):
    content_model: Model

    def parse(self, log: IssueCallback, e: etree._Element) -> Element | None:
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
            ret = Hyperlink(href)
            self.content_model.parse_content(log, e, ret.content)
            return ret


@dataclass
class ListModel(ElementModel):
    content_model: Model

    def parse(self, log: IssueCallback, e: etree._Element) -> Element | None:
        if e.tag != 'list':
            return None
        list_type = e.attrib.get("list-type")
        if list_type and list_type != "bullet":
            log(fc.UnsupportedAttributeValue.issue(e, "list-type", list_type))
            return None
        check_no_attrib(log, e, ['list-type'])
        if e.text and e.text.strip():
            log(fc.IgnoredText.issue(e))
        ret = List()
        for s in e:
            if s.tag == 'list-item':
                item = ListItem()
                self.content_model.parse_array(log, s, item.append)
                ret.append(item)
            else:
                log(fc.UnsupportedElement.issue(s))
            if s.tail and s.tail.strip():
                log(fc.IgnoredText.issue(e))
        return ret


class TitleGroupParser(Parser):
    def __init__(self, log: IssueCallback, dest: MixedContent):
        super().__init__(log)
        self.dest = dest
        model = base_hypertext_model()
        self._parser = MixedContentParser(log, self.dest, model)

    def parse_element(self, e: etree._Element) -> bool:
        if e.tag != 'title-group':
            return False
        self.check_no_attrib(e)
        for s in e:
            if s.tag == 'article-title':
                self.check_no_attrib(s)
                if self.dest.empty_or_ws():
                    self._parser.parse_content(s)
                else:
                    self.log(fc.ExcessElement.issue(s))
            else:
                self.log(fc.UnsupportedElement.issue(s))
        return True


class ContribIdParser(Validator):
    def __init__(self, log: IssueCallback):
        super().__init__(log)
        self.out: Orcid | None = None

    def parse(self, e: etree._Element) -> bool:
        if e.tag != 'contrib-id':
            return False
        k = 'contrib-id-type'
        if e.attrib.get(k) == 'orcid':
            del e.attrib[k]
            url = parse_string(self.log, e)
            try:
                self.out = Orcid.from_url(url)
            except ValueError:
                self.log_issue(fc.InvalidOrcid(), e.sourceline, url)
        elif k in e.attrib:
            v = e.attrib[k]
            self.log(fc.UnsupportedAttributeValue.issue(e, k, v))
        else:
            self.log(fc.UnsupportedElement.issue(e))
        return True


class AuthorGroupParser(Parser):
    def __init__(self, log: IssueCallback):
        super().__init__(log)
        self.out: list[Author] | None = None
        self.author_parser = AuthorParser(log)

    def parse_element(self, e: etree._Element) -> bool:
        if e.tag != 'contrib-group':
            return False
        self.check_no_attrib(e)
        if self.out is not None:
            self.log(fc.ExcessElement.issue(e))
            return True
        self.out = []
        for s in e:
            if self.author_parser.parse_element(s):
                if self.author_parser.out:
                    self.out.append(self.author_parser.out)
            else:
                self.log(fc.UnsupportedElement.issue(s))
        return True


class AuthorParser(Parser):
    def __init__(self, log: IssueCallback):
        super().__init__(log)
        self.out: Author | None = None
        self.orcid_parser = ContribIdParser(self.log)

    def parse_element(self, e: etree._Element) -> bool:
        if e.tag != 'contrib':
            return False
        for k, v in e.attrib.items():
            if k == 'contrib-type':
                if v != "author":
                    self.log(fc.UnsupportedAttributeValue.issue(e, k, v))
                    return False
            elif k == 'id':
                pass
            else:
                self.log(fc.UnsupportedAttribute.issue(e, k))
        self.check_no_attrib(e, ['contrib-type'])
        surname = None
        given_names = None
        email = None
        for s in e:
            if s.tag == 'name':
                (surname, given_names) = self._name(s)
            elif s.tag == 'email':
                email = parse_string(self.log, s)
            elif self.orcid_parser.parse(s):
                pass
            else:
                self.log(fc.UnsupportedElement.issue(s))
        if surname or given_names:
            self.out = Author(surname, given_names, email, self.orcid_parser.out)
            return True
        else:
            self.log_issue(fc.MissingName(), s.sourceline)
            return True

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


class AutoCorrector(Validator):
    def __init__(self, log: IssueCallback, dest: ElementHandler, p_elements: Model):
        super().__init__(log)
        self.dest = dest
        self.p_elements = p_elements
        self.text = ""
        self.correction: MarkupElement | None  = None

    def possible_misplaced_text(self, text: str) -> None:
        if text.strip():
            self.correction = make_paragraph(text)
            self.text = ""
        else:
            self.text = text

    def unsupported_element(self, e: etree._Element) -> None:
        if not self.correction:
            self.correction = make_paragraph(self.text)
            self.text = ""
        self.p_elements.parse_element(self.log, e, self.correction.content)

    def handle_paragraph(self, e: Element | None) -> None:
        if self.correction:
            self.dest(self.correction)
            self.correction = None
        if e is not None:
            self.dest(e)


class ProtoSectionParser(Parser):
    def __init__(self,
            log: IssueCallback,
            dest: ProtoSection,
            p_elements: Model,
            dest_title: MixedContent | None = None,
        ):
        super().__init__(log)
        self.dest = dest
        self._corrector = AutoCorrector(log, dest.presection.append, p_elements)
        p_level = TextElementModel({'p': 'p'}, p_elements)
        self.p_parser = p_level.parser(self.log, self._corrector.handle_paragraph)
        self.title_parser = None
        if dest_title is not None:
            title_model = base_hypertext_model()
            self.title_parser = MixedContentParser(log, dest_title, title_model)
        self.section_parser = SectionParser(log, self.dest.subsections.append, p_elements)

    def parse_element(self, e: etree._Element) -> bool:
        if e.tag not in ['abstract', 'body', 'sec']:
            return False
        self.check_no_attrib(e, ['id'])
        if not self.dest.has_no_content():
            self.log(fc.ExcessElement.issue(e))
            return True
        self._corrector.possible_misplaced_text(e.text or "")
        for s in e:
            if s.tag == 'p':
                self._corrector.possible_misplaced_text(s.tail or "")
                s.tail = None
                self.p_parser.parse_element(s)
            elif s.tag == 'sec':
                self.section_parser.parse_element(s)
            elif s.tag == 'title':
                if self.title_parser:
                    self._corrector.possible_misplaced_text(s.tail or "")
                    s.tail = None
                    self.title_parser.parse_content(s)
            else:
                self.log(fc.UnsupportedElement.issue(s))
                self._corrector.unsupported_element(s)
        self._corrector.handle_paragraph(None)
        return True


class SectionParser(Parser):
    def __init__(self,
         log: IssueCallback, dest: Callable[[Section], None], p_elements: Model
    ):
        super().__init__(log)
        self.dest = dest
        self.p_elements = p_elements

    def parse_element(self, e: etree._Element) -> bool:
        if e.tag != 'sec':
            return False
        self.check_no_attrib(e, ['id'])
        sec = Section([],[], e.attrib.get('id'), MixedContent())
        sub_parser = ProtoSectionParser(self.log, sec, self.p_elements, sec.title)
        sub_parser.parse_element(e)
        self.dest(sec)
        return True


class ArticleParser(Parser):
    def __init__(self, log: IssueCallback, dest: Baseprint):
        super().__init__(log)
        self.dest = dest
        p_elements = p_elements_model()
        self.title = TitleGroupParser(log, dest.title)
        self.authors = AuthorGroupParser(log)
        self.abstract = ProtoSectionParser(log, dest.abstract, p_elements)
        self.body = ProtoSectionParser(log, dest.body, p_elements)

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
                self.body.parse_element(s)
            elif s.tag == "back":
                pass
            else:
                self.log(fc.UnsupportedElement.issue(s))
        if self.dest.title.empty_or_ws():
            self.log_issue(fc.MissingContent('article-title', 'title-group'))
        if not len(self.dest.authors):
            self.log_issue(fc.MissingContent('contrib', 'contrib-group'))
        if self.dest.abstract.has_no_content():
            self.log_issue(fc.MissingContent('abstract', 'article-meta'))
        if self.dest.body.has_no_content():
            self.log_issue(fc.MissingContent('body', 'article'))
        return True

    def _front(self, e: etree._Element) -> None:
        self.check_no_attrib(e)
        for s in e:
            if s.tag == 'article-meta':
                self._article_meta(s)
            else:
                self.log(fc.UnsupportedElement.issue(s))

    def _article_meta(self, e: etree._Element) -> None:
        self.check_no_attrib(e)
        for s in e:
            if s.tag == 'abstract':
                self.abstract.parse_element(s)
            elif self.authors.parse_element(s):
                if self.authors.out is not None:
                    self.dest.authors = self.authors.out
            elif s.tag == 'permissions':
                pass
            elif s.tag == 'title-group':
                self.title.parse_element(s)
            else:
                self.log(fc.UnsupportedElement.issue(s))


class BaseprintParser(Validator):
    def __init__(self, log: IssueCallback):
        super().__init__(log)
        self._out = Baseprint()
        self.article = ArticleParser(log, self._out)

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
        return self._out


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

    hypertext = base_hypertext_model()  # TODO: add xref as hyperlink element
    # NOTE: open issue whether xref should be allowed in preformatted
    preformatted = TextElementModel({'code': 'pre', 'preformat': 'pre'}, hypertext)

    # https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/p-elements.html
    # %p-elements
    p_elements |= hypertext
    p_elements |= preformatted
    p_elements |= ListModel(list_item_content)
    return p_elements


def ignore_issue(issue: fc.FormatIssue) -> None:
    pass


def parse_baseprint(src: Path, log: IssueCallback = ignore_issue) -> Baseprint | None:
    return BaseprintParser(log).parse(src)


def parse_baseprint_root(
    root: etree._Element, log: IssueCallback = ignore_issue
) -> Baseprint | None:
    return BaseprintParser(log).parse_from_root(root)
