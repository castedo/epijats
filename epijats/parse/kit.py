from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, Protocol, TYPE_CHECKING, TypeAlias, TypeVar

from .. import condition as fc
from ..tree import Element, StartTag

if TYPE_CHECKING:
    from ..xml import XmlElement
    import lxml.etree

    AttribView: TypeAlias = lxml.etree._Attrib | Mapping[str, str]


IssueCallback: TypeAlias = Callable[[fc.FormatIssue], None]
EnumT = TypeVar('EnumT', bound=StrEnum)


def issue(
    log: IssueCallback,
    condition: fc.FormatCondition,
    sourceline: int | None = None,
    info: str | None = None,
) -> None:
    return log(fc.FormatIssue(condition, sourceline, info))


def match_start_tag(xe: XmlElement, ok: StartTag) -> bool:
    if isinstance(xe.tag, str) and xe.tag == ok.tag:
        for key, value in ok.attrib.items():
            if xe.attrib.get(key) != value:
                return False
        return True
    return False


def check_no_attrib(
    log: IssueCallback, e: XmlElement, ignore: Iterable[str] = []
) -> None:
    for k in e.attrib.keys():
        if k not in ignore:
            log(fc.UnsupportedAttribute.issue(e, k))


def confirm_attrib_value(
    log: IssueCallback, e: XmlElement, key: str, ok: Iterable[str | None]
) -> bool:
    got = e.attrib.get(key)
    if got in ok:
        return True
    else:
        log(fc.UnsupportedAttributeValue.issue(e, key, got))
        return False


def copy_ok_attrib_values(
    log: IssueCallback,
    e: XmlElement,
    ok_keys: Iterable[str],
    dest: MutableMapping[str, str],
) -> None:
    for key, value in e.attrib.items():
        if key in ok_keys:
            dest[key] = value
        else:
            log(fc.UnsupportedAttribute.issue(e, key))


def get_enum_value(
    log: IssueCallback, e: XmlElement, key: str, enum: type[EnumT]
) -> EnumT | None:
    ret: EnumT | None = None
    if got := e.attrib.get(key):
        if got in enum:
            ret = enum(got)
        else:
            log(fc.UnsupportedAttributeValue.issue(e, key, got))
    return ret


def prep_array_elements(log: IssueCallback, e: XmlElement) -> None:
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

    def check_no_attrib(self, e: XmlElement, ignore: Iterable[str] = ()) -> None:
        check_no_attrib(self.log, e, ignore)

    def prep_array_elements(self, e: XmlElement) -> None:
        prep_array_elements(self.log, e)


if TYPE_CHECKING:
    ParseFunc: TypeAlias = Callable[[XmlElement], bool]


class Parser(Validator):
    @abstractmethod
    def match(self, xe: XmlElement) -> ParseFunc | None: ...

    def parse_element(self, e: XmlElement) -> bool:
        fun = self.match(e)
        return False if fun is None else fun(e)

    def parse_array_content(self, e: XmlElement) -> None:
        prep_array_elements(self.log, e)
        for s in e:
            if not self.parse_element(s):
                self.log(fc.UnsupportedElement.issue(s))


class UnionParser(Parser):
    def __init__(self, log: IssueCallback, parsers: Iterable[Parser] = ()):
        super().__init__(log)
        self._parsers = list(parsers)

    def match(self, xe: XmlElement) -> ParseFunc | None:
        for p in self._parsers:
            fun = p.match(xe)
            if fun is not None:
                return fun
        return None


class SingleElementParser(Parser):
    def __init__(self, log: IssueCallback, tag: str, content_parser: Parser):
        super().__init__(log)
        self.tag = tag
        self.content_parser = content_parser

    def match(self, xe: XmlElement) -> ParseFunc | None:
        return self._parse if xe.tag == self.tag else None

    def _parse(self, e: XmlElement) -> bool:
        check_no_attrib(self.log, e)
        self.content_parser.parse_array_content(e)
        return True


DestT = TypeVar('DestT')
DestConT = TypeVar('DestConT', contravariant=True)

ParsedT = TypeVar('ParsedT')
ParsedCovT = TypeVar('ParsedCovT', covariant=True)


class Loader(Protocol, Generic[ParsedCovT]):
    def __call__(self, log: IssueCallback, e: XmlElement) -> ParsedCovT | None: ...


def load_string(log: IssueCallback, e: XmlElement) -> str:
    check_no_attrib(log, e)
    return load_string_content(log, e)


def load_string_content(log: IssueCallback, e: XmlElement) -> str:
    frags = []
    if e.text:
        frags.append(e.text)
    for s in e:
        log(fc.UnsupportedElement.issue(s))
        frags += load_string_content(log, s)
        if s.tail:
            frags.append(s.tail)
    return "".join(frags)


def load_int(
    log: IssueCallback, e: XmlElement, *, strip_trailing_period: bool = False
) -> int | None:
    for s in e:
        log(fc.UnsupportedElement.issue(s))
        if s.tail and s.tail.strip():
            log(fc.IgnoredText.issue(e))
    try:
        text = e.text or ""
        if strip_trailing_period:
            text = text.rstrip().rstrip('.')
        return int(text)
    except ValueError:
        log(fc.InvalidInteger.issue(e, text))
        return None


