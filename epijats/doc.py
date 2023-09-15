from . import webstract

# standard library
import os
from pathlib import Path


class DocLoader:
    def __init__(self, cache, eprinter_config=None):
        self.cache = Path(cache)
        self.pandoc_opts = eprinter_config.pandoc_opts

    def webstract_from_edition(self, edition):
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

                ret = jats.webstract_from_jats(work_path, self.pandoc_opts)
            else:
                raise ValueError(f"Unknown digital object type at {edition.dsi}")

            edidata = dict(edid=str(edition.edid), base_dsi=str(edition.suc.dsi))
            latest_edid = edition.suc.latest(edition.unlisted).edid
            if latest_edid > edition.edid:
                edidata["newer_edid"] = str(latest_edid)
            ret['edition'] = edidata

            os.makedirs(cached.parent, exist_ok=True)
            ret.dump_xml(cached)

        return ret
