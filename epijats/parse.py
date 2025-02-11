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


class Binder(ABC, Generic[DestT]):
    @abstractmethod
    def bind(self, log: IssueCallback, dest: DestT) -> Parser: ...

    def as_binders(self) -> Iterable[Binder[DestT]]:
        return [self]

    def __or__(self, other: Binder[DestT]) -> Binder[DestT]:
        union = list(self.as_binders()) + list(other.as_binders())
        return UnionBinder(union)


class UnionBinder(Binder[DestT]):
    def __init__(self, binders: Iterable[Binder[DestT]] = ()):
        self._binders = list(binders)

    def bind(self, log: IssueCallback, dest: DestT) -> Parser:
        parsers = [b.bind(log, dest) for b in self._binders]
        return UnionParser(log, parsers)

    def as_binders(self) -> Iterable[Binder[DestT]]:
        return self._binders

    def __ior__(self, other: Binder[DestT]) -> UnionBinder[DestT]:
        self._binders.extend(other.as_binders())
        return self


Sink: TypeAlias = Callable[[ParsedT], None]
Model: TypeAlias = Binder[Sink[ParsedT]]
UnionModel: TypeAlias = UnionBinder[Sink[ParsedT]]
EModel: TypeAlias = Model[Element]


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


class LoaderParser(Parser, Generic[ParsedT]):
    def __init__(
        self,
        log: IssueCallback,
        dest: Sink[ParsedT],
        tags: str | Iterable[str],
        loader: Loader[ParsedT]
    ):
        super().__init__(log)
        self.dest = dest
        self._tags = [tags] if isinstance(tags, str) else list(tags)
        self.loader = loader

    def match(self, tag: str) -> ParseFunc | None:
        return self._parse if tag in self._tags else None

    def _parse(self, e: etree._Element) -> bool:
        result = self.loader(self.log, e)
        if result is not None:
            if isinstance(result, Element) and e.tail:
                result.tail = e.tail
            self.dest(result)
        return result is not None


class LoaderModel(Model[ParsedT]):
    def __init__(self, tag: str, loader: Loader[ParsedT]):
        self._tag = tag
        self._loader = loader

    def bind(self, log: IssueCallback, dest: Sink[ParsedT]) -> Parser:
        return LoaderParser(log, dest, self._tag, self._loader)


class OnlyOnceParser(Parser):
    def __init__(self, parser: Parser):
        super().__init__(parser.log)
        self._parser = parser
        self._parse_done = False

    def match(self, tag: str) -> ParseFunc | None:
        fun = self._parser.match(tag)
        return None if fun is None else self._parse

    def _parse(self, e: etree._Element) -> bool:
        if not isinstance(e.tag, str):
            return False
        parse_func = self._parser.match(e.tag)
        if parse_func is None:
            return False
        if not self._parse_done:
            self._parse_done = parse_func(e)
        else:
            self.log(fc.ExcessElement.issue(e))
        return True


class OnlyOnceBinder(Binder[DestT]):
    def __init__(self, binder: Binder[DestT]):
        self.binder = binder

    def bind(self, log: IssueCallback, dest: DestT) -> Parser:
        return OnlyOnceParser(self.binder.bind(log, dest))


@dataclass
class Result(Generic[ParsedT]):
    out: ParsedT | None = None

    def __call__(self, parsed: ParsedT) -> None:
        self.out = parsed


class FirstReadBinder(Binder[Result[ParsedT]]):
    def __init__(self, model: Model[ParsedT]):
        self._model = model

    def bind(self, log: IssueCallback, dest: Result[ParsedT]) -> Parser:
        return OnlyOnceParser(self._model.bind(log, dest))


class ContentParser(UnionParser):
    def __init__(self, log: IssueCallback):
        super().__init__(log)

    def one(self, model: Model[ParsedT]) -> Result[ParsedT]:
        ret = Result[ParsedT]()
        self.bind(FirstReadBinder(model), ret)
        return ret

    def every(self, binder: Binder[Sink[ParsedT]]) -> Sequence[ParsedT]:
        ret: list[ParsedT] = list()
        self.bind(binder, ret.append)
        return ret

    def bind(self, binder: Binder[DestT], dest: DestT) -> None:
        self._parsers.append(binder.bind(self.log, dest))

    def once(self, binder: Binder[DestT], dest: DestT) -> None:
        self.bind(OnlyOnceBinder(binder), dest)

    def bind_reader(self, tag: str, reader: Reader[DestT], dest: DestT) -> None:
        self.bind(ReaderBinder(tag, reader), dest)


