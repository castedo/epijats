
class JatsVars:

    def __init__(self, jats):
        self.jats = jats

    @property
    def title(self):
        return self.jats.title_html

    @property
    def date(self):
        return self.jats.date

    @property
    def authors(self):
        return self.jats.authors

    @property
    def abstract(self):
        return self.jats.abstract_html

    @property
    def body(self):
        return self.jats.body_html

    @property
    def hexhash(self):
        return self.jats.git_hash

    @property
    def uri(self):
        return "swh:1:cnt:" + self.jats.git_hash


class JatsEditionVars(JatsVars):
    def __init__(self, jats, edition):
        super().__init__(jats)
        self.edition = edition

    @property
    def obsolete(self):
        return self.edition.obsolete

    @property
    def dsi(self):
        return str(self.edition.suc.dsi)

    @property
    def edid(self):
        return str(self.edition.edid)

    @property
    def seq_edid(self):
        return str(self.edition.up.edid)

    @property
    def latest_edid(self):
        subid = self.edition.up.last_subid
        return self.edition.up.subs[subid].edid
