from .util import copytree_nostat
from .jinja import PackagePageGenerator


#std library
import os, tempfile
from datetime import datetime, date, time, timezone
from pathlib import Path
from pkg_resources import resource_filename


# WeasyPrint will inject absolute local file paths into a PDF file if the input HTML
# file has relative URLs in anchor hrefs.
# This hardcoded meaningless HACK_WEASY_PATH is to ensure these local file paths are
# meaningless and constant (across similar operating systems).
HACK_WEASY_PATH = Path(tempfile.gettempdir()) / "mZ3iBmnGae1f4Wcgt2QstZn9VYx"


class EprinterConfig:
    def __init__(self, theme_dir=None, dsi_base_url=None, math_css_url=None):
        self.urls = dict(
            dsi_base_url=(dsi_base_url.rstrip("/") if dsi_base_url else None),
            math_css_url=(math_css_url or "static/katex/katex.css"),
        )
        self.pandoc_opts = []
        if theme_dir:
            self.pandoc_opts = ["--data-dir", theme_dir, "--defaults", "pandoc.yaml"]
        self.article_style = 'lyon'
        self.embed_web_fonts = True
        self.show_pdf_icon = False


class Eprint:

    _gen = None
    _static_dir = Path(resource_filename(__name__, "static/"))

    def __init__(self, webstract, tmp, config=None):
        if config is None:
            config = EprinterConfig()
        self._tmp = Path(tmp)
        self._html_ctx = dict(config.urls)
        self._html_ctx["article_style"] = config.article_style
        self._html_ctx["embed_web_fonts"] = config.embed_web_fonts
        self._html_ctx["show_pdf_icon"] = config.show_pdf_icon
        self.webstract = webstract
        if Eprint._gen is None:
            Eprint._gen = PackagePageGenerator()

    def _get_html(self):
        html_dir = self._tmp
        os.makedirs(html_dir, exist_ok=True)
        ret = html_dir / "index.html"
        # for now just assume math is always needed
        ctx = dict(doc=self.webstract.facade, has_math=True, **self._html_ctx)
        self._gen.render_file("article.html.jinja", ret, ctx)
        if not ret.with_name("static").exists():
            os.symlink(Eprint._static_dir, ret.with_name("static"))
        if self.webstract.source.subpath_exists("pass"):
            self.webstract.source.symlink_subpath(html_dir / "pass", "pass")
        return ret

    def make_html_dir(self, target):
        copytree_nostat(self._get_html().parent, target)

    @staticmethod
    def copy_static_dir(target):
        copytree_nostat(Eprint._static_dir, target)

    @staticmethod
    def html_to_pdf(source, target):
        import weasyprint

        weasyprint.HTML(source).write_pdf(target)

    @staticmethod
    def stable_html_to_pdf(html_path, target, source_date):
        target = Path(target)
        os.environ.update(source_date)
        if os.environ.get("EPIJATS_SKIP_PDF"):
            return
        try:
            os.remove(HACK_WEASY_PATH)
        except FileNotFoundError:
            pass
        os.symlink(html_path.parent.resolve(), HACK_WEASY_PATH)
        Eprint.html_to_pdf(HACK_WEASY_PATH / html_path.name, target)
        os.remove(HACK_WEASY_PATH)
        return target

    def make_pdf(self, target):
        Eprint.stable_html_to_pdf(self._get_html(), target, self._source_date_epoch())

    def make_html_and_pdf(self, html_target, pdf_target):
        html_path = self._get_html()
        copytree_nostat(html_path.parent, html_target)
        Eprint.stable_html_to_pdf(html_path, pdf_target, self._source_date_epoch())

    def _source_date_epoch(self):
        ret = dict()
        if self.webstract.date is not None:
            assert isinstance(self.webstract.date, date)
            doc_date = datetime.combine(self.webstract.date, time(0), timezone.utc)
            source_mtime = doc_date.timestamp()
            if source_mtime:
                ret["SOURCE_DATE_EPOCH"] = "{:.0f}".format(source_mtime)
        return ret
