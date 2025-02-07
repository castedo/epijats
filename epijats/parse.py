from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, Protocol, TYPE_CHECKING, TypeAlias, TypeVar

from lxml import etree

from . import condition as fc
from . import baseprint as bp
from .baseprint import (
    Baseprint,
    Hyperlink,
    ProtoSection,
    Section,
)
from .tree import (
    DataElement, Element, MarkupElement, MixedContent, StartTag, make_paragraph
)


if TYPE_CHECKING:
    IssueCallback: TypeAlias = Callable[[fc.FormatIssue], None]


def issue(
    log: IssueCallback,
    condition: fc.FormatCondition,
    sourceline: int | None = None,
    info: str | None = None,
) -> None:
    return log(fc.FormatIssue(condition, sourceline, info))


def check_no_attrib(
    log: IssueCallback, e: etree._Element, ignore: list[str] = []
) -> None:
    for k in e.attrib.keys():
        if k not in ignore:
            log(fc.UnsupportedAttribute.issue(e, k))


def confirm_attrib_value(
    log: IssueCallback, e: etree._Element, key: str, ok: Iterable[str | None]
) -> bool:
    got = e.attrib.get(key)
    if got in ok:
        return True
    else:
        log(fc.UnsupportedAttributeValue.issue(e, key, got))
        return False


def prep_array_elements(log: IssueCallback, e: etree._Element) -> None:
    if e.text and e.text.strip():
        log(fc.IgnoredText.issue(e))
    for s in e:
        if s.tail and s.tail.strip():
            log(fc.IgnoredText.issue(e))
        s.tail = None


if TYPE_CHECKING:
    ParseFunc: TypeAlias = Callable[[etree._Element], bool]


def parse_array_content(
    log: IssueCallback, e: etree._Element, parse_funcs: Iterable[ParseFunc]
) -> None:
    prep_array_elements(log, e)
    for s in e:
        if not any(pf(s) for pf in parse_funcs):
            log(fc.UnsupportedElement.issue(s))


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
        return issue(self._log, condition, sourceline, info)

    def check_no_attrib(self, e: etree._Element, ignore: list[str] = []) -> None:
        check_no_attrib(self.log, e, ignore)

    def prep_array_elements(self, e: etree._Element) -> None:
        prep_array_elements(self.log, e)

    def parse_array_content(
        self, e: etree._Element, parse_funcs: Iterable[ParseFunc]
    ) -> None:
        parse_array_content(self.log, e, parse_funcs)


class Parser(Validator):
    @abstractmethod
    def parse_element(self, e: etree._Element) -> bool: ...

    def __call__(self, e: etree._Element) -> bool:
        return self.parse_element(e)


ParsedT = TypeVar('ParsedT')
ParsedCovT = TypeVar('ParsedCovT', covariant=True)


class Reader(Protocol, Generic[ParsedCovT]):
    def __call__(self, log: IssueCallback, e: etree._Element) -> ParsedCovT | None: ...


def read_string(log: IssueCallback, e: etree._Element) -> str:
    check_no_attrib(log, e)
    frags = []
    if e.text:
        frags.append(e.text)
    for s in e:
        log(fc.UnsupportedElement.issue(s))
        frags += read_string(log, s)
        if s.tail:
            frags.append(s.tail)
    return "".join(frags)


def read_int(log: IssueCallback, e: etree._Element) -> int | None:
    for s in e:
        log(fc.UnsupportedElement.issue(s))
        if s.tail and s.tail.strip():
            log(fc.IgnoredText.issue(e))
    try:
        text = e.text or ""
        return int(text)
    except ValueError:
        log(fc.InvalidInteger.issue(e, text))
        return None


def read_year(log: IssueCallback, e: etree._Element) -> int | None:
    check_no_attrib(log, e, ['iso-8601-date'])
    expect = (e.text or "").strip()
    got = e.attrib.get('iso-8601-date', '').strip()
    if got and expect != got:
        log(fc.UnsupportedAttributeValue.issue(e, 'iso-8601-date', got))
    return read_int(log, e)


