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


def match_start_tag(xe: XmlElement, ok: StartTag) -> bool:
    if isinstance(xe.tag, str) and xe.tag == ok.tag:
        for key, value in ok.attrib.items():
            if xe.attrib.get(key) != value:
                return False
        return True
    return False


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


class Binder(ABC, Generic[DestConT]):
    @abstractmethod
    def match(self, xe: XmlElement) -> bool: ...

    @abstractmethod
    def parse(self, log: Log, xe: XmlElement, dest: DestConT) -> None: ...

    def __or__(self, other: Binder[DestConT]) -> Binder[DestConT]:
        ret = UnionBinder[DestConT]()
        ret |= self
        ret |= other
        return ret


class UnionBinder(Binder[DestT]):
    def __init__(self) -> None:
        self._binders: list[Binder[DestT]] = []

    def match(self, xe: XmlElement) -> bool:
        return any(b.match(xe) for b in self._binders)

    def parse(self, log: Log, xe: XmlElement, dest: DestT) -> None:
        for b in self._binders:
            if b.match(xe):
                b.parse(log, xe, dest)
                return

    def __or__(self, other: Binder[DestT]) -> Binder[DestT]:
        ret = UnionBinder[DestT]()
        ret._binders = [self, other]
        return ret

    def __ior__(self, other: Binder[DestT]) -> UnionBinder[DestT]:
        self._binders.append(other)
        return self


class TagBinderBase(Binder[DestT]):
    def __init__(self, tag: str | StartTag | None = None):
        if tag is None:
            tag = getattr(type(self), 'TAG')
        self.stag = StartTag(tag)

    @property
    def tag(self) -> str:
        return self.stag.tag

    def match(self, xe: XmlElement) -> bool:
        return match_start_tag(xe, self.stag)


Sink: TypeAlias = Callable[[ParsedT], None]
Model: TypeAlias = Binder[Sink[ParsedT]]
UnionModel: TypeAlias = UnionBinder[Sink[ParsedT]]


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
    def __init__(self, tag: str | StartTag | None = None):
        if tag is None:
            tag = getattr(type(self), 'TAG')
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
