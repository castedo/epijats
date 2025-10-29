from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping, MutableMapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, Protocol, TYPE_CHECKING, TypeAlias, TypeVar

from .. import condition as fc
from ..tree import StartTag

if TYPE_CHECKING:
    from ..typeshed import XmlElement
    import lxml.etree

    AttribView: TypeAlias = lxml.etree._Attrib | Mapping[str, str]


Log: TypeAlias = Callable[[fc.FormatIssue], None]
EnumT = TypeVar('EnumT', bound=StrEnum)


def nolog(issue: fc.FormatIssue) -> None:
    pass


def issue(
    log: Log,
    condition: fc.FormatCondition,
    sourceline: int | None = None,
    info: str | None = None,
) -> None:
    return log(fc.FormatIssue(condition, sourceline, info))


def check_no_attrib(log: Log, e: XmlElement, ignore: Iterable[str] = []) -> None:
    for k in e.attrib.keys():
        if k not in ignore:
            log(fc.UnsupportedAttribute.issue(e, k))


def check_required_child(log: Log, xe: XmlElement, tags: Iterable[str] | str) -> None:
    if isinstance(tags, str):
        tags = [tags]
    for child_tag in tags:
        if xe.find(child_tag) is None:
            log(fc.MissingChild.issue(xe, child_tag))


def confirm_attrib_value(
    log: Log, e: XmlElement, key: str, ok: Iterable[str | None]
) -> bool:
    got = e.attrib.get(key)
    if got in ok:
        return True
    else:
        log(fc.UnsupportedAttributeValue.issue(e, key, got))
        return False


def copy_ok_attrib_values(
    log: Log,
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
    log: Log, e: XmlElement, key: str, enum: type[EnumT]
) -> EnumT | None:
    ret: EnumT | None = None
    if got := e.attrib.get(key):
        if got in enum:
            ret = enum(got)
        else:
            log(fc.UnsupportedAttributeValue.issue(e, key, got))
    return ret


DestT = TypeVar('DestT')
DestConT = TypeVar('DestConT', contravariant=True)

ParsedT = TypeVar('ParsedT')
ParsedCovT = TypeVar('ParsedCovT', covariant=True)


class Loader(Protocol, Generic[ParsedCovT]):
    def __call__(self, log: Log, e: XmlElement) -> ParsedCovT | None: ...


def load_string(log: Log, e: XmlElement) -> str:
    check_no_attrib(log, e)
    return load_string_content(log, e)


def load_string_content(log: Log, e: XmlElement) -> str:
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
    log: Log, e: XmlElement, *, strip_trailing_period: bool = False
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


class Parser(ABC, Generic[DestConT]):
    @abstractmethod
    def match(self, xe: XmlElement) -> bool: ...

    @abstractmethod
    def parse(self, log: Log, xe: XmlElement, dest: DestConT) -> None: ...

    def parse_str(self, log: Log, s: str, dest: DestConT) -> bool:
        return False

    def parse_content(self, log: Log, xe: XmlElement, dest: DestConT) -> None:
        if xe.text:
            if not self.parse_str(log, xe.text, dest):
                log(fc.IgnoredText.issue(xe))
        for s in xe:
            if self.match(s):
                self.parse(log, s, dest)
            else:
                log(fc.UnsupportedElement.issue(s))
                self.parse_content(log, s, dest)
            if s.tail:
                if not self.parse_str(log, s.tail, dest):
                    log(fc.IgnoredTail.issue(s))

    def __or__(self, other: Parser[DestConT]) -> Parser[DestConT]:
        ret = UnionParser[DestConT]()
        ret |= self
        ret |= other
        return ret


class UnionParser(Parser[DestT]):
    def __init__(self) -> None:
        self._parsers: list[Parser[DestT]] = []

    def match(self, xe: XmlElement) -> bool:
        return any(p.match(xe) for p in self._parsers)

    def parse(self, log: Log, xe: XmlElement, dest: DestT) -> None:
        for p in self._parsers:
            if p.match(xe):
                p.parse(log, xe, dest)
                return

    def parse_str(self, log: Log, s: str, dest: DestT) -> bool:
        return any(p.parse_str(log, s, dest) for p in self._parsers)

    def __or__(self, other: Parser[DestT]) -> Parser[DestT]:
        ret = UnionParser[DestT]()
        ret._parsers = [self, other]
        return ret

    def __ior__(self, other: Parser[DestT]) -> UnionParser[DestT]:
        self._parsers.append(other)
        return self


Sink: TypeAlias = Callable[[ParsedT], None]
Model: TypeAlias = Parser[Sink[ParsedT]]
UnionModel: TypeAlias = UnionParser[Sink[ParsedT]]


class LoadModelBase(Model[ParsedT]):
    @abstractmethod
    def load(self, log: Log, e: XmlElement) -> ParsedT | None: ...

    def load_if_match(self, log: Log, e: XmlElement) -> ParsedT | None:
        if self.match(e):
            return self.load(log, e)
        else:
            return None

    def parse(self, log: Log, xe: XmlElement, dest: Sink[ParsedT]) -> None:
        parsed = self.load(log, xe)
        if parsed is not None:
            # mypy v1.9 has issue below but not v1.15
            dest(parsed)  # type: ignore[arg-type, unused-ignore]


class TagModelBase(LoadModelBase[ParsedT]):
    def __init__(self, tag: str | StartTag):
        self.stag = StartTag(tag)

    def match(self, xe: XmlElement) -> bool:
        return self.stag.issubset(xe)


class LoaderTagModel(TagModelBase[ParsedT]):
    def __init__(self, tag: str, loader: Loader[ParsedT]):
        super().__init__(tag)
        self._loader = loader

    def load(self, log: Log, e: XmlElement) -> ParsedT | None:
        return self._loader(log, e)


class Outcome(Protocol[ParsedCovT]):
    @property
    def out(self) -> ParsedCovT | None: ...


@dataclass
class SinkDestination(Outcome[ParsedT]):
    out: ParsedT | None = None

    def __call__(self, parsed: ParsedT) -> None:
        self.out = parsed
