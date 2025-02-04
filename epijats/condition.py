from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from lxml import etree
from lxml.etree import QName

if TYPE_CHECKING:
    JSONType: TypeAlias = None | str | int | float | list['JSONType'] | dict[str, 'JSONType']


@dataclass(frozen=True)
class FormatCondition:
    def __str__(self) -> str:
        return self.__doc__ or type(self).__name__

    def as_pod(self) -> JSONType:
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

    def as_pod(self) -> dict[str, JSONType]:
        ret: dict[str, JSONType] = {}
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
    def issue(e: etree._Element) -> FormatIssue:
        return FormatIssue(ProcessingInstruction(e.text), e.sourceline)


@dataclass(frozen=True)
class ElementFormatCondition(FormatCondition):
    tag: str | bytes | bytearray | QName
    parent: str | bytes | bytearray | QName | None

    def __str__(self) -> str:
        parent = "" if self.parent is None else repr(self.parent)
        return "{} {}/{!r}".format(self.__doc__, parent, self.tag)

    @classmethod
    def issue(klas, e: etree._Element, info: str | None = None) -> FormatIssue:
        parent = e.getparent()
        ptag = None if parent is None else parent.tag
        return FormatIssue(klas(e.tag, ptag), e.sourceline, info)

    def as_pod(self) -> JSONType:
        return [type(self).__name__, str(self.tag), str(self.parent)]


@dataclass(frozen=True)
class UnsupportedElement(ElementFormatCondition):
    """Unsupported XML element"""


@dataclass(frozen=True)
class ExcessElement(ElementFormatCondition):
    """Excess XML element"""


@dataclass(frozen=True)
class MissingContent(ElementFormatCondition):
    """Missing XML element content"""


@dataclass(frozen=True)
class IgnoredText(ElementFormatCondition):
    """Unexpected text ignored within XML element"""


class InvalidOrcid(ElementFormatCondition):
    """Invalid ORCID"""


class InvalidInteger(ElementFormatCondition):
    """Invalid integer"""


class MissingName(FormatCondition):
    """Missing name"""


@dataclass(frozen=True)
class UnsupportedAttribute(FormatCondition):
    """Unsupported XML attribute"""

    tag: str | bytes | bytearray | QName
    attribute: str

    def __str__(self) -> str:
        return f"{self.__doc__} {self.tag!r}@{self.attribute!r}"

    @staticmethod
    def issue(e: etree._Element, key: str) -> FormatIssue:
        return FormatIssue(UnsupportedAttribute(e.tag, key), e.sourceline)

    def as_pod(self) -> JSONType:
        return [type(self).__name__, str(self.tag), str(self.attribute)]


@dataclass(frozen=True)
class UnsupportedAttributeValue(FormatCondition):
    """Unsupported XML attribute value"""

    tag: str | bytes | bytearray | QName
    attribute: str
    value: str

    def __str__(self) -> str:
        msg = "{} {!r}@{!r} = {!r}"
        return msg.format(self.__doc__, self.tag, self.attribute, self.value)

    @staticmethod
    def issue(e: etree._Element, key: str, value: str) -> FormatIssue:
        return FormatIssue(UnsupportedAttributeValue(e.tag, key, value), e.sourceline)


@dataclass(frozen=True)
class MissingElement(FormatCondition):
    """Missing XML element"""

    tag: str
    parent: str

    def __str__(self) -> str:
        return "{} {!r}/{!r}".format(self.__doc__, self.parent, self.tag)


@dataclass(frozen=True)
class MissingAttribute(FormatCondition):
    """Missing XML attribute"""

    tag: str | bytes | bytearray | QName
    attribute: str

    def __str__(self) -> str:
        return f"{self.__doc__} {self.tag!r}@{self.attribute!r}"

    @staticmethod
    def issue(e: etree._Element, key: str) -> FormatIssue:
        return FormatIssue(MissingAttribute(e.tag, key), e.sourceline)
