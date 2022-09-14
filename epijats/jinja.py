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
    def __init__(self, edition):
        super().__init__(edition.jats())
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
        return str(self.edition.up.edid) if self.edition.up else None

    @property
    def flow_edition(self):
        flow = self.edition.flow_edition()
        return JatsEditionVars(flow) if flow else None

    @property
    def latest_edid(self):
        subid = self.edition.up.last_subid
        return self.edition.up.subs[subid].edid

    @property
    def ref_commit(self):
        return self.edition.suc.ref_commit

    @property
    def sign_key(self):
        fingerprint = self.edition.suc.sign_key_fingerprint
        return fingerprint.hex().upper()

    @property
    def all_editions(self):
        eds = self.edition.suc.root.all_subeditions()
        return [JatsEditionVars(e) for e in eds]