class SingleSubElementReader(Reader[DestT]):
    def __init__(self, binder: Binder[DestT]):
        self._binder = binder

    def __call__(self, log: IssueCallback, e: etree._Element, dest: DestT) -> bool:
        check_no_attrib(log, e)
        cp = ContentParser(log)
        cp.once(self._binder, dest)
        cp.parse_array_content(e)
        return True


def load_single_sub_element(
    log: IssueCallback, e: etree._Element, model: Model[ParsedT]
) -> ParsedT | None:
    reader = SingleSubElementReader(model)
    ret = Result[ParsedT]()
    reader(log, e, ret)
    return ret.out


def parse_mixed_content(
    log: IssueCallback, e: etree._Element, emodel: EModel, dest: MixedContent
) -> None:
    dest.append_text(e.text)
    eparser = emodel.bind(log, dest.append)
    for s in e:
        if not eparser.parse_element(s):
            log(fc.UnsupportedElement.issue(s))
            parse_mixed_content(log, s, emodel, dest)
            dest.append_text(s.tail)


class BaseModel(Model[ParsedT]):
    def __init__(self, tag: str):
        self.tag = tag

    @abstractmethod
    def load(self, log: IssueCallback, e: etree._Element) -> ParsedT | None: ...

    def bind(self, log: IssueCallback, dest: Sink[ParsedT]) -> Parser:
        return LoaderParser(log, dest, self.tag, self.load)


class DataElementModel(BaseModel[Element]):
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


class TextElementModel(Model[Element]):
    def __init__(self, tagmap: dict[str, str], content_model: EModel | bool = True):
        self.tagmap = tagmap
        self.content_model: EModel | None = None
        if content_model:
            self.content_model = self if content_model == True else content_model

    def bind(self, log: IssueCallback, dest: Sink[Element]) -> Parser:
        return LoaderParser(log, dest, self.tagmap.keys(), self.load)

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


class ExtLinkModel(BaseModel[Element]):
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
            ret = bp.Hyperlink(href)
            parse_mixed_content(log, e, self.content_model, ret.content)
            return ret


class CrossReferenceModel(BaseModel[Element]):
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


class ListModel(BaseModel[Element]):
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


class TableCellModel(BaseModel[Element]):
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


def title_group_model() -> Model[MixedContent]:
    reader = SingleSubElementReader(title_model('article-title'))
    return ReaderBinder('title-group', reader)


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


class AutoCorrectModel(Model[Element]):
    def __init__(self, p_elements: EModel):
        self.p_elements = p_elements

    def bind(self, log: IssueCallback, dest: Sink[Element]) -> Parser:
        return AutoCorrectParser(log, dest, self.p_elements)


class AutoCorrectParser(Parser):
    def __init__(self, log: IssueCallback, dest: Sink[Element], p_elements: EModel):
        super().__init__(log)
        self.dest = dest
        self._parser = p_elements.bind(log, self._dest)

    def _dest(self, parsed_p_element: Element) -> None:
        correction = make_paragraph("")
        correction.content.append(parsed_p_element)
        self.dest(correction)

    def match(self, tag: str) -> ParseFunc | None:
        return self._parser.match(tag)


class ProtoSectionContentBinder(Binder[bp.ProtoSection]):
    def __init__(self, p_elements: EModel, p_level: EModel):
        self.p_elements = p_elements
        self.p_level = p_level

    def bind(self, log: IssueCallback, dest: bp.ProtoSection) -> Parser:
        ret = ContentParser(log)
        ret.bind(self.p_level, dest.presection.append)
        ret.bind(AutoCorrectModel(self.p_elements), dest.presection.append)
        ret.bind(section_model(self.p_elements), dest.subsections.append)
        return ret


def proto_section_binder(tag: str, p_elements: EModel) -> Binder[bp.ProtoSection]:
    p_level = TextElementModel({'p': 'p'}, p_elements)
    return SingleElementBinder(tag, ProtoSectionContentBinder(p_elements,p_level))


