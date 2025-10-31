"""Parsing of XML content."""

from __future__ import annotations

from typing import Generic, Protocol, TYPE_CHECKING, TypeAlias

from .. import condition as fc
from ..elements import ElementT
from ..tree import (
    AppendCovT,
    Element,
    MarkupBlock,
    MixedParent,
)
from . import kit
from .kit import (
    DestT,
    Log,
    Model,
    ParsedT,
    Parser,
    Sink,
)

if TYPE_CHECKING:
    from ..typeshed import XmlContent, XmlElement

Inline: TypeAlias = Element


class BoundParser:
    """Same interface as Parser but log and destination are pre-bound."""

    def __init__(self, parser: Parser[DestT], dest: DestT):
        self.parser = parser
        self.dest = dest

    def try_parse(self, log: Log, xe: XmlElement) -> bool:
        match = self.parser.match(xe)
        if match:
            self.parser.parse(log, xe, self.dest)
            # return of parse(...) intentionally ignored
            # try_parse returns true just for a parser matching
        return match


class OnlyOnceParser(BoundParser):
    def __init__(self, parser: Parser[DestT], dest: DestT):
        super().__init__(parser, dest)
        self._parse_done = False

    def try_parse(self, log: Log, xe: XmlElement) -> bool:
        match = self.parser.match(xe)
        if match:
            if not self._parse_done:
                self._parse_done = self.parser.parse(log, xe, self.dest)
            else:
                log(fc.ExcessElement.issue(xe))
        return match


class ArrayContentSession:
    """Parsing session for array (non-mixed, data-oriented) XML content."""

    def __init__(self) -> None:
        self._parsers: list[BoundParser] = []

    def bind(self, parser: Parser[DestT], dest: DestT) -> None:
        self._parsers.append(BoundParser(parser, dest))

    def bind_once(self, parser: Parser[DestT], dest: DestT) -> None:
        self._parsers.append(OnlyOnceParser(parser, dest))

    def one(self, model: Model[ParsedT]) -> kit.Outcome[ParsedT]:
        ret = kit.SinkDestination[ParsedT]()
        self.bind_once(model, ret)
        return ret

    def parse_content(self, log: Log, xc: XmlContent) -> None:
        if xc.text and xc.text.strip():
            log(fc.IgnoredText.issue(xc))
        for s in xc:
            tail = s.tail
            s.tail = None
            if not any(p.try_parse(log, s) for p in self._parsers):
                log(fc.UnsupportedElement.issue(s))
            if tail and tail.strip():
                log(fc.IgnoredTail.issue(s))


class ContentModel(Protocol, Generic[AppendCovT]):
    def parse_content(
        self, log: Log, xc: XmlContent, dest: Sink[AppendCovT]
    ) -> None: ...


class MixedModel(Model[str | Inline], ContentModel[str | Inline]):
    def parse_content(self, log: Log, xc: XmlContent, dest: Sink[str | Inline]) -> None:
        if xc.text:
            dest(xc.text)
        for s in xc:
            if self.match(s):
                self.parse(log, s, dest)
            else:
                log(fc.UnsupportedElement.issue(s))
                self.parse_content(log, s, dest)
            if s.tail:
                dest(s.tail)

    def __or__(self, model: Model[str | Inline] | Model[Inline]) -> MixedModel:
        ret = UnionMixedModel()
        ret |= self
        ret |= model
        return ret


class UnionMixedModel(MixedModel):
    def __init__(self) -> None:
        self._models = kit.UnionModel[str | Inline]()

    def match(self, xe: XmlElement) -> bool:
        return self._models.match(xe)

    def parse(self, log: Log, xe: XmlElement, sink: Sink[str | Inline]) -> bool:
        return self._models.parse(log, xe, sink)

    def __ior__(self, model: Model[str | Inline] | Model[Inline]) -> UnionMixedModel:
        self._models |= model
        return self


ArrayContentModel: TypeAlias = ContentModel[Element]


class DataContentModel(ContentModel[ElementT]):
    def __init__(self, child_model: Model[ElementT]):
        self.child_model = child_model

    def parse_content(self, log: Log, xc: XmlElement, out: Sink[ElementT]) -> None:
        sess = ArrayContentSession()
        sess.bind(self.child_model, out)
        sess.parse_content(log, xc)


class PendingMarkupBlock:
    def __init__(self, dest: Sink[Element], init: MixedParent | None = None):
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


class RollContentModel(ArrayContentModel):
    def __init__(self, block_model: Model[Element], inline_model: MixedModel):
        self.block_model = block_model
        self.inline_model = inline_model

    def parse_content(self, log: Log, xe: XmlElement, sink: Sink[Element]) -> None:
        pending = PendingMarkupBlock(sink)
        if xe.text and xe.text.strip():
            pending.append(xe.text)
        for s in xe:
            tail = s.tail
            s.tail = None
            if self.block_model.match(s):
                pending.close()
                self.block_model.parse(log, s, sink)
            elif self.inline_model.match(s):
                self.inline_model.parse(log, s, pending.append)
            else:
                log(fc.UnsupportedElement.issue(s))
            if tail and tail.strip():
                pending.append(tail)
        pending.close()
