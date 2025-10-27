"""Parsing of XML content."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from typing import Generic, Protocol, TYPE_CHECKING, TypeAlias

from .. import condition as fc
from . import kit
from ..tree import (
    AppendT,
    ArrayContent,
    Element,
    Inline,
    MarkupBlock,
    MixedContent,
    MixedParentElement,
    MutableArrayContent,
)
from .kit import (
    Binder,
    DestT,
    Log,
    Model,
    ParsedT,
    Sink,
)

if TYPE_CHECKING:
    from ..typeshed import XmlElement


def _parse_array_content(
    log: Log, e: XmlElement, parsers: Iterable[Parser] | Parser
) -> None:
    if isinstance(parsers, Parser):
        parsers = [parsers]
    if e.text and e.text.strip():
        log(fc.IgnoredText.issue(e))
    for s in e:
        tail = s.tail
        s.tail = None
        if not any(p.parse_element(s) for p in parsers):
            log(fc.UnsupportedElement.issue(s))
        if tail and tail.strip():
            log(fc.IgnoredTail.issue(s))


if TYPE_CHECKING:
    ParseFunc: TypeAlias = Callable[[XmlElement], None]


class Parser(ABC):
    @abstractmethod
    def match(self, xe: XmlElement) -> ParseFunc | None:
        """Test whether Parser handles an element, without issue logging."""
        ...

    def parse_element(self, e: XmlElement) -> bool:
        """Try parsing element.

        Logs issues if XmlElement is matched/handled.

        Returns:
          True if parser matches/handles the XmlElement and parsed successfully.
          False if parser does not match/handle the XmlElement or parsing failed.
        """

        fun = self.match(e)
        if fun is not None:
            fun(e)
        return fun is not None


class StatelessParser(Parser, Generic[DestT]):
    def __init__(self, binder: Binder[DestT], log: Log, dest: DestT):
        def parse_fun(xe: XmlElement) -> None:
            binder.parse(log, xe, dest)

        self.match_fun = binder.match
        self.parse_fun = parse_fun

    def match(self, xe: XmlElement) -> ParseFunc | None:
        if self.match_fun(xe):
            return self.parse_fun
        return None


def parse_array_content(
    log: Log, xe: XmlElement, binder: Binder[DestT], dest: DestT
) -> None:
    _parse_array_content(log, xe, StatelessParser(binder, log, dest))


class OnlyOnceParser(Parser):
    def __init__(self, log: Log, binder: Binder[DestT], dest: DestT):
        self.log = log
        self._parser = StatelessParser(binder, log, dest)
        self._parse_done = False

    def match(self, xe: XmlElement) -> ParseFunc | None:
        fun = self._parser.match(xe)
        return None if fun is None else self._parse

    def _parse(self, e: XmlElement) -> None:
        parse_func = self._parser.match(e)
        if parse_func is None:
            return
        if not self._parse_done:
            parse_func(e)
            self._parse_done = True
        else:
            self.log(fc.ExcessElement.issue(e))


class ArrayContentSession:
    """Parsing session for array (non-mixed, data-oriented) XML content."""

    def __init__(self, log: Log):
        self.log = log
        self._parsers: list[Parser] = []

    def bind(self, binder: Binder[DestT], dest: DestT) -> None:
        self._parsers.append(StatelessParser(binder, self.log, dest))

    def bind_once(self, binder: Binder[DestT], dest: DestT) -> None:
        self._parsers.append(OnlyOnceParser(self.log, binder, dest))

    def one(self, model: Model[ParsedT]) -> kit.Outcome[ParsedT]:
        ret = kit.SinkDestination[ParsedT]()
        self.bind_once(model, ret)
        return ret

    def parse_content(self, e: XmlElement) -> None:
        _parse_array_content(self.log, e, self._parsers)


MixedModel: TypeAlias = Model[str | Inline]
UnionMixedModel: TypeAlias = kit.UnionModel[str | Inline]


def parse_mixed_content(
    log: Log, e: XmlElement, emodel: Model[str | Inline], dest: Sink[str | Inline]
) -> None:
    if e.text:
        dest(e.text)
    for s in e:
        if emodel.match(s):
            emodel.parse(log, s, dest)
        else:
            log(fc.UnsupportedElement.issue(s))
            parse_mixed_content(log, s, emodel, dest)
            if s.tail:
                dest(s.tail)


class MixedModelBase(MixedModel):
    @abstractmethod
    def load(self, log: Log, xe: XmlElement) -> Inline | None: ...

    def parse(self, log: Log, xe: XmlElement, dest: Sink[str | Inline]) -> None:
        try:
            parsed = self.load(log, xe)
            if parsed is not None:
                if xe.tail:
                    parsed.tail = xe.tail
                dest(parsed)
        except ValueError:
            log(fc.InvalidElementData.issue(xe))
            parse_mixed_content(log, xe, self, dest)
            if xe.tail:
                dest(xe.tail)


class ContentMold(Protocol, Generic[AppendT]):
    def read(self, log: Log, xe: XmlElement, dest: Sink[AppendT]) -> None: ...


class MixedContentMold(ContentMold[str | Inline]):
    def __init__(self, child_model: MixedModel):
        self.content_type = MixedContent
        self.child_model = child_model

    def read(self, log: Log, xe: XmlElement, dest: Sink[str | Inline]) -> None:
        parse_mixed_content(log, xe, self.child_model, dest)


ArrayContentMold: TypeAlias = ContentMold[Element]


class DataContentMold(ArrayContentMold):
    def __init__(self, child_model: Model[Element]):
        self.content_type = ArrayContent
        self.child_model = child_model

    def read(self, log: Log, xe: XmlElement, dest: Sink[Element]) -> None:
        parse_array_content(log, xe, self.child_model, dest)


class PendingMarkupBlock:
    def __init__(self, dest: Sink[Element], init: MixedParentElement | None = None):
        self.dest = dest
        self._pending = init

    def close(self) -> bool:
        if self._pending is not None and not self._pending.content.blank():
            self.dest(self._pending)
            self._pending = None
            return True
        return False

    def append(self, x: str | Inline) -> None:
        if self._pending is None:
            self._pending = MarkupBlock()
        self._pending.append(x)


class RollContentMold(ArrayContentMold):
    def __init__(self, block_model: Model[Element], inline_model: MixedModel):
        self.content_type = MutableArrayContent
        self.block_model = block_model
        self.inline_model = inline_model

    def read(self, log: Log, xe: XmlElement, dest: Sink[Element]) -> None:
        pending = PendingMarkupBlock(dest)
        if xe.text and xe.text.strip():
            pending.append(xe.text)
        for s in xe:
            tail = s.tail
            s.tail = None
            if self.block_model.match(s):
                pending.close()
                self.block_model.parse(log, s, dest)
            elif self.inline_model.match(s):
                self.inline_model.parse(log, s, pending.append)
            else:
                log(fc.UnsupportedElement.issue(s))
            if tail and tail.strip():
                pending.append(tail)
        pending.close()
