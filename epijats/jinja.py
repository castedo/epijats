from .doc import DocLoader

import jinja2


class DocEditionVars:
    def __init__(self, doc, edition=None):
        self.webface = doc.webstract.facade
        self.edition = edition
        self.is_jats = DocLoader.is_jats(doc)

    @property
    def title(self):
        return self.webface.title

    @property
    def date(self):
        return self.webface.date

    @property
    def authors(self):
        return self.webface.authors

    @property
    def contributors(self):
        return self.webface.contributors

    @property
    def abstract(self):
        return self.webface.abstract

    @property
    def body(self):
        return self.webface.body

    @property
    def hash_scheme(self):
        return self.webface.hash_scheme

    @property
    def hexhash(self):
        return self.webface.hexhash

    @property
    def obsolete(self):
        return self.edition.obsolete

    @property
    def base_dsi(self):
        return str(self.edition.suc.dsi)

    @property
    def dsi(self):
        return str(self.edition.dsi)

    @property
    def edid(self):
        return str(self.edition.edid)

    @property
    def seq_edid(self):
        return str(self.edition.up.edid) if self.edition.up else None

    @property
    def latest_edid(self):
        latest = self.edition.suc.latest(self.edition.unlisted)
        return latest.edid if latest else None


class SuccessionFacade:
    def __init__(self, succession):
        self.succession = succession

    @property
    def dsi(self):
        return self.succession.dsi

    @property
    def ref_commit(self):
        return self.succession.ref_commit.hexsha

    @property
    def sign_key(self):
        fingerprint = self.succession.sign_key_fingerprint
        return fingerprint.hex().upper()


class WebPageGenerator:
    def __init__(self):
        self.env = jinja2.Environment(
            loader=jinja2.PackageLoader(__name__, "templates"),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            extensions=["jinja2.ext.do"],
        )

    def render_file(self, tmpl_subpath, dest_filepath, ctx=dict()):
        tmpl = self.env.get_template(str(tmpl_subpath))
        tmpl.stream(**ctx).dump(str(dest_filepath), "utf-8")


def style_template_loader():
    return jinja2.PrefixLoader(
        {"epijats": jinja2.PackageLoader(__name__, "templates/epijats")}
    )