class Model(ABC, Generic[ParsedT]):
    @abstractmethod
    def reader(self, tag: str) -> Reader[ParsedT] | None: ...


class TModel(Model[ParsedT]):
    def __init__(self, tag: str, reader: Reader[ParsedT]):
        self._tag = tag
        self._reader = reader

    def reader(self, tag: str) -> Reader[ParsedT] | None:
        return None if tag != self._tag else self._reader


@dataclass
class Result(Generic[ParsedT]):
    out: ParsedT | None = None


class FirstReadParser(Parser, Generic[ParsedT]):
    def __init__(
        self,
        log: IssueCallback,
        result: Result[ParsedT],
        model: Model[ParsedT],
    ):
        super().__init__(log)
        self.result = result
        self._model = model

    def parse_element(self, e: etree._Element) -> bool:
        if not isinstance(e.tag, str):
            return False
        reader = self._model.reader(e.tag)
        if reader is None:
            return False
        if self.result.out is None:
            self.result.out = reader(self.log, e)
        else:
            self.log(fc.ExcessElement.issue(e))
        return True


if TYPE_CHECKING:
    Sink: TypeAlias = Callable[[ParsedT], None]


class ArrayParser(Parser):
    def __init__(self, log: IssueCallback, tag: str | None):
        super().__init__(log)
        self.tag = tag
        self._parsers: list[ParseFunc] = []

    def first(self, model: Model[ParsedT]) -> Result[ParsedT]:
        ret = Result[ParsedT]()
        self._parsers.append(FirstReadParser(self.log, ret, model))
        return ret

    def add(self, model: Model[ParsedT], dest: Sink[ParsedT]) -> None:
        self._parsers.append(DestParser(self.log, dest, model))

    def parse_element(self, e: etree._Element) -> bool:
        if self.tag and e.tag != self.tag:
            return False
        parse_array_content(self.log, e, self._parsers)
        return True


if TYPE_CHECKING:
    ElementHandler: TypeAlias = Callable[[Element], None]


class EModel(Model[Element]):
    def __or__(self, other: EModel) -> EModel:
        union = self._models.copy() if isinstance(self, UnionModel) else [self]
        if isinstance(other, UnionModel):
            union.extend(other._models)
        elif isinstance(other, EModel):
            union.append(other)
        else:
            raise TypeError()
        return UnionModel(union)


def parse_mixed_content(
    log: IssueCallback, e: etree._Element, emodel: EModel, dest: MixedContent
) -> None:
    eparser = ElementParser(log, dest.append, emodel)
    dest.append_text(e.text)
    for s in e:
        if not eparser.parse_element(s):
            log(fc.UnsupportedElement.issue(s))
            parse_mixed_content(log, s, emodel, dest)
            dest.append_text(s.tail)


class UnionModel(EModel):
    def __init__(self, models: Iterable[EModel] | None = None):
        self._models = list(models) if models else []

    def reader(self, tag: str) -> Reader[Element] | None:
        for m in self._models:
            ret = m.reader(tag)
            if ret is not None:
                return ret
        return None

    def __ior__(self, other: EModel) -> UnionModel:
        if isinstance(other, UnionModel):
            self._models.extend(other._models)
        elif isinstance(other, EModel):
            self._models.append(other)
        else:
            raise TypeError()
        return self


class ElementModel(EModel):
    def __init__(self, tag: str):
        self.tag = tag

    @abstractmethod
    def read(self, log: IssueCallback, e: etree._Element) -> Element | None: ...

    def reader(self, tag: str) -> Reader[Element] | None:
        return self.read if tag == self.tag else None


class DataElementModel(ElementModel):
    def __init__(self, tag: str, content_model: EModel):
        super().__init__(tag)
        self.content_model = content_model

    def read(self, log: IssueCallback, e: etree._Element) -> Element | None:
        check_no_attrib(log, e)
        ret = DataElement(self.tag)
        ap = ArrayParser(log, self.tag)
        ap.add(self.content_model, ret.append)
        ap.parse_element(e)
        return ret


