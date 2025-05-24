from __future__ import annotations

import os, shutil
from pathlib import Path
from typing import TYPE_CHECKING
from warnings import warn
if TYPE_CHECKING:
    from .typeshed import StrPath

import dulwich.objects


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


def warn_git_baseprint_diffs(entry: os.DirEntry[str]) -> None:
    if entry.name.startswith("."):
        warn(f"Hidden files are ignored: {entry.name}")
    stat = entry.stat(follow_symlinks=False)
    if stat.st_mode & 0o111:
        warn(f"Excecution bits are ignored for file {entry.name}")


def _calc_file_sha1_hex(path: Path) -> str:
    with open(path, 'rb') as f:
        blob = dulwich.objects.Blob()
        blob.data = f.read()
        ret = blob.sha().hexdigest()
        assert isinstance(ret, str)
        return ret


def _calc_dir_sha1_hex(path: Path) -> str:
    tree = dulwich.objects.Tree()
    for entry in os.scandir(path):
        warn_git_baseprint_diffs(entry)
        if not entry.name.startswith("."):
            if entry.is_file():
                mode = 0o100644
                sha = _calc_file_sha1_hex(path / entry.name).encode('ascii')
            elif entry.is_dir():
                mode = 0o040000
                sha = _calc_dir_sha1_hex(path / entry.name).encode('ascii')
            else:
                raise ValueError
            tree.add(entry.name.encode(), mode, sha)
    ret = tree.sha().hexdigest()
    assert isinstance(ret, str)
    return ret


def swhid_from_files(path: StrPath) -> str:
    path = Path(path)
    if path.is_file():
        return "swh:1:cnt:" + _calc_file_sha1_hex(path)
    if path.is_dir():
        return "swh:1:dir:" + _calc_dir_sha1_hex(path)
    msg = "Only regular files and folders supported for Baseprint snapshots."
    raise ValueError(msg)
