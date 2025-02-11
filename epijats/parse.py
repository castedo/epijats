from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Generic, Protocol, Sequence, TYPE_CHECKING, TypeAlias, TypeVar

from lxml import etree

from . import condition as fc
from . import baseprint as bp
from .baseprint import (
    Baseprint,
    Hyperlink,
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
    log: IssueCallback, e: etree._Element, ignore: Iterable[str] = []
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

    def check_no_attrib(self, e: etree._Element, ignore: Iterable[str] = ()) -> None:
        check_no_attrib(self.log, e, ignore)

    def prep_array_elements(self, e: etree._Element) -> None:
        prep_array_elements(self.log, e)


if TYPE_CHECKING:
    ParseFunc: TypeAlias = Callable[[etree._Element], bool]


class Parser(Validator):
    @abstractmethod
    def match(self, tag: str) -> ParseFunc | None: ...

    def parse_element(self, e: etree._Element) -> bool:
        if not isinstance(e.tag, str):
            return False
        fun = self.match(e.tag)
        return False if fun is None else fun(e)

    def parse_array_content(self, e: etree._Element) -> None:
        prep_array_elements(self.log, e)
        for s in e:
            if not self.parse_element(s):
                self.log(fc.UnsupportedElement.issue(s))


class UnionParser(Parser):
    def __init__(self, log: IssueCallback, parsers: Iterable[Parser] = ()):
        super().__init__(log)
        self._parsers = list(parsers)

    def match(self, tag: str) -> ParseFunc | None:
        for p in self._parsers:
            fun = p.match(tag)
            if fun is not None:
                return fun
        return None


class SingleElementParser(Parser):
    def __init__(self, log: IssueCallback, tag: str, content_parser: Parser):
        super().__init__(log)
        self.tag = tag
        self.content_parser = content_parser

    def match(self, tag: str) -> ParseFunc | None:
        return self._parse if tag == self.tag else None

    def _parse(self, e: etree._Element) -> bool:
        check_no_attrib(self.log, e)
        self.content_parser.parse_array_content(e)
        return True


DestT = TypeVar('DestT')
DestConT = TypeVar('DestConT', contravariant=True)


class Reader(Protocol, Generic[DestConT]):
    def __call__(self, log: IssueCallback, e: etree._Element, dest: DestConT) -> bool: ...


ParsedT = TypeVar('ParsedT')
ParsedCovT = TypeVar('ParsedCovT', covariant=True)


class Loader(Protocol, Generic[ParsedCovT]):
    def __call__(self, log: IssueCallback, e: etree._Element) -> ParsedCovT | None: ...


def load_string(
    log: IssueCallback, e: etree._Element, ignore: Iterable[str] = ()
) -> str:
    check_no_attrib(log, e, ignore)
    frags = []
    if e.text:
        frags.append(e.text)
    for s in e:
        log(fc.UnsupportedElement.issue(s))
        frags += load_string(log, s)
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


def load_year(log: IssueCallback, e: etree._Element) -> int | None:
    check_no_attrib(log, e, ['iso-8601-date'])
    expect = (e.text or "").strip()
    got = e.attrib.get('iso-8601-date', '').strip()
    if got and expect != got:
        log(fc.UnsupportedAttributeValue.issue(e, 'iso-8601-date', got))
    return read_int(log, e)


class Binder(ABC, Generic[DestConT]):
    @abstractmethod
    def bind(self, log: IssueCallback, dest: DestConT) -> Parser: ...


Sink: TypeAlias = Callable[[ParsedT], None]

class Model(Binder[Sink[ParsedT]]):
    @abstractmethod
    def match(self, tag: str) -> Loader[ParsedT] | None: ...

    def bind(self, log: IssueCallback, dest: Sink[ParsedT]) -> Parser:
        return SinkParser(log, dest, self)


class SingleElementBinder(Binder[DestT]):
    def __init__(self, tag: str, content_binder: Binder[DestT]):
        self.tag = tag
        self.content_binder = content_binder

    def bind(self, log: IssueCallback, dest: DestT) -> Parser:
        return SingleElementParser(log, self.tag, self.content_binder.bind(log, dest))


class ReaderBinder(Binder[DestT]):
    def __init__(self, tag: str, reader: Reader[DestT]):
        self.tag = tag
        self._reader = reader

    def reader(self, tag: str) -> Reader[DestT] | None:
        return self._reader if tag == self.tag else None

    def bind(self, log: IssueCallback, dest: DestT) -> Parser:
        return ReaderBinderParser(log, dest, self)


class ReaderBinderParser(Parser, Generic[DestT]):
    def __init__(self, log: IssueCallback, dest: DestT, model: ReaderBinder[DestT]):
        super().__init__(log)
        self.dest = dest
        self.model = model

    def match(self, tag: str) -> ParseFunc | None:
        reader = self.model.reader(tag)
        if reader is None:
            return None
        def ret(e: etree._Element) -> bool:
            return reader(self.log, e, self.dest)
        return ret


class LoaderModel(Model[ParsedT]):
    def __init__(self, tag: str, loader: Loader[ParsedT]):
        self._tag = tag
        self._loader = loader

    def match(self, tag: str) -> Loader[ParsedT] | None:
        return None if tag != self._tag else self._loader


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

    def match(self, tag: str) -> ParseFunc | None:
        loader = self._model.match(tag)
        return None if loader is None else self._parse

    def _parse(self, e: etree._Element) -> bool:
        if not isinstance(e.tag, str):
            return False
        loader = self._model.match(e.tag)
        if loader is None:
            return False
        if self.result.out is None:
            self.result.out = loader(self.log, e)
        else:
            self.log(fc.ExcessElement.issue(e))
        return True


class ContentParser(UnionParser):
    def __init__(self, log: IssueCallback):
        super().__init__(log)

    def one(self, model: Model[ParsedT]) -> Result[ParsedT]:
        ret = Result[ParsedT]()
        self._parsers.append(FirstReadParser(self.log, ret, model))
        return ret

    def every(self, binder: Binder[Sink[ParsedT]]) -> Sequence[ParsedT]:
        ret: list[ParsedT] = list()
        self.bind(binder, ret.append)
        return ret

    def bind(self, binder: Binder[DestT], dest: DestT) -> None:
        self._parsers.append(binder.bind(self.log, dest))

    def bind_reader(self, tag: str, reader: Reader[DestT], dest: DestT) -> None:
        self.bind(ReaderBinder(tag, reader), dest)


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
    eparser = SinkParser(log, dest.append, emodel)
    dest.append_text(e.text)
    for s in e:
        if not eparser.parse_element(s):
            log(fc.UnsupportedElement.issue(s))
            parse_mixed_content(log, s, emodel, dest)
            dest.append_text(s.tail)


class UnionModel(EModel):
    def __init__(self, models: Iterable[EModel] | None = None):
        self._models = list(models) if models else []

    def match(self, tag: str) -> Loader[Element] | None:
        for m in self._models:
            ret = m.match(tag)
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


class ElementModelBase(EModel):
    def __init__(self, tag: str):
        self.tag = tag

    @abstractmethod
    def load(self, log: IssueCallback, e: etree._Element) -> Element | None: ...

    def match(self, tag: str) -> Loader[Element] | None:
        return self.load if tag == self.tag else None


class DataElementModel(ElementModelBase):
    def __init__(self, tag: str, content_model: EModel):
        super().__init__(tag)
        self.content_model = content_model

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        check_no_attrib(log, e)
        ret = DataElement(self.tag)
        self.content_model.bind(log, ret.append).parse_array_content(e)
        return ret


class HtmlDataElementModel(DataElementModel):
    def __init__(self, tag: str, content_model: EModel, html_tag: str | None = None):
        super().__init__(tag, content_model)
        self.html = StartTag(html_tag or tag)

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        ret = super().load(log, e)
        if ret:
            ret.html = self.html
        return ret


class SinkParser(Parser, Generic[ParsedT]):
    def __init__(self, log: IssueCallback, dest: Sink[ParsedT], model: Model[ParsedT]):
        super().__init__(log)
        self.dest = dest
        self.model = model

    def match(self, tag: str) -> ParseFunc | None:
        loader = self.model.match(tag)
        return None if loader is None else self._parse

    def _parse(self, e: etree._Element) -> bool:
        if not isinstance(e.tag, str):
            return False
        loader = self.model.match(e.tag)
        if loader is None:
            return False
        result = loader(self.log, e)
        if result is not None:
            if isinstance(result, Element) and e.tail:
                result.tail = e.tail
            self.dest(result)
        return result is not None


class TextElementModel(EModel):
    def __init__(self, tagmap: dict[str, str], content_model: EModel | bool = True):
        self.tagmap = tagmap
        self.content_model: EModel | None = None
        if content_model:
            self.content_model = self if content_model == True else content_model

    def match(self, tag: str) -> Loader[Element] | None:
        return self.load if tag in self.tagmap else None

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        ret = None
        if isinstance(e.tag, str) and e.tag in self.tagmap:
            check_no_attrib(log, e)
            html_tag = self.tagmap[e.tag]
            ret = MarkupElement(e.tag)
            ret.html = StartTag(html_tag)
            if self.content_model:
                parse_mixed_content(log, e, self.content_model, ret.content)
        return ret


class ExtLinkModel(ElementModelBase):
    def __init__(self, content_model: EModel):
        super().__init__('ext-link')
        self.content_model = content_model

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
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


class CrossReferenceModel(ElementModelBase):
    def __init__(self, content_model: EModel):
        super().__init__('xref')
        self.content_model = content_model

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
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


if TYPE_CHECKING:
    EnumT = TypeVar('EnumT', bound=StrEnum)


def get_enum_value(
    log: IssueCallback, e: etree._Element, key: str, enum: type[EnumT]
) -> EnumT | None:
    ret: EnumT | None = None
    if got := e.attrib.get(key):
        if got in enum:
            ret = enum(got)
        else:
            log(fc.UnsupportedAttributeValue.issue(e, key, got))
    return ret


class ListModel(ElementModelBase):
    def __init__(self, p_elements_model: EModel):
        super().__init__('list')
        # https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/list-item-model.html
        # %list-item-model
        p = TextElementModel({'p': 'p'}, p_elements_model)
        list_item_content = p | self
        self._list_content_model = HtmlDataElementModel(
            'list-item', list_item_content, 'li'
        )

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        check_no_attrib(log, e, ['list-type'])
        list_type = get_enum_value(log, e, 'list-type', bp.ListTypeCode)
        ret = bp.List(list_type)
        self._list_content_model.bind(log, ret.append).parse_array_content(e)
        return ret


class TableCellModel(ElementModelBase):
    def __init__(self, content_model: EModel, *, header: bool):
        super().__init__('th' if header else 'td')
        self.content_model = content_model

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        check_no_attrib(log, e, ['align'])
        align = get_enum_value(log, e, 'align', bp.AlignCode)
        ret = bp.TableCell(self.tag == 'th', align)
        parse_mixed_content(log, e, self.content_model, ret.content)
        return ret


class MixedContentParser(Parser):
    def __init__(self, log: IssueCallback, dest: MixedContent, model: EModel, tag: str):
        super().__init__(log)
        self.dest = dest
        self.model = model
        self.tag = tag

    def match(self, tag: str) -> ParseFunc | None:
        return self._parse if tag == self.tag else None

    def _parse(self, e: etree._Element) -> bool:
        self.check_no_attrib(e)
        if self.dest.blank():
            parse_mixed_content(self.log, e, self.model, self.dest)
        else:
            self.log(fc.ExcessElement.issue(e))
        return True


class MixedContentLoader(Loader[MixedContent]):
    def __init__(self, model: EModel):
        self.model = model

    def __call__(self, log: IssueCallback, e: etree._Element) -> MixedContent | None:
        check_no_attrib(log, e)
        ret = MixedContent()
        parse_mixed_content(log, e, self.model, ret)
        return ret


def mixed_element_model(tag: str) -> Model[MixedContent]:
    return LoaderModel(tag, MixedContentLoader(base_hypertext_model()))


title_model = mixed_element_model


class MixedContentBinder(Binder[MixedContent]):
    def __init__(self, tag: str, content_model: EModel):
        self.tag = tag
        self.content_model = content_model

    def bind(self, log: IssueCallback, dest: MixedContent) -> Parser:
        return MixedContentParser(log, dest, self.content_model, self.tag)


def hypertext_element_binder(tag: str) -> Binder[MixedContent]:
    return MixedContentBinder(tag, base_hypertext_model())


title_binder = hypertext_element_binder


def load_title_group(log: IssueCallback, e: etree._Element) -> MixedContent | None:
    check_no_attrib(log, e)
    ap = ContentParser(log)
    title = ap.one(title_model('article-title'))
    ap.parse_array_content(e)
    return title.out


def orcid_model() -> Model[bp.Orcid]:
    return LoaderModel('contrib-id', load_orcid)


def load_orcid(log: IssueCallback, e: etree._Element) -> bp.Orcid | None:
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


def load_author_group(log: IssueCallback, e: etree._Element) -> list[bp.Author] | None:
    check_no_attrib(log, e)
    acp = ContentParser(log)
    ret = acp.every(LoaderModel('contrib', load_author))
    acp.parse_array_content(e)
    return list(ret)


def person_name_model() -> Model[bp.PersonName]:
    return LoaderModel('name', load_person_name)


def load_person_name(log: IssueCallback, e: etree._Element) -> bp.PersonName | None:
    check_no_attrib(log, e)
    p = ContentParser(log)
    surname = p.one(LoaderModel('surname', load_string))
    given_names = p.one(LoaderModel('given-names', load_string))
    p.parse_array_content(e)
    if not surname.out and not given_names.out:
        log(fc.MissingContent.issue(e))
        return None
    return bp.PersonName(surname.out, given_names.out)


def load_author(log: IssueCallback, e: etree._Element) -> bp.Author | None:
    if e.tag != 'contrib':
        return None
    if not confirm_attrib_value(log, e, 'contrib-type', ['author']):
        return None
    check_no_attrib(log, e, ['contrib-type', 'id'])
    p = ContentParser(log)
    name = p.one(person_name_model())
    email = p.one(LoaderModel('email', load_string))
    orcid = p.one(orcid_model())
    p.parse_array_content(e)
    if name.out is None:
        log(fc.MissingContent.issue(e, "Missing name"))
        return None
    return bp.Author(name.out, email.out, orcid.out)


class AutoCorrector(Model[Element]):
    def __init__(self, p_elements: Model[Element]):
        self.p_elements = p_elements

    def match(self, tag: str) -> Loader[Element] | None:
        return self.correct if self.p_elements.match(tag) else None

    def correct(self, log: IssueCallback, e: etree._Element) -> Element | None:
        if not isinstance(e.tag, str):
            return None
        loader = self.p_elements.match(e.tag)
        if loader is None:
            return None
        p_element = loader(log, e)
        if p_element is None:
            return None
        correction = make_paragraph("")
        correction.content.append(p_element)
        return correction


class ProtoSectionContentBinder(Binder[bp.ProtoSection]):
    def __init__(self, p_elements: EModel, p_level: EModel):
        self.p_elements = p_elements
        self.p_level = p_level

    def bind(self, log: IssueCallback, dest: bp.ProtoSection) -> Parser:
        ret = ContentParser(log)
        ret.bind(self.p_level, dest.presection.append)
        ret.bind(AutoCorrector(self.p_elements), dest.presection.append)
        ret.bind(SectionModel(self.p_elements), dest.subsections.append)
        return ret


class SectionContentBinder(Binder[bp.Section]):
    def __init__(self, p_elements: EModel):
        p_level = p_level_model(p_elements)
        self._proto = ProtoSectionContentBinder(p_elements, p_level)

    def bind(self, log: IssueCallback, dest: bp.Section) -> Parser:
        title = title_binder('title')
        parsers = [title.bind(log, dest.title), self._proto.bind(log, dest)]
        return UnionParser(log, parsers)


def proto_section_binder(tag: str, p_elements: EModel) -> Binder[bp.ProtoSection]:
    p_level = TextElementModel({'p': 'p'}, p_elements)
    return SingleElementBinder(tag, ProtoSectionContentBinder(p_elements,p_level))


class SectionModel(Model[bp.Section]):
    def __init__(self, p_elements: EModel):
        self.content_binder = SectionContentBinder(p_elements)

    def match(self, tag: str) -> Loader[bp.Section] | None:
        return self.load if tag == 'sec' else None

    def load(self, log: IssueCallback, e: etree._Element) -> bp.Section | None:
        check_no_attrib(log, e, ['id'])
        ret = Section([],[], e.attrib.get('id'), MixedContent())
        self.content_binder.bind(log, ret).parse_array_content(e)
        return ret


def ref_authors_model() -> Model[list[bp.PersonName | str]]:
    return LoaderModel('person-group', load_ref_authors)


def load_ref_authors(
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
            if pname := load_person_name(log, s):
                ret.append(pname)
        elif s.tag == 'string-name':
            if sname := load_string(log, s):
                ret.append(sname)
        else:
            log(fc.UnsupportedElement.issue(s))
    return ret


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
    p_elements |= ListModel(p_elements)
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
    p_level |= ListModel(p_elements)
    p_level |= table_wrap_model(p_elements)
    p_level |= disp_quote_model(p_elements)
    return p_level


CC_URLS = {
    'https://creativecommons.org/publicdomain/zero/': bp.CcLicenseType.CC0,
    'https://creativecommons.org/licenses/by/': bp.CcLicenseType.BY,
    'https://creativecommons.org/licenses/by-sa/': bp.CcLicenseType.BYSA,
    'https://creativecommons.org/licenses/by-nc/': bp.CcLicenseType.BYNC,
    'https://creativecommons.org/licenses/by-nc-sa/': bp.CcLicenseType.BYNCSA,
    'https://creativecommons.org/licenses/by-nd/': bp.CcLicenseType.BYND,
    'https://creativecommons.org/licenses/by-nc-nd/': bp.CcLicenseType.BYNCND,
}


def read_license_ref(log: IssueCallback, e: etree._Element, dest: bp.License) -> bool:
    dest.license_ref = load_string(log, e, ['content-type'])
    got_license_type = get_enum_value(log, e, 'content-type', bp.CcLicenseType)
    for prefix, matching_type in CC_URLS.items():
        if dest.license_ref.startswith(prefix):
            if got_license_type and got_license_type != matching_type:
                log(fc.InvalidAttributeValue.issue(e, 'content-type', got_license_type))
            dest.cc_license_type = matching_type
            return True
    dest.cc_license_type = got_license_type
    return True


def load_license(log: IssueCallback, e: etree._Element) -> bp.License | None:
    ali = "{http://www.niso.org/schemas/ali/1.0/}"
    ret = bp.License(MixedContent(), "", None)
    check_no_attrib(log, e)
    ap = ContentParser(log)
    ap.bind(hypertext_element_binder('license-p'), ret.license_p)
    ap.bind_reader(f"{ali}license_ref", read_license_ref, ret)
    ap.parse_array_content(e)
    return None if ret.blank() else ret


def load_permissions(log: IssueCallback, e: etree._Element) -> bp.Permissions | None:
    check_no_attrib(log, e)
    ap = ContentParser(log)
    statement = ap.one(mixed_element_model('copyright-statement'))
    license = ap.one(LoaderModel("license", load_license))
    ap.parse_array_content(e)
    if license.out is None or statement.out is None or statement.out.blank():
        return None
    return bp.Permissions(license.out, bp.Copyright(statement.out))


def read_article_meta(
    log: IssueCallback, e: etree._Element, dest: bp.Baseprint
) -> bool:
    check_no_attrib(log, e)
    p_elements = p_elements_model()
    cp = ContentParser(log)
    title = cp.one(LoaderModel('title-group', load_title_group))
    authors = cp.one(LoaderModel('contrib-group', load_author_group))
    cp.bind(proto_section_binder('abstract', p_elements), dest.abstract)
    permissions = cp.one(LoaderModel('permissions', load_permissions))
    cp.parse_array_content(e)
    if title.out:
        dest.title = title.out
    if authors.out is not None:
        dest.authors = authors.out
    if permissions.out is not None:
        dest.permissions = permissions.out
    return True


def read_article_front(
    log: IssueCallback, e: etree._Element, dest: bp.Baseprint
) -> bool:
    check_no_attrib(log, e)
    cp = ContentParser(log)
    cp.bind_reader('article-meta', read_article_meta, dest)
    cp.parse_array_content(e)
    return True


def read_element_citation(log: IssueCallback, e: etree._Element) -> bp.BiblioReference:
    check_no_attrib(log, e, ['publication-type'])
    ap = ContentParser(log)
    title = ap.one(title_model('article-title'))
    authors = ap.one(ref_authors_model())
    year = ap.one(LoaderModel('year', load_year))
    fields = {}
    for key in bp.BiblioReference.BIBLIO_FIELD_KEYS:
        fields[key] = ap.one(LoaderModel(key, load_string))
    ap.parse_array_content(e)
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


def load_biblio_ref(log: IssueCallback, e: etree._Element) -> bp.BiblioReference | None:
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


def load_ref_list(log: IssueCallback, e: etree._Element) -> bp.RefList | None:
    check_no_attrib(log, e)
    ap = ContentParser(log)
    title = ap.one(title_model('title'))
    references = ap.every(LoaderModel('ref', load_biblio_ref))
    ap.parse_array_content(e)
    return bp.RefList(title.out, list(references))


def read_article_back(log: IssueCallback, e: etree._Element) -> bp.RefList | None:
    check_no_attrib(log, e)
    p = ContentParser(log)
    ref_list = p.one(LoaderModel('ref-list', load_ref_list))
    p.parse_array_content(e)
    return ref_list.out


def load_article(log: IssueCallback , e: etree._Element) -> Baseprint | None:
    lang = '{http://www.w3.org/XML/1998/namespace}lang'
    confirm_attrib_value(log, e, lang, ['en', None])
    check_no_attrib(log, e, [lang])
    ret = bp.Baseprint()
    back = e.find("back")
    if back is not None:
        ret.ref_list = read_article_back(log, back)
        e.remove(back)
    cp = ContentParser(log)
    cp.bind_reader('front', read_article_front, ret)
    cp.bind(proto_section_binder('body', p_elements_model()), ret.body)
    cp.parse_array_content(e)
    if ret.title.blank():
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
    return load_article(log, root)


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