class HtmlDataElementModel(DataElementModel):
    def __init__(self, tag: str, content_model: EModel):
        super().__init__(tag, content_model)
        self.html = StartTag(tag)

    def read(self, log: IssueCallback, e: etree._Element) -> Element | None:
        ret = super().read(log, e)
        if ret:
            ret.html = self.html
        return ret


class DestParser(Parser, Generic[ParsedT]):
    def __init__(self, log: IssueCallback, dest: Sink[ParsedT], model: Model[ParsedT]):
        super().__init__(log)
        self.dest = dest
        self.model = model

    def parse_element(self, e: etree._Element) -> bool:
        if not isinstance(e.tag, str):
            return False
        reader = self.model.reader(e.tag)
        if reader is None:
            return False
        result = reader(self.log, e)
        if result is not None:
            self.dest(result)
        return result is not None


def sink_array_content(
    log: IssueCallback, e: etree._Element, model: Model[ParsedT], dest: Sink[ParsedT]
) -> None:
    parse_array_content(log, e, [DestParser(log, dest, model)])


class ElementParser(Parser):
    def __init__(self, log: IssueCallback, dest: ElementHandler, emodel: EModel):
        super().__init__(log)
        self.dest = dest
        self.emodel = emodel

    def parse_element(self, e: etree._Element) -> bool:
        if not isinstance(e.tag, str):
            return False
        reader = self.emodel.reader(e.tag)
        if reader is None:
            return False
        out = reader(self.log, e)
        if out is not None:
            if e.tail:
                out.tail = e.tail
            self.dest(out)
        return out is not None


class TextElementModel(EModel):
    def __init__(self, tagmap: dict[str, str], content_model: EModel | bool = True):
        self.tagmap = tagmap
        self.content_model: EModel | None = None
        if content_model:
            self.content_model = self if content_model == True else content_model

    def reader(self, tag: str) -> Reader[Element] | None:
        return self.read if tag in self.tagmap else None

    def read(self, log: IssueCallback, e: etree._Element) -> Element | None:
        ret = None
        if isinstance(e.tag, str) and e.tag in self.tagmap:
            check_no_attrib(log, e)
            html_tag = self.tagmap[e.tag]
            ret = MarkupElement(e.tag)
            ret.html = StartTag(html_tag)
            if self.content_model:
                parse_mixed_content(log, e, self.content_model, ret.content)
        return ret


class ExtLinkModel(ElementModel):
    def __init__(self, content_model: EModel):
        super().__init__('ext-link')
        self.content_model = content_model

    def read(self, log: IssueCallback, e: etree._Element) -> Element | None:
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
            parse_mixed_content(log, e, self.content_model, ret.content)
            return ret


class CrossReferenceModel(ElementModel):
    def __init__(self, content_model: EModel):
        super().__init__('xref')
        self.content_model = content_model

    def read(self, log: IssueCallback, e: etree._Element) -> Element | None:
        check_no_attrib(log, e, ["rid", "ref-type"])
        rid = e.attrib.get("rid")
        if rid is None:
            log(fc.MissingAttribute.issue(e, "rid"))
            return None
        ref_type = e.attrib.get("ref-type")
        if ref_type and ref_type != "bibr":
            log(fc.UnsupportedAttributeValue.issue(e, "ref-type", ref_type))
            return None
        ret = bp.CrossReference(rid, ref_type)
        parse_mixed_content(log, e, self.content_model, ret.content)
        return ret


class ListModel(ElementModel):
    def __init__(self, content_model: EModel):
        super().__init__('list')
        self.content_model = content_model

    def read(self, log: IssueCallback, e: etree._Element) -> Element | None:
        list_type = e.attrib.get("list-type")
        if list_type and list_type not in ["bullet", "order"]:
            log(fc.UnsupportedAttributeValue.issue(e, "list-type", list_type))
        check_no_attrib(log, e, ['list-type'])
        ret = bp.List(list_type)
        ap = ArrayParser(log, 'list')
        ap.add(TModel('list-item', self.read_item), ret.append)
        ap.parse_element(e)
        return ret

    def read_item(self, log: IssueCallback, e: etree._Element) -> Element | None:
        ret = bp.ListItem()
        sink_array_content(log, e, self.content_model, ret.append)
        return ret


