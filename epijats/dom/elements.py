from __future__ import annotations

from dataclasses import dataclass

from ..tree import ParentInline


@dataclass
class IssueElement(ParentInline[str]):
    def __init__(self, msg: str):
        super().__init__('format-issue', msg)