class SectionLoader(Loader[bp.Section]):
    def __init__(self, p_elements: EModel):
        p_level = p_level_model(p_elements)
        self._proto = ProtoSectionContentBinder(p_elements, p_level)

    def __call__(self, log: IssueCallback, e: etree._Element) -> bp.Section | None:
        check_no_attrib(log, e, ['id'])
        ret = bp.Section([],[], e.attrib.get('id'), MixedContent())
        cp = ContentParser(log)
        cp.bind(title_binder('title'), ret.title)
        cp.bind(self._proto, ret)
        cp.parse_array_content(e)
        return ret


def section_model(p_elements: EModel) -> Model[bp.Section]:
    return LoaderModel('sec', SectionLoader(p_elements))


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
    hypertext = UnionModel[Element]()
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
    p_elements = UnionModel[Element]()
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
    p_level = UnionModel[Element]()
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
    ap.once(hypertext_element_binder('license-p'), ret.license_p)
    ap.once(ReaderBinder(f"{ali}license_ref", read_license_ref), ret)
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
    title = cp.one(title_group_model())
    authors = cp.one(LoaderModel('contrib-group', load_author_group))
    cp.once(proto_section_binder('abstract', p_elements), dest.abstract)
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
    cp.once(ReaderBinder('article-meta', read_article_meta), dest)
    cp.parse_array_content(e)
    return True


def read_element_citation(
    log: IssueCallback, e: etree._Element, dest: bp.BiblioReference
) -> bool:
    check_no_attrib(log, e, ['publication-type'])
    ap = ContentParser(log)
    title = ap.one(title_model('article-title'))
    authors = ap.one(ref_authors_model())
    year = ap.one(LoaderModel('year', load_year))
    fields = {}
    for key in bp.BiblioReference.BIBLIO_FIELD_KEYS:
        fields[key] = ap.one(LoaderModel(key, load_string))
    ap.parse_array_content(e)
    dest.publication_type = e.get('publication-type', '')
    if dest.publication_type not in [
        'book',
        'confproc',
        'journal',
        'other',
        'patent',
        'webpage',
    ]:
        log(
            fc.UnsupportedAttributeValue.issue(
                 e, 'publication-type', dest.publication_type
            )
        )
    dest.article_title = title.out
    if authors.out:
        dest.authors = authors.out
    dest.year = year.out
    for key, parser in fields.items():
        if parser.out:
            dest.biblio_fields[key] = parser.out
    return True


def load_biblio_ref(log: IssueCallback, e: etree._Element) -> bp.BiblioReference | None:
    ret = bp.BiblioReference()
    check_no_attrib(log, e, ['id'])
    cp = ContentParser(log)
    cp.once(ReaderBinder('element-citation', read_element_citation), ret)
    cp.parse_array_content(e)
    ret.id = e.attrib.get('id', "")
    return ret


class RefListModel(BaseModel[bp.RefList]):
    def __init__(self) -> None:
        super().__init__('ref-list')

    def load(self, log: IssueCallback, e: etree._Element) -> bp.RefList | None:
        check_no_attrib(log, e)
        cp = ContentParser(log)
        title = cp.one(title_model('title'))
        references = cp.every(LoaderModel('ref', load_biblio_ref))
        cp.parse_array_content(e)
        return bp.RefList(title.out, list(references))


def load_article(log: IssueCallback , e: etree._Element) -> bp.Baseprint | None:
    lang = '{http://www.w3.org/XML/1998/namespace}lang'
    confirm_attrib_value(log, e, lang, ['en', None])
    check_no_attrib(log, e, [lang])
    ret = bp.Baseprint()
    back = e.find("back")
    if back is not None:
        ret.ref_list = load_single_sub_element(log, back, RefListModel())
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
) -> bp.Baseprint | None:
    for pi in root.xpath("//processing-instruction()"):
        log(fc.ProcessingInstruction.issue(pi))
        etree.strip_elements(root, pi.tag, with_tail=False)
    if root.tag != 'article':
        log(fc.UnsupportedElement.issue(root))
        return None
    return load_article(log, root)


def parse_baseprint(
    src: Path, log: IssueCallback = ignore_issue
) -> bp.Baseprint | None:
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