class TableCellModel(ElementModel):
    def __init__(self, content_model: EModel, *, header: bool):
        super().__init__('th' if header else 'td')
        self.content_model = content_model

    def read(self, log: IssueCallback, e: etree._Element) -> Element | None:
        check_no_attrib(log, e, ['align'])
        align: bp.AlignCode | None = None
        got = e.attrib.get('align')
        if got and got in bp.AlignCode:
            align = bp.AlignCode(got)
        else:
            log(fc.UnsupportedAttributeValue.issue(e, 'align', got)) 
        ret = bp.TableCell(self.tag == 'th', align)
        parse_mixed_content(log, e, self.content_model, ret.content)
        return ret


class MixedContentParser(Parser):
    def __init__(self, log: IssueCallback, dest: MixedContent, model: EModel, tag: str):
        super().__init__(log)
        self.dest = dest
        self.model = model
        self.tag = tag

    def parse_element(self, e: etree._Element) -> bool:
        if e.tag != self.tag:
            return False
        self.check_no_attrib(e)
        if self.dest.empty_or_ws():
            parse_mixed_content(self.log, e, self.model, self.dest)
        else:
            self.log(fc.ExcessElement.issue(e))
        return True


class MixedContentReader(Reader[MixedContent]):
    def __init__(self, model: EModel):
        self.model = model

    def __call__(self, log: IssueCallback, e: etree._Element) -> MixedContent | None:
        check_no_attrib(log, e)
        ret = MixedContent()
        parse_mixed_content(log, e, self.model, ret)
        return ret


def title_model(tag: str) -> Model[MixedContent]:
    return TModel(tag, MixedContentReader(base_hypertext_model()))


class TitleGroupParser(Parser):
    def __init__(self, log: IssueCallback, dest: MixedContent):
        super().__init__(log)
        self.dest = dest
        model = base_hypertext_model()
        self._title_parser = MixedContentParser(log, dest, model, 'article-title')

    def parse_element(self, e: etree._Element) -> bool:
        if e.tag != 'title-group':
            return False
        self.check_no_attrib(e)
        for s in e:
            if not self._title_parser.parse_element(s):
                self.log(fc.UnsupportedElement.issue(s))
        return True


def orcid_model() -> Model[bp.Orcid]:
    return TModel('contrib-id', read_orcid)


def read_orcid(log: IssueCallback, e: etree._Element) -> bp.Orcid | None:
    if e.tag != 'contrib-id' or e.attrib.get('contrib-id-type') != 'orcid':
        return None
    check_no_attrib(log, e, ['contrib-id-type'])
    for s in e:
        log(fc.UnsupportedElement.issue(s))
    try:
        url = e.text or ""
        return bp.Orcid.from_url(url)
    except ValueError:
        log(fc.InvalidOrcid.issue(e, url))
        return None


class AuthorGroupParser(Parser):
    def __init__(self, log: IssueCallback):
        super().__init__(log)
        self.out: list[bp.Author] | None = None

    def parse_element(self, e: etree._Element) -> bool:
        if e.tag != 'contrib-group':
            return False
        self.check_no_attrib(e)
        if self.out is not None:
            self.log(fc.ExcessElement.issue(e))
            return True
        self.out = []
        for s in e:
            author = read_author(self.log, s)
            if author is not None:
                self.out.append(author)
            else:
                self.log(fc.UnsupportedElement.issue(s))
        return True


def person_name_model() -> Model[bp.PersonName]:
    return TModel('name', read_person_name)


def read_person_name(log: IssueCallback, e: etree._Element) -> bp.PersonName | None:
    check_no_attrib(log, e)
    p = ArrayParser(log, 'name')
    surname = p.first(TModel('surname', read_string))
    given_names = p.first(TModel('given-names', read_string))
    if not p.parse_element(e):
        raise ValueError(e)
    if not surname.out and not given_names.out:
        log(fc.MissingContent.issue(e))
        return None
    return bp.PersonName(surname.out, given_names.out)


