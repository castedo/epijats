from typing import TypeAlias

import _typeshed


StrPath = _typeshed.StrPath  # (os.PathLike[str] | str)

JSONType: TypeAlias = (
    None | str | int | float | list['JSONType'] | dict[str, 'JSONType']
)
