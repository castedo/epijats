from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from . import webstract

if TYPE_CHECKING:
    from hidos import Edition
    from .webstract import Webstract

class DocLoader:
    def __init__(self, cache: Path | str):
        self.cache = Path(cache)

    def webstract_from_edition(self, edition: Edition) -> Webstract:
        work_path = self.cache / "arc" / str(edition.dsi)
        cached = self.cache / "epijats" / str(edition.dsi) / "webstract.xml"
        if cached.exists():
            ret = webstract.Webstract.load_xml(cached)
            ret.source.path = work_path
        else:
            if not work_path.exists():
                edition.work_copy(work_path)
            if work_path.is_dir():
                from . import jats

                ret = jats.webstract_from_jats(work_path)
            else:
                raise ValueError(f"Unknown digital object type at {edition.dsi}")

            edidata = dict(edid=str(edition.edid), base_dsi=str(edition.suc.dsi))
            latest = edition.suc.latest(edition.unlisted)
            if latest and latest.edid > edition.edid:
                edidata["newer_edid"] = str(latest.edid)
            ret['edition'] = edidata
            if hasattr(edition, 'date'):  # date added in hidos 2.0
                ret['date'] = edition.date

            os.makedirs(cached.parent, exist_ok=True)
            ret.dump_xml(cached)

        return ret
