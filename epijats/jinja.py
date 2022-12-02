from .doc import DocLoader

import jinja2

# std lib
from pkg_resources import resource_filename


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
    def contributors(self):
        return self.jats.contributors

    @property
    def abstract(self):
        return self.jats.abstract_html

    @property
    def body(self):
        return self.jats.body_html

    @property
    def dsi(self):
        return self.jats.dsi

    @property
    def hexhash(self):
        return self.jats.git_hash

    @property
    def uri(self):
        return "swh:1:cnt:" + self.jats.git_hash


class DocEditionVars:
    def __init__(self, edition):
        self.edition = edition
        self.is_jats = DocLoader.is_jats(edition.dobj)

    @property
    def title(self):
        return self.edition.dobj.title_html

    @property
    def date(self):
        return self.edition.dobj.date

    @property
    def authors(self):
        if self.is_jats:
            return self.edition.dobj.authors
        return [self.edition.suc.author.name]

    @property
    def contributors(self):
        return self.edition.dobj.contributors

    @property
    def abstract(self):
        if self.is_jats:
            return self.edition.dobj.abstract_html
        return None

    @property
    def body(self):
        if self.is_jats:
            return self.edition.dobj.body_html
        return None

    @property
    def hexhash(self):
        if self.is_jats:
            return self.edition.dobj.git_hash
        return self.edition.hexsha

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
        return DocEditionVars(flow) if flow else None

    @property
    def latest_edid(self):
        latest = self.edition.suc.latest(self.edition.unlisted)
        return latest.edid if latest else None

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
        return [DocEditionVars(e) for e in eds]


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
