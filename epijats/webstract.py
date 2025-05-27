from __future__ import annotations

import datetime, json, os, shutil, tempfile
from pathlib import Path
from datetime import date
from typing import TYPE_CHECKING, Any, Callable
from warnings import warn

from hidos import Edition, EditionId

from .util import copytree_nostat, swhid_from_files

if TYPE_CHECKING:
    from .typeshed import StrPath


SWHID_SCHEME_LENGTH = len("swh:1:abc:")


class _Source:
    def __init__(self, *, swhid: str | None = None, path: Path | None = None):
        if swhid is None and path is None:
            raise ValueError("SWHID or path must be specified")
        if swhid is None:
            assert path is not None
            swhid = swhid_from_files(path)
        if not swhid.startswith("swh:1:"):
            raise ValueError("Source not identified by SWHID v1")
        self.swhid = swhid
        self.path = None if path is None else Path(path)

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


class Source(_Source):
    def __init__(self, *, swhid: str | None = None, path: Path | None = None):
        super().__init__(swhid=swhid, path=path)
        warn("Stop using webstract.Source", DeprecationWarning)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Source):
            return self.swhid == other.swhid
        return False


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
        self._source: _Source | None = None

    @staticmethod
    def from_edition(ed: Edition, cache_subdir: StrPath) -> Webstract:
        cache_subdir = Path(cache_subdir)
        cached = cache_subdir / "webstract.json"
        snapshot = cache_subdir / "snapshot"
        if cached.exists():
            ret = Webstract.load_json(cached)
            ret.set_source_from_path(snapshot)
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
            ret['date'] = str(ed.date)
            ret.dump_json(cached)
        return ret

    @property
    def facade(self) -> WebstractFacade:
        return self._facade

    @property
    def source(self) -> _Source:
        if not isinstance(self._source, _Source):
            raise ValueError("Webstract source missing.")
        return self._source

    @property
    def date(self) -> date | None:
        s = self.get("date")
        return date.fromisoformat(s) if s else None

    @property
    def archive_date(self) -> datetime.date | None:
        s = self.get("archive_date")
        return date.fromisoformat(s) if s else None

    def __setitem__(self, key: str, value: Any) -> None:
        if key not in self.KEYS:
            raise KeyError(f"Invalid Webstract key: {key}")
        if value is None:
            warn(f"Skip set of None for webstract key '{key}'", RuntimeWarning)
            return
        elif key == "source":
            if isinstance(value, Path):
                warn("call set_source_from_path", DeprecationWarning)
                self._source = _Source(path=value)
            elif isinstance(value, _Source):
                warn("stop assigning Source", DeprecationWarning)
                self._source = value
                value = self._source.swhid
            else:
                self._source = _Source(swhid=value)
                assert value == self._source.swhid
        elif key in ["date", "archive_date"]:
            if not isinstance(value, (str, type(None))):
              warn("Assign dates as ISO strings", DeprecationWarning)
              value = str(value)
        super().__setitem__(key, value)

    def set_source_from_path(self, src: StrPath) -> None:
        self._source = _Source(path=Path(src))
        super().__setitem__('source', self._source.swhid)

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
        return self._webstract.source.hash_scheme

    @property
    def hexhash(self):
        return self._webstract.source.hexhash

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


def webstract_pod_from_edition(ed: Edition) -> dict[str, Any]:
    os.environ["EPIJATS_NO_PANDOC"] = "1"
    with tempfile.TemporaryDirectory() as tempdir:
      return dict(Webstract.from_edition(ed, tempdir))
