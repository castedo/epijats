from .util import swhid_from_files

import copy, json, os
from pathlib import Path
from datetime import date
from warnings import warn


SWHID_SCHEME_LENGTH = len("shw:1:abc:")


class Source:
    def __init__(self, swhid=None, path=None):
        self._swhid = swhid
        self.path = None if path is None else Path(path)
        if self._swhid is None and self.path is None:
            raise ValueError("SWHID or path must be specified")

    @property
    def swhid(self):
        if self._swhid is None:
            self._swhid = swhid_from_files(self.path)
            if not self._swhid.startswith("swh:1:"):
                raise ValueError("Source not identified by SWHID v1")
        return self._swhid

    @property
    def hash_scheme(self):
        return self.swhid[:SWHID_SCHEME_LENGTH]

    @property
    def hexhash(self):
        return self.swhid[SWHID_SCHEME_LENGTH:]

    def __str__(self):
        return self.swhid

    def __repr__(self):
        return str(dict(swhid=self._swhid, path=self.path))

    def __eq__(self, other):
        if isinstance(other, Source):
            return self.swhid == other.swhid
        return False

    def subpath_exists(self, subpath="."):
        return self.path is not None and (self.path / subpath).exists()

    def symlink_subpath(self, symlink, subpath="."):
        if self.path is None:
            raise ValueError(f"Path unknown for: {self._swhid}")
        srcpath = self.path / subpath
        if not srcpath.exists():
            raise ValueError(f"Path not found: {srcpath}")
        if symlink.exists():
            os.unlink(symlink)
        os.symlink(srcpath.resolve(), symlink)


class Webstract(dict):
    KEYS = ["abstract", "body", "contributors", "date", "source", "title"]

    def __init__(self, init=None):
        super().__init__()
        self['contributors'] = list()
        if init is None:
            init = dict()
        for key, value in init.items():
            self[key] = value
        self._facade = WebstractFacade(self)

    @property
    def facade(self):
        return self._facade

    @property
    def source(self):
        return self["source"]

    @property
    def date(self):
        return self["date"]

    def __setitem__(self, key, value):
        if key not in self.KEYS:
            raise KeyError(f"Invalid Webstract key: {key}")
        if value is None:
            warn(f"Skip set of None for webstract key '{key}'", RuntimeWarning)
            return
        elif key == "source":
            if isinstance(value, Path):
                value = Source(path=value)
            elif not isinstance(value, Source):
                value = Source(value)
        elif key == "date" and not isinstance(value, date):
            value = date.fromisoformat(value)
        super().__setitem__(key, value)

    def dump_json(self, path):
        """Write JSON to path."""

        with open(path, "w") as file:
            json.dump(
                self,
                file,
                indent=4,
                default=str,
                ensure_ascii=False,
                sort_keys = True,
            )
            file.write("\n")

    @staticmethod
    def load_json(path):
        with open(path) as f:
            return Webstract(json.load(f))

    def dump_xml(self, path):
        """Write XML to path."""

        with open(path, "w") as file:
            import jsoml

            jsoml.dump(self, file)
            file.write("\n")

    @staticmethod
    def load_xml(path):
        import jsoml

        return Webstract(jsoml.load(path))

def add_webstract_key_properties(cls):
    def make_getter(key):
        return lambda self: self._webstract.get(key)

    for key in Webstract.KEYS:
        setattr(cls, key, property(make_getter(key)))
    return cls


@add_webstract_key_properties
class WebstractFacade:
    def __init__(self, webstract):
        self._webstract = webstract

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
