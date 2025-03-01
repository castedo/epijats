from __future__ import annotations

import json, os, shutil
from pathlib import Path
from datetime import date
from typing import Any, Callable
from warnings import warn

from hidos import Edition, EditionId

from .util import copytree_nostat, swhid_from_files


SWHID_SCHEME_LENGTH = len("shw:1:abc:")


class Source:
    def __init__(self, *, swhid: str | None = None, path: Path | None = None):
        self._swhid = swhid
        self.path = None if path is None else Path(path)
        if self._swhid is None and self.path is None:
            raise ValueError("SWHID or path must be specified")

    @property
    def swhid(self) -> str:
        if self._swhid is None:
            assert self.path is not None
            self._swhid = swhid_from_files(self.path)
            if not self._swhid.startswith("swh:1:"):
                raise ValueError("Source not identified by SWHID v1")
        return self._swhid

    @property
    def hash_scheme(self) -> str:
        return self.swhid[:SWHID_SCHEME_LENGTH]

    @property
    def hexhash(self) -> str:
        return self.swhid[SWHID_SCHEME_LENGTH:]

    def __str__(self) -> str:
        return self.swhid

    def __repr__(self) -> str:
        return str(dict(swhid=self._swhid, path=self.path))

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Source):
            return self.swhid == other.swhid
        return False

    def copy_resources(self, dest: Path) -> None:
        os.makedirs(dest, exist_ok=True)
        for srcentry in os.scandir(self.path):
            dstentry = os.path.join(dest, srcentry.name)
            if srcentry.name == "static":
                msg = "A source directory entry named 'static' is not supported"
                raise NotImplementedError(msg)
            elif srcentry.is_dir():
                copytree_nostat(srcentry, dstentry)
            elif srcentry.name != "article.xml":
                shutil.copy(srcentry, dstentry)


class Webstract(dict[str, Any]):
    KEYS = [
        "abstract",
        "archive_date",
        "body",
        "cc_license_type",
        "contributors",
        "copyright",
        "date",
        "edition",
        "issues",
        "license_p",
        "license_ref",
        "source",
        "title",
    ]

    def __init__(self, init: dict[str, Any] | None = None):
        super().__init__()
        self["contributors"] = list()
        if init is None:
            init = dict()
        for key, value in init.items():
            self[key] = value
        self._facade = WebstractFacade(self)

    @staticmethod
    def from_edition(ed: Edition, cache_subdir: Path) -> Webstract:
        cache_subdir = Path(cache_subdir)
        cached = cache_subdir / "webstract.json"
        snapshot = cache_subdir / "snapshot"
        if cached.exists():
            ret = Webstract.load_json(cached)
            ret.source.path = snapshot
        else:
            from . import jats

            if not ed.snapshot:
                raise ValueError(f"Edition {ed} is not a snapshot edition")
            ed.snapshot.copy(snapshot)
            ret = jats.webstract_from_jats(snapshot)
            edidata = dict(edid=str(ed.edid), base_dsi=str(ed.suc.dsi))
            latest = ed.suc.latest(ed.unlisted)
            if latest and latest.edid > ed.edid:
                edidata["newer_edid"] = str(latest.edid)
            ret['edition'] = edidata
            ret['date'] = ed.date
            ret.dump_json(cached)
        return ret

    @property
    def facade(self) -> WebstractFacade:
        return self._facade

    @property
    def source(self) -> Source:
        ret = self.get("source")
        if not isinstance(ret, Source):
            raise ValueError("Webstract source missing.")
        return ret

    @property
    def date(self) -> date | None:
        ret = self.get("date")
        assert isinstance(ret, (date, type(None)))
        return ret

    def __setitem__(self, key: str, value: Any) -> None:
        if key not in self.KEYS:
            raise KeyError(f"Invalid Webstract key: {key}")
        if value is None:
            warn(f"Skip set of None for webstract key '{key}'", RuntimeWarning)
            return
        elif key == "source":
            if isinstance(value, Path):
                value = Source(path=value)
            elif not isinstance(value, Source):
                value = Source(swhid=value)
        elif key == "date" and not isinstance(value, date):
            value = date.fromisoformat(value)
        elif key == "archive_date" and not isinstance(value, date):
            value = date.fromisoformat(value)
        super().__setitem__(key, value)

    def dump_json(self, path: Path | str) -> None:
        """Write JSON to path."""

        with open(path, "w") as file:
            json.dump(
                self,
                file,
                indent=4,
                default=str,
                ensure_ascii=False,
                sort_keys=True,
            )
            file.write("\n")

    @staticmethod
    def load_json(path: Path | str) -> Webstract:
        with open(path) as f:
            return Webstract(json.load(f))


def add_webstract_key_properties(cls: type) -> type:
    def make_getter(key: str) -> Callable[[Any], Any]:
        return lambda self: self._webstract.get(key)

    for key in Webstract.KEYS:
        setattr(cls, key, property(make_getter(key)))
    return cls


# mypy: disable-error-code="no-untyped-def, attr-defined"

@add_webstract_key_properties
class WebstractFacade:
    def __init__(self, webstract: Webstract):
        self._webstract = webstract

    @property
    def _edidata(self):
        return self._webstract.get('edition', dict())

    @property
    def authors(self):
        ret = []
        for c in self.contributors:
            ret.append(c["given-names"] + " " + c["surname"])
        return ret

    @property
    def hash_scheme(self):
        return self.source.hash_scheme

    @property
    def hexhash(self):
        return self.source.hexhash

    @property
    def obsolete(self) -> bool:
        return "newer_edid" in self._edidata

    @property
    def base_dsi(self):
        return self._edidata.get("base_dsi")

    @property
    def dsi(self) -> str | None:
        return (self.base_dsi + "/" + self.edid) if self._edidata else None

    @property
    def edid(self):
        return self._edidata.get("edid")

    @property
    def _edition_id(self) -> EditionId | None:
        edid = self._edidata.get("edid")
        return EditionId(edid) if edid else None

    @property
    def seq_edid(self) -> str | None:
        edid = self._edition_id
        if not edid:
            return None
        nums = list(edid)
        return str(EditionId(nums[:-1]))

    @property
    def listed(self):
        edid = self._edition_id
        return edid and edid.listed

    @property
    def unlisted(self):
        edid = self._edition_id
        return edid and edid.unlisted

    @property
    def latest_edid(self):
        if self.obsolete:
            return self._edidata.get("newer_edid")
        else:
            return self.edid