class Binder(ABC, Generic[DestT]):
    @abstractmethod
    def bind(self, log: IssueCallback, dest: DestT) -> Parser: ...

    def as_binders(self) -> Iterable[Binder[DestT]]:
        return [self]

    def once(self: Binder[DestT]) -> Binder[DestT]:
        return OnlyOnceBinder(self)

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


class SingleElementBinder(Binder[DestT]):
    def __init__(self, tag: str, content_binder: Binder[DestT]):
        self.tag = tag
        self.content_binder = content_binder

    def bind(self, log: IssueCallback, dest: DestT) -> Parser:
        return SingleElementParser(log, self.tag, self.content_binder.bind(log, dest))


class StatelessParser(Parser, Generic[DestT]):
    def __init__(self, log: IssueCallback, dest: DestT, binder: ParserBinder[DestT]):
        super().__init__(log)
        self.dest = dest
        self._binder = binder

    def match(self, xe: XmlElement) -> ParseFunc | None:
        if self._binder.match(xe):
            return self._parse
        return None

    def _parse(self, e: XmlElement) -> bool:
        return self._binder.parse(self.log, e, self.dest)


class ParserBinder(Binder[DestT]):
    @abstractmethod
    def match(self, xe: XmlElement) -> bool: ...

    @abstractmethod
    def parse(self, log: IssueCallback, xe: XmlElement, dest: DestT) -> bool: ...

    def bind(self, log: IssueCallback, dest: DestT) -> Parser:
        return StatelessParser(log, dest, self)


class Reader(ParserBinder[DestT]):
    def __init__(self, tag: str | None = None):
        if tag is None:
            tag = getattr(type(self), 'TAG')
        self.tag = tag

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == self.tag

    @abstractmethod
    def read(self, log: IssueCallback, xe: XmlElement, dest: DestT) -> None: ...

    def parse(self, log: IssueCallback, xe: XmlElement, dest: DestT) -> bool:
        self.read(log, xe, dest)
        return True


Sink: TypeAlias = Callable[[ParsedT], None]
Model: TypeAlias = Binder[Sink[ParsedT]]
UnionModel: TypeAlias = UnionBinder[Sink[ParsedT]]


class ModelBase(ParserBinder[Sink[ParsedT]]):
    @abstractmethod
    def load(self, log: IssueCallback, e: XmlElement) -> ParsedT | None: ...

    def load_if_match(self, log: IssueCallback, e: XmlElement) -> ParsedT | None:
        if self.match(e):
            return self.load(log, e)
        else:
            return None

    def parse(self, log: IssueCallback, xe: XmlElement, dest: Sink[ParsedT]) -> bool:
        parsed = self.load(log, xe)
        if parsed is not None:
            if isinstance(parsed, Element) and xe.tail:
                parsed.tail = xe.tail
            # mypy v1.9 has issue below but not v1.15
            dest(parsed)  # type: ignore[arg-type, unused-ignore]
        return parsed is not None

    def bind(self, log: IssueCallback, dest: Sink[ParsedT]) -> Parser:
        return StatelessParser(log, dest, self)


class TagModelBase(ModelBase[ParsedT]):
    def __init__(self, tag: str | StartTag):
        self.stag = StartTag(tag)

    @property
    def tag(self) -> str:
        return self.stag.tag

    def match(self, xe: XmlElement) -> bool:
        return match_start_tag(xe, self.stag)


class LoaderTagModel(TagModelBase[ParsedT]):
    def __init__(self, tag: str, loader: Loader[ParsedT]):
        super().__init__(tag)
        self._loader = loader

    def load(self, log: IssueCallback, e: XmlElement) -> ParsedT | None:
        return self._loader(log, e)


def tag_model(tag: str, loader: Loader[ParsedT]) -> Model[ParsedT]:
    return LoaderTagModel(tag, loader)


class OnlyOnceParser(Parser):
    def __init__(self, parser: Parser):
        super().__init__(parser.log)
        self._parser = parser
        self._parse_done = False

    def match(self, xe: XmlElement) -> ParseFunc | None:
        fun = self._parser.match(xe)
        return None if fun is None else self._parse

    def _parse(self, e: XmlElement) -> bool:
        if not isinstance(e.tag, str):
            return False
        parse_func = self._parser.match(e)
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


class ContentParser(UnionParser):
    def __init__(self, log: IssueCallback):
        super().__init__(log)

    def one(self, model: Model[ParsedT]) -> Result[ParsedT]:
        ret = Result[ParsedT]()
        sink: Sink[ParsedT] = ret
        self.bind(model.once(), sink)
        return ret

    def every(self, binder: Binder[Sink[ParsedT]]) -> Sequence[ParsedT]:
        ret: list[ParsedT] = list()
        self.bind(binder, ret.append)
        return ret

    def bind(self, binder: Binder[DestT], dest: DestT) -> None:
        self._parsers.append(binder.bind(self.log, dest))


class SingleSubElementLoader(Loader[ParsedT]):
    def __init__(self, model: Model[ParsedT]):
        self._model = model

    def __call__(self, log: IssueCallback, e: XmlElement) -> ParsedT | None:
        check_no_attrib(log, e)
        cp = ContentParser(log)
        result = cp.one(self._model)
        cp.parse_array_content(e)
        return result.out
