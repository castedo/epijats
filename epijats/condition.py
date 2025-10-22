from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from .typeshed import JsonData
    from .typeshed import XmlElement
    import xml.etree.ElementTree, lxml.etree

    QName: TypeAlias = xml.etree.ElementTree.QName | lxml.etree.QName


@dataclass(frozen=True)
class FormatCondition:
    def __str__(self) -> str:
        return self.__doc__ or type(self).__name__

    def as_pod(self) -> JsonData:
        return type(self).__name__


@dataclass(frozen=True)
class FormatIssue:
    condition: FormatCondition
    sourceline: int | None = None
    info: str | None = None

    def __str__(self) -> str:
        msg = str(self.condition)
        if self.sourceline:
            msg += f" (line {self.sourceline})"
        if self.info:
            msg += f": {self.info}"
        return msg

    def as_pod(self) -> dict[str, JsonData]:
        ret: dict[str, JsonData] = {}
        ret['condition'] = self.condition.as_pod()
        if self.sourceline is not None:
            ret['sourceline'] = self.sourceline
        if self.info:
            ret['info'] = self.info
        return ret


class XMLSyntaxError(FormatCondition):
    """XML syntax error"""


class DoctypeDeclaration(FormatCondition):
    """XML DOCTYPE declaration"""


@dataclass(frozen=True)
class EncodingNotUtf8(FormatCondition):
    encoding: str | None


@dataclass(frozen=True)
class ProcessingInstruction(FormatCondition):
    """XML processing instruction"""

    text: str | None

    def __str__(self) -> str:
        return "{} {}".format(self.__doc__, repr(self.text))

    @staticmethod
    def issue(e: XmlElement) -> FormatIssue:
        sourceline = getattr(e, 'sourceline', None)
        return FormatIssue(ProcessingInstruction(e.text), sourceline)


@dataclass(frozen=True)
class ElementFormatCondition(FormatCondition):
    tag: str | bytes | bytearray | QName
    parent: str | bytes | bytearray | QName | None

    def __str__(self) -> str:
        parent = "" if self.parent is None else repr(self.parent)
        return "{} {}/{!r}".format(self.__doc__, parent, self.tag)

    @classmethod
    def issue(klas, e: XmlElement, info: str | None = None) -> FormatIssue:
        getparent = getattr(e, 'getparent', None)
        parent = getparent() if getparent else None
        ptag = None if parent is None else parent.tag
        sourceline = getattr(e, 'sourceline', None)
        return FormatIssue(klas(e.tag, ptag), sourceline, info)

    def as_pod(self) -> JsonData:
        parent = str(self.parent) if self.parent else None
        return [type(self).__name__, str(self.tag), parent]


@dataclass(frozen=True)
class UnsupportedElement(ElementFormatCondition):
    """Unsupported XML element"""


@dataclass(frozen=True)
class ExcessElement(ElementFormatCondition):
    """Excess XML element"""


@dataclass(frozen=True)
class BlockElementInPhrasingContent(ElementFormatCondition):
    """Block-level element in phrasing content"""


@dataclass(frozen=True)
class MissingContent(ElementFormatCondition):
    """Missing XML element content"""


@dataclass(frozen=True)
class IgnoredText(ElementFormatCondition):
    """Unexpected text ignored within XML element"""


@dataclass(frozen=True)
class IgnoredTail(ElementFormatCondition):
    """Unexpected text ignored after XML element"""


class InvalidOrcid(ElementFormatCondition):
    """Invalid ORCID"""


class InvalidDoi(ElementFormatCondition):
    """Invalid DOI"""


class InvalidPmid(ElementFormatCondition):
    """Invalid PMID"""


class InvalidInteger(ElementFormatCondition):
    """Invalid integer"""


class InvalidCitation(ElementFormatCondition):
    """Invalid citation"""


class MissingSectionHeading(ElementFormatCondition):
    """Missing section heading"""


@dataclass(frozen=True)
class MissingChild(FormatCondition):
    """Missing child element"""

    tag: str | bytes | bytearray | QName
    parent: str | bytes | bytearray | QName | None
    child: str | bytes | bytearray | QName

    def __str__(self) -> str:
        parent = "" if self.parent is None else repr(self.parent)
        return "{} {}/{!r}/{!r}".format(self.__doc__, parent, self.tag, self.child)

    @classmethod
    def issue(klas, e: XmlElement, child: str, info: str | None = None) -> FormatIssue:
        getparent = getattr(e, 'getparent', None)
        parent = getparent() if getparent else None
        ptag = None if parent is None else parent.tag
        sourceline = getattr(e, 'sourceline', None)
        return FormatIssue(klas(e.tag, ptag, child), sourceline, info)

    def as_pod(self) -> JsonData:
        parent = str(self.parent) if self.parent else None
        return [type(self).__name__, str(self.child), str(self.tag), parent]


@dataclass(frozen=True)
class UnsupportedAttribute(FormatCondition):
    """Unsupported XML attribute"""

    tag: str | bytes | bytearray | QName
    attribute: str

    def __str__(self) -> str:
        return f"{self.__doc__} {self.tag!r}@{self.attribute!r}"

    @staticmethod
    def issue(e: XmlElement, key: str) -> FormatIssue:
        sourceline = getattr(e, 'sourceline', None)
        return FormatIssue(UnsupportedAttribute(e.tag, key), sourceline)

    def as_pod(self) -> JsonData:
        return [type(self).__name__, str(self.tag), self.attribute]


@dataclass(frozen=True)
class AttributeValueCondition(FormatCondition):
    tag: str | bytes | bytearray | QName
    attribute: str
    value: str | None

    def __str__(self) -> str:
        msg = "{} {!r}@{!r} = {!r}"
        return msg.format(self.__doc__, self.tag, self.attribute, self.value)

    @staticmethod
    def issue(e: XmlElement, key: str, value: str | None) -> FormatIssue:
        sourceline = getattr(e, 'sourceline', None)
        return FormatIssue(UnsupportedAttributeValue(e.tag, key, value), sourceline)

    def as_pod(self) -> JsonData:
        return [type(self).__name__, str(self.tag), self.attribute, self.value]


@dataclass(frozen=True)
class UnsupportedAttributeValue(AttributeValueCondition):
    """Unsupported XML attribute value"""


@dataclass(frozen=True)
class InvalidAttributeValue(AttributeValueCondition):
    """Invalid XML attribute value"""


@dataclass(frozen=True)
class MissingElement(ElementFormatCondition):
    """Missing XML element"""


@dataclass(frozen=True)
class MissingAttribute(FormatCondition):
    """Missing XML attribute"""

    tag: str | bytes | bytearray | QName
    attribute: str

    def __str__(self) -> str:
        return f"{self.__doc__} {self.tag!r}@{self.attribute!r}"

    @staticmethod
    def issue(e: XmlElement, key: str) -> FormatIssue:
        sourceline = getattr(e, 'sourceline', None)
        return FormatIssue(MissingAttribute(e.tag, key), sourceline)