def read_author(log: IssueCallback, e: etree._Element) -> bp.Author | None:
    if e.tag != 'contrib':
        return None
    if not confirm_attrib_value(log, e, 'contrib-type', ['author']):
        return None
    check_no_attrib(log, e, ['contrib-type', 'id'])
    p = ArrayParser(log, 'contrib')
    name = p.first(person_name_model())
    email = p.first(TModel('email', read_string))
    orcid = p.first(orcid_model())
    if not p.parse_element(e):
        raise ValueError(e)
    if name.out is None:
        log(fc.MissingContent.issue(e, "Missing name"))
        return None
    return bp.Author(name.out, email.out, orcid.out)


class AutoCorrector(Parser):
    def __init__(self, log: IssueCallback, dest: ElementHandler, p_elements: EModel):
        super().__init__(log)
        self.dest = dest
        self.p_elements = p_elements

    def parse_element(self, e: etree._Element) -> bool:
        correction = make_paragraph("")
        ep = ElementParser(self.log, correction.content.append, self.p_elements)
        if not ep.parse_element(e):
            return False
        self.dest(correction)
        self.log(fc.UnsupportedElement.issue(e))
        return True


class SectionContentParser(Validator):
    def __init__(self,
        log: IssueCallback, dest: ProtoSection, p_elements: EModel, p_level: EModel
    ):
        super().__init__(log)
        self.parsers = [
            ElementParser(log, dest.presection.append, p_level),
            AutoCorrector(log, dest.presection.append, p_elements),
            SubSectionParser(log, dest.subsections.append, p_elements),
        ]

    def add_title(self, dest_title: MixedContent) -> None:
        title_model = base_hypertext_model()
        title_parser = MixedContentParser(self.log, dest_title, title_model, 'title')
        self.parsers.append(title_parser)

    def parse_content(self, e: etree._Element) -> None:
        self.parse_array_content(e, self.parsers)


class ProtoSectionParser(Parser):
    def __init__(self,
        log: IssueCallback, dest: ProtoSection, p_elements: EModel, tag: str
    ):
        super().__init__(log)
        self.dest = dest
        self.tag = tag
        p_level = TextElementModel({'p': 'p'}, p_elements)
        self._content = SectionContentParser(log, dest, p_elements, p_level)

    def parse_element(self, e: etree._Element) -> bool:
        if e.tag != self.tag:
            return False
        self.check_no_attrib(e)
        if not self.dest.has_no_content():
            self.log(fc.ExcessElement.issue(e))
            return True
        self._content.parse_content(e)
        return True


class SubSectionParser(Parser):
    def __init__(self,
         log: IssueCallback, dest: Callable[[Section], None], p_elements: EModel
    ):
        super().__init__(log)
        self.dest = dest
        self.p_elements = p_elements

    def parse_element(self, e: etree._Element) -> bool:
        if e.tag != 'sec':
            return False
        self.check_no_attrib(e, ['id'])
        sec = Section([],[], e.attrib.get('id'), MixedContent())
        p_level = p_level_model(self.p_elements)
        content = SectionContentParser(self.log, sec, self.p_elements, p_level)
        content.add_title(sec.title)
        content.parse_content(e)
        self.dest(sec)
        return True


def ref_authors_model() -> Model[list[bp.PersonName | str]]:
    return TModel('person-group', read_ref_authors)


def read_ref_authors(
    log: IssueCallback, e: etree._Element
) -> list[bp.PersonName | str] | None:
    ret: list[bp.PersonName | str] = []
    k = 'person-group-type'
    check_no_attrib(log, e, [k])
    v = e.attrib.get(k, "")
    if v != 'author':
        log(fc.UnsupportedAttributeValue.issue(e, k, v))
        return None
    prep_array_elements(log, e)
    for s in e:
        if s.tag == 'name':
            if pname := read_person_name(log, s):
                ret.append(pname)
        elif s.tag == 'string-name':
            if sname := read_string(log, s):
                ret.append(sname)
        else:
            log(fc.UnsupportedElement.issue(s))
    return ret


