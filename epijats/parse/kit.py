from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, Protocol, Sequence, TypeAlias, TypeVar

from lxml import etree

from .. import condition as fc


IssueCallback: TypeAlias = Callable[[fc.FormatIssue], None]
EnumT = TypeVar('EnumT', bound=StrEnum)


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
    def __call__(
        self, log: IssueCallback, e: etree._Element, dest: DestConT
    ) -> bool: ...


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


def load_int(log: IssueCallback, e: etree._Element) -> int | None:
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


Sink: TypeAlias = Callable[[ParsedT], None]
Model: TypeAlias = Binder[Sink[ParsedT]]
UnionModel: TypeAlias = UnionBinder[Sink[ParsedT]]


class TagModelBase(Model[ParsedT]):
    def __init__(self, tag: str):
        self.tag = tag

    @abstractmethod
    def load(self, log: IssueCallback, e: etree._Element) -> ParsedT | None: ...

    def bind(self, log: IssueCallback, dest: Sink[ParsedT]) -> Parser:
        return ReaderBinderParser(log, dest, self.tag, LoaderReader(self.load))


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

    def bind(self, log: IssueCallback, dest: DestT) -> Parser:
        return ReaderBinderParser(log, dest, self.tag, self._reader)


class ReaderBinderParser(Parser, Generic[DestT]):
    def __init__(
        self,
        log: IssueCallback,
        dest: DestT,
        tag: str | Iterable[str],
        reader: Reader[DestT]
    ):
        super().__init__(log)
        self.dest = dest
        self._tags = [tag] if isinstance(tag, str) else list(tag)
        self._reader = reader

    def match(self, tag: str) -> ParseFunc | None:
        return self._parse if tag in self._tags else None

    def _parse(self, e: etree._Element) -> bool:
        return self._reader(self.log, e, self.dest)


class LoaderReader(Reader[Sink[ParsedT]]):
    def __init__(self, loader: Loader[ParsedT]):
        self._loader = loader

    def __call__(self, log: IssueCallback, e: etree._Element, dest: Sink[ParsedT]) -> bool:
        parsed = self._loader(log, e)
        if parsed is not None:
            dest(parsed)
        return parsed is not None


def tag_model(tag: str, loader: Loader[ParsedT]) -> Model[ParsedT]:
    return ReaderBinder(tag, LoaderReader(loader))


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


class SingleSubElementReader(Reader[DestT]):
    def __init__(self, binder: Binder[DestT]):
        self._binder = binder

    def __call__(self, log: IssueCallback, e: etree._Element, dest: DestT) -> bool:
        check_no_attrib(log, e)
        cp = ContentParser(log)
        cp.bind(self._binder.once(), dest)
        cp.parse_array_content(e)
        return True


def load_single_sub_element(
    log: IssueCallback, e: etree._Element, model: Model[ParsedT]
) -> ParsedT | None:
    reader = SingleSubElementReader(model)
    ret = Result[ParsedT]()
    reader(log, e, ret)
    return ret.out
