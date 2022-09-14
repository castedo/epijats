import hidos
from epijats import JatsEprinter


class JatsEdition(hidos.Edition):
    def __init__(self, git_tree, succession, edid, up=None):
        super().__init__(git_tree, succession, edid, up)
        self._jats = None

    def flow_edition(self):
        if self.has_digital_object:
            return self
        for subid in reversed(sorted(self.subs.keys())):
            if subid > 0 or self.edid.unlisted:
                flow = self.subs[subid].flow_edition()
                if flow is not None:
                    return flow
        return None

    def jats(self):
        if self._jats is None and self.work_copy() is not None:
            self._jats = JatsEprinter(
                self.suc.arc.eprinter_config,
                self.work_copy() / "article.xml",
                self.suc.arc.cache / "jats" / self.suc.dsi / str(self.edid),
            )
        return self._jats


class JatsArchive(hidos.Archive):
    def __init__(self, git_repo_path, eprinter_config, cache_dir):
        super().__init__(git_repo_path, cache_dir)
        self.edition_class = JatsEdition
        self.eprinter_config = eprinter_config