class ArticleFrontParser(Parser):
    def __init__(self, log: IssueCallback, dest: Baseprint):
        super().__init__(log)
        self.dest = dest
        p_elements = p_elements_model()
        self.title = TitleGroupParser(log, dest.title)
        self.authors = AuthorGroupParser(log)
        self.abstract = ProtoSectionParser(log, dest.abstract, p_elements, 'abstract')

    def parse_element(self, e: etree._Element) -> bool:
        if e.tag != 'front':
            return False
        self.check_no_attrib(e)
        self.parse_array_content(e, [self._article_meta])
        return True

    def _article_meta(self, e: etree._Element) -> bool:
        if e.tag != 'article-meta':
            return False
        self.check_no_attrib(e)
        parsers = [self.abstract, self.title]
        self.prep_array_elements(e)
        for s in e:
            if self.authors.parse_element(s):
                if self.authors.out is not None:
                    self.dest.authors = self.authors.out
            elif s.tag == 'permissions':
                pass
            elif not any(p.parse_element(s) for p in parsers):
                self.log(fc.UnsupportedElement.issue(s))
        return True


def formatted_text_model(sub_model: EModel | None = None) -> EModel:
    formatted_text_tags = {
        'bold': 'strong',
        'italic': 'em',
        'monospace': 'tt',
        'sub': 'sub',
        'sup': 'sup',
    }
    content_model = True if sub_model is None else sub_model
    return TextElementModel(formatted_text_tags, content_model)


def base_hypertext_model() -> EModel:
    """Base hypertext model"""
    hypertext = UnionModel()
    hypertext |= ExtLinkModel(formatted_text_model())
    hypertext |= CrossReferenceModel(formatted_text_model())
    hypertext |= formatted_text_model(hypertext)
    return hypertext


def list_model(p_elements: EModel) -> EModel:
    # https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/list-item-model.html
    # %list-item-model
    list_item_content = UnionModel()
    list_item_content |= TextElementModel({'p': 'p'}, p_elements)
    list_item_content |= ListModel(list_item_content)
    return ListModel(list_item_content)


def p_elements_model() -> EModel:
    """Paragraph Elements

    Similar to JATS def, but using more restrictive base hypertext model.
    """
    hypertext = base_hypertext_model()  # TODO: add xref as hyperlink element
    # NOTE: open issue whether xref should be allowed in preformatted
    preformatted = TextElementModel({'code': 'pre', 'preformat': 'pre'}, hypertext)

    # https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/p-elements.html
    # %p-elements
    p_elements = UnionModel()
    p_elements |= hypertext
    p_elements |= preformatted
    p_elements |= list_model(p_elements)
    return p_elements


def table_wrap_model(p_elements: EModel) -> EModel:
    th = TableCellModel(p_elements, header=True)
    td = TableCellModel(p_elements, header=False)
    tr = HtmlDataElementModel('tr', th | td)
    thead = HtmlDataElementModel('thead', tr)
    tbody = HtmlDataElementModel('tbody', tr)
    table = HtmlDataElementModel('table', thead | tbody)
    return DataElementModel('table-wrap', table)


def disp_quote_model(p_elements: EModel) -> EModel:
    p = TextElementModel({'p': 'p'}, p_elements)
    ret =  HtmlDataElementModel('disp-quote', p)
    ret.html = StartTag('blockquote')
    return ret


def p_level_model(p_elements: EModel) -> EModel:
    hypertext = base_hypertext_model()
    p_level = UnionModel()
    p_level |= TextElementModel({'p': 'p'}, p_elements)
    p_level |= TextElementModel({'code': 'pre', 'preformat': 'pre'}, hypertext)
    p_level |= list_model(p_elements)
    p_level |= table_wrap_model(p_elements)
    p_level |= disp_quote_model(p_elements)
    return p_level


