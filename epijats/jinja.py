import jinja2


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
