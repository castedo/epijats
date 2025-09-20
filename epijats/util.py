from __future__ import annotations

import os, shutil
from pathlib import Path
from typing import TYPE_CHECKING
from warnings import warn
if TYPE_CHECKING:
    from .typeshed import StrPath

from hidos import swhid_from_path


def up_to_date(target: Path, source: Path) -> bool:
    last_update = os.path.getmtime(target) if target.exists() else 0
    return last_update > os.path.getmtime(source)


def copytree_nostat(src: StrPath, dst: StrPath) -> Path:
    """like shutil but avoids calling copystat so SELinux context is not copied"""

    os.makedirs(dst, exist_ok=True)
    for srcentry in os.scandir(src):
        dstentry = os.path.join(dst, srcentry.name)
        if srcentry.is_dir():
            copytree_nostat(srcentry, dstentry)
        else:
            shutil.copy(srcentry, dstentry)
    return Path(dst)


def swhid_from_files(path: StrPath) -> str:
    warn("Call hidos.swhid_from_path", DeprecationWarning)
    return swhid_from_path(path)