def read_element_citation(log: IssueCallback, e: etree._Element) -> bp.BiblioReference:
    check_no_attrib(log, e, ['publication-type'])
    ap = ArrayParser(log, 'element-citation')
    title = ap.first(title_model('article-title'))
    authors = ap.first(ref_authors_model())
    year = ap.first(TModel('year', read_year))
    fields = {}
    for key in bp.BiblioReference.BIBLIO_FIELD_KEYS:
        fields[key] = ap.first(TModel(key, read_string))
    if not ap.parse_element(e):
        raise ValueError
    br = bp.BiblioReference()
    br.publication_type = e.get('publication-type', '')
    if br.publication_type not in [
        'book',
        'confproc',
        'journal',
        'other',
        'patent',
        'webpage',
    ]:
        log(
            fc.UnsupportedAttributeValue.issue(
                 e, 'publication-type', br.publication_type
            )
        )
    br.article_title = title.out
    if authors.out:
        br.authors = authors.out
    br.year = year.out
    for key, parser in fields.items():
        if parser.out:
            br.biblio_fields[key] = parser.out
    return br


def read_biblio_ref(log: IssueCallback, e: etree._Element) -> bp.BiblioReference | None:
    if e.tag != 'ref':
        return None
    check_no_attrib(log, e, ['id'])
    prep_array_elements(log, e)
    for s in e:
        if s.tag == 'element-citation':
            ret = read_element_citation(log, s)
            ret.id = e.attrib.get('id', "")
            return ret
        else:
            log(fc.UnsupportedElement.issue(s))
    return None


def read_ref_list(log: IssueCallback, e: etree._Element) -> bp.RefList | None:
    check_no_attrib(log, e)
    ret = bp.RefList()
    p = ArrayParser(log, 'ref-list')
    title = p.first(title_model('title'))
    p.add(TModel('ref', read_biblio_ref), ret.references.append)
    p.parse_element(e)
    ret.title = title.out
    return ret


def read_article_back(log: IssueCallback, e: etree._Element) -> bp.RefList | None:
    check_no_attrib(log, e)
    p = ArrayParser(log, 'back')
    ref_list = p.first(TModel('ref-list', read_ref_list))
    p.parse_element(e)
    return ref_list.out


def read_article(log: IssueCallback , e: etree._Element) -> Baseprint | None:
    lang = '{http://www.w3.org/XML/1998/namespace}lang'
    confirm_attrib_value(log, e, lang, ['en', None])
    check_no_attrib(log, e, [lang])
    ret = bp.Baseprint()
    back = e.find("back")
    if back is not None:
        ret.ref_list = read_article_back(log, back)
        e.remove(back)
    parse_array_content(log, e, [
        ArticleFrontParser(log, ret),
        ProtoSectionParser(log, ret.body, p_elements_model(), 'body'),
    ])
    if ret.title.empty_or_ws():
        issue(log, fc.MissingContent('article-title', 'title-group'))
    if not len(ret.authors):
        issue(log, fc.MissingContent('contrib', 'contrib-group'))
    if ret.abstract.has_no_content():
        issue(log, fc.MissingContent('abstract', 'article-meta'))
    if ret.body.has_no_content():
        issue(log, fc.MissingContent('body', 'article'))
    return ret


def ignore_issue(issue: fc.FormatIssue) -> None:
    pass


def parse_baseprint_root(
    root: etree._Element, log: IssueCallback = ignore_issue
) -> Baseprint | None:
    for pi in root.xpath("//processing-instruction()"):
        log(fc.ProcessingInstruction.issue(pi))
        etree.strip_elements(root, pi.tag, with_tail=False)
    if root.tag != 'article':
        log(fc.UnsupportedElement.issue(root))
        return None
    return read_article(log, root)


def parse_baseprint(src: Path, log: IssueCallback = ignore_issue) -> Baseprint | None:
    path = Path(src)
    if path.is_dir():
        xml_path = path / "article.xml"
    else:
        xml_path = path
    xml_parser = etree.XMLParser(remove_comments=True, load_dtd=False)
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
