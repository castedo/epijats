from __future__ import annotations

from typing import TYPE_CHECKING, cast

from epijats.xml import ET

if TYPE_CHECKING:
    from epijats.xml import XmlElement


def ET_tostring_unicode(e: XmlElement) -> str:
    return cast(str, ET.tostring(e, encoding='unicode'))  # type: ignore[arg-type]
