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


Log: TypeAlias = Callable[[fc.FormatIssue], None]
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
            log(fc.IgnoredTail.issue(s))
        s.tail = None


if TYPE_CHECKING:
    ParseFunc: TypeAlias = Callable[[XmlElement], bool]


class Parser(ABC):
    @abstractmethod
    def match(self, xe: XmlElement) -> ParseFunc | None: ...

    def parse_element(self, e: XmlElement) -> bool:
        fun = self.match(e)
        return False if fun is None else fun(e)


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


class Binder(Protocol, Generic[DestConT]):
    def bound_parser(self, log: Log, dest: DestConT, /) -> Parser: ...


class StatelessParser(Parser, Generic[DestT]):
    def __init__(self, match_fun: ParseFunc, parse_fun: ParseFunc):
        self.match_fun = match_fun
        self.parse_fun = parse_fun

    def match(self, xe: XmlElement) -> ParseFunc | None:
        if self.match_fun(xe):
            return self.parse_fun
        return None


class TagBinderBase(ABC, Binder[DestT]):
    def __init__(self, tag: str | StartTag | None = None):
        if tag is None:
            tag = getattr(type(self), 'TAG')
        self.stag = StartTag(tag)

    @abstractmethod
    def read(self, log: IssueCallback, xe: XmlElement, dest: DestT) -> None: ...

    @property
    def tag(self) -> str:
        return self.stag.tag

    def match(self, xe: XmlElement) -> bool:
        return match_start_tag(xe, self.stag)

    def bound_parser(self, log: Log, dest: DestT) -> Parser:
        def parse_fun(xe: XmlElement) -> bool:
            self.read(log, xe, dest)
            return True

        return StatelessParser(self.match, parse_fun)


Sink: TypeAlias = Callable[[ParsedT], None]


class Model(ABC, Binder[Sink[ParsedT]]):
    @abstractmethod
    def match(self, xe: XmlElement) -> bool: ...

    @abstractmethod
    def parse(self, log: Log, xe: XmlElement, dest: Sink[ParsedT]) -> bool: ...

    def bound_parser(self, log: Log, dest: Sink[ParsedT]) -> Parser:
        def parse_fun(xe: XmlElement) -> bool:
            return self.parse(log, xe, dest)

        return StatelessParser(self.match, parse_fun)

    def as_models(self) -> Iterable[Model[ParsedT]]:
        return [self]

    def __or__(self, other: Model[ParsedT]) -> Model[ParsedT]:
        union = list(self.as_models()) + list(other.as_models())
        return UnionModel(union)


class UnionModel(Model[ParsedT]):
    def __init__(self, binders: Iterable[Model[ParsedT]] = ()):
        self._binders = list(binders)

    def match(self, xe: XmlElement) -> bool:
        return any(b.match(xe) for b in self._binders)

    def parse(self, log: Log, xe: XmlElement, dest: Sink[ParsedT]) -> bool:
        for b in self._binders:
            if b.match(xe):
                return b.parse(log, xe, dest)
        return False

    def as_models(self) -> Iterable[Model[ParsedT]]:
        return self._binders

    def __ior__(self, other: Model[ParsedT]) -> UnionModel[ParsedT]:
        self._binders.extend(other.as_models())
        return self


class LoadModel(Model[ParsedT]):
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


class ModModel(LoadModel[ParsedT]):
    @property
    @abstractmethod
    def parsed_type(self) -> type[ParsedT]: ...

    @abstractmethod
    def mod(self, log: Log, xe: XmlElement, target: ParsedT) -> None: ...

    def load(self, log: Log, xe: XmlElement) -> ParsedT | None:
        out = self.parsed_type()
        self.mod(log, xe, out)
        return out

    def bind_mod(self, log: Log, target: ParsedT) -> Parser:
        def parse_fun(xe: XmlElement) -> bool:
            self.mod(log, xe, target)
            return True

        return StatelessParser(self.match, parse_fun)


