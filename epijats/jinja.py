import jinja2


class WebPageGenerator:
    def __init__(self):
        self.env = jinja2.Environment(
            loader=jinja2.ChoiceLoader([]),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            extensions=["jinja2.ext.do"],
        )

    def add_template_loader(self, loader):
        self.env.loader.loaders.append(loader)

    def render_file(self, tmpl_subpath, dest_filepath, ctx=dict()):
        tmpl = self.env.get_template(str(tmpl_subpath))
        tmpl.stream(**ctx).dump(str(dest_filepath), "utf-8")


class PackagePageGenerator(WebPageGenerator):
    def __init__(self):
        super().__init__()
        self.add_template_loader(jinja2.PackageLoader(__name__, "templates"))


def style_template_loader():
    return jinja2.PrefixLoader(
        {"epijats": jinja2.PackageLoader(__name__, "templates/epijats")}
    )
