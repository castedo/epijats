from __future__ import annotations

from dataclasses import dataclass

from lxml import etree


class FormatCondition:
    def __str__(self) -> str:
        return self.__doc__ or object.__str__(self)


@dataclass
class FormatIssue:
    condition: FormatCondition
    sourceline: int | None = None

    def __str__(self) -> str:
        msg = str(self.condition)
        if self.sourceline:
            msg += f" (line {self.sourceline})"
        return msg


class Baseprint:
    def __init__(self, et: etree.ElementTree):
        self.issues: list[FormatIssue] = list()

        if bool(et.docinfo.doctype):
            self._issue(DoctypeDeclaration())
        if et.docinfo.encoding.lower() != "utf-8":
            self._issue(EncodingNotUtf8(et.docinfo.encoding))
        for pi in et.xpath("//processing-instruction()"):
            self._issue(ProcessingInstruction(pi.text), pi.sourceline)
            etree.strip_elements(et, pi.tag, with_tail=False)
        self._root(et.getroot())

    def _issue(self, condition: FormatCondition, sourceline: int | None = None) -> None:
        self.issues.append(FormatIssue(condition, sourceline))

    def _issue_element(self, e: etree.ElementBase) -> None:
        p = e.getparent()
        self._issue(UnsupportedElement(e.tag, p.tag if p else None), e.sourceline)

    def _root(self, e: etree.ElementBase) -> None:
        if e.tag != 'article':
            self._issue_element(e)
        for k, v in e.attrib.items():
            if k == '{http://www.w3.org/XML/1998/namespace}lang':
                if v != "en":
                    self._issue(UnsupportedAttributeValue(e.tag, k, v))
            else:
                self._issue(UnsupportedAttribute(e.tag, k))
        for s in e:
            assert isinstance(s, etree._Element)


@dataclass(frozen=True)
class DoctypeDeclaration(FormatCondition):
    """XML DOCTYPE declaration present"""


@dataclass(frozen=True)
class EncodingNotUtf8(FormatCondition):
    encoding: str | None


@dataclass(frozen=True)
class ProcessingInstruction(FormatCondition):
    """XML processing instruction"""

    text: str

    def __str__(self) -> str:
        return "{} {}".format(self.__doc__, repr(self.text))


@dataclass(frozen=True)
class UnsupportedElement(FormatCondition):
    """Unsupported XML element"""

    tag: str
    parent: str | None

    def __str__(self) -> str:
        assert self.__doc__
        msg = self.__doc__ + f" '{self.tag}'"
        if self.parent:
            msg += f" under '{self.parent}'"
        return msg


@dataclass(frozen=True)
class UnsupportedAttribute(FormatCondition):
    """Unsupported XML attribute"""

    tag: str
    attribute: str

    def __str__(self) -> str:
        return f"{self.__doc__} '{self.attribute}' of element '{self.tag}'"


@dataclass(frozen=True)
class UnsupportedAttributeValue(FormatCondition):
    """Unsupported XML attribute value"""

    tag: str
    attribute: str
    value: str

    def __str__(self) -> str:
        msg = "{} {} for '{}' of element '{}'"
        return msg.format(self.__doc__, repr(self.value), self.attribute, self.tag)