class TagModelBase(LoadModel[ParsedT]):
    def __init__(self, tag: str | StartTag | None = None):
        if tag is None:
            tag = getattr(type(self), 'TAG')
        self.stag = StartTag(tag)

    @property
    def tag(self) -> str:
        return self.stag.tag

    def match(self, xe: XmlElement) -> bool:
        return match_start_tag(xe, self.stag)


class TagModModelBase(ModModel[ParsedT]):
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

    def load(self, log: IssueCallback, e: XmlElement) -> ParsedT | None:
        return self._loader(log, e)


def tag_model(tag: str, loader: Loader[ParsedT]) -> Model[ParsedT]:
    return LoaderTagModel(tag, loader)


class OnlyOnceParser(Parser):
    def __init__(self, log: Log, parser: Parser):
        self.log = log
        self._parser = parser
        self._parse_done = False

    def match(self, xe: XmlElement) -> ParseFunc | None:
        fun = self._parser.match(xe)
        return None if fun is None else self._parse

    def _parse(self, e: XmlElement) -> bool:
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

    def bound_parser(self, log: IssueCallback, dest: DestT) -> Parser:
        return OnlyOnceParser(log, self.binder.bound_parser(log, dest))


class Outcome(Protocol[ParsedCovT]):
    @property
    def out(self) -> ParsedCovT | None: ...


@dataclass
class SinkDestination(Outcome[ParsedT]):
    out: ParsedT | None = None

    def __call__(self, parsed: ParsedT) -> None:
        self.out = parsed


class Session(ABC):
    def __init__(self, log: Log):
        self.log = log
        self._parsers: list[Parser] = []

    def _add_parser(self, p: Parser) -> None:
        self._parsers.append(p)

    def bind(self, binder: Binder[DestT], dest: DestT) -> None:
        self._add_parser(binder.bound_parser(self.log, dest))

    def bind_mod(self, model: ModModel[ParsedT], target: ParsedT) -> None:
        self._add_parser(model.bind_mod(self.log, target))


class ArrayContentSession(Session):
    def bind_once(self, binder: Binder[DestT], dest: DestT) -> None:
        once = OnlyOnceBinder(binder)
        self._add_parser(once.bound_parser(self.log, dest))

    def one(self, model: Model[ParsedT]) -> Outcome[ParsedT]:
        ret = SinkDestination[ParsedT]()
        once = OnlyOnceBinder(model)
        self._add_parser(once.bound_parser(self.log, ret))
        return ret

    def every(self, model: Model[ParsedT]) -> Sequence[ParsedT]:
        ret: list[ParsedT] = list()
        parser = model.bound_parser(self.log, ret.append)
        self._add_parser(parser)
        return ret

    def parse_content(self, e: XmlElement) -> None:
        prep_array_elements(self.log, e)
        for s in e:
            if not any(p.parse_element(s) for p in self._parsers):
                self.log(fc.UnsupportedElement.issue(s))


class ContentBinder(ABC, Generic[DestT]):
    def __init__(self, dest_type: type[DestT]):
        self.dest_type = dest_type

    @abstractmethod
    def binds(self, sess: Session, dest: DestT) -> None: ...


class MergedElementsContentBinder(ContentBinder[DestT]):
    def __init__(self, child_model: ModModel[DestT]) -> None:
        super().__init__(child_model.parsed_type)
        self.child_model = child_model

    def binds(self, sess: Session, dest: DestT) -> None:
        sess.bind_mod(self.child_model, dest)


class ContentInElementModel(TagModModelBase[ParsedT]):
    def __init__(self, tag: str, content: ContentBinder[ParsedT]):
        super().__init__(tag)
        self.content = content

    @property
    def parsed_type(self) -> type[ParsedT]:
        return self.content.dest_type

    def mod(self, log: Log, xe: XmlElement, target: ParsedT) -> None:
        check_no_attrib(log, xe, self.stag.attrib.keys())
        sess = ArrayContentSession(log)
        self.content.binds(sess, target)
        sess.parse_content(xe)
