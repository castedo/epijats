"""Parsing of XML content."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

from .. import condition as fc
from . import kit
from .kit import (
    Binder,
    DestT,
    Log,
    MonoModel,
    Model,
    ParsedT,
    Parser,
)

if TYPE_CHECKING:
    from ..typeshed import XmlElement


def parse_array_content(
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


class ArrayContentSession:
    """Parsing session for array (non-mixed, data-oriented) XML content."""

    def __init__(self, log: Log):
        self.log = log
        self._parsers: list[Parser] = []

    def bind(self, binder: Binder[DestT], dest: DestT) -> None:
        self._parsers.append(binder.bound_parser(self.log, dest))

    def bind_mono(self, model: MonoModel[ParsedT], target: ParsedT) -> None:
        self._parsers.append(model.mono_parser(self.log, target))

    def bind_once(self, binder: Binder[DestT], dest: DestT) -> None:
        once = kit.OnlyOnceBinder(binder)
        self._parsers.append(once.bound_parser(self.log, dest))

    def one(self, model: Model[ParsedT]) -> kit.Outcome[ParsedT]:
        ret = kit.SinkDestination[ParsedT]()
        once = kit.OnlyOnceBinder(model)
        self._parsers.append(once.bound_parser(self.log, ret))
        return ret

    def every(self, model: Model[ParsedT]) -> Sequence[ParsedT]:
        ret: list[ParsedT] = list()
        parser = model.bound_parser(self.log, ret.append)
        self._parsers.append(parser)
        return ret

    def parse_content(self, e: XmlElement) -> None:
        parse_array_content(self.log, e, self._parsers)
