import os, shutil, tempfile
from datetime import datetime, date, time, timezone
from importlib import resources
from pathlib import Path
from typing import Any, Never
from warnings import warn

from .jats import webstract_from_jats
from .util import copytree_nostat
from .webstract import Webstract


# WeasyPrint will inject absolute local file paths into a PDF file if the input HTML
# file has relative URLs in anchor hrefs.
# This hardcoded meaningless HACK_WEASY_PATH is to ensure these local file paths are
# meaningless and constant (across similar operating systems).
HACK_WEASY_PATH = Path(tempfile.gettempdir()) / "mZ3iBmnGae1f4Wcgt2QstZn9VYx"


class EprinterConfig:
    def __init__(
        self,
        *,
        dsi_domain: str | None = None,
        math_css_url: str | None = None,
    ):
        self.math_css_url = math_css_url
        self.dsi_domain = dsi_domain
        self.embed_web_fonts = True
        self.show_pdf_icon = False
        self.header_banner_msg: str | None = None


class Eprint:
    _gen: Any = None

    def __init__(
        self, webstract: Webstract, tmp: Path, config: EprinterConfig | None = None
    ):
        from .jinja import PackagePageGenerator

        if config is None:
            config = EprinterConfig()
        self._add_pdf = config.show_pdf_icon
        self._tmp = Path(tmp)
        self._html_ctx: dict[str, str | bool | None] = dict()
        for key in [
            'math_css_url',
            'dsi_domain',
            'embed_web_fonts',
            'show_pdf_icon',
            'header_banner_msg',
        ]:
            self._html_ctx[key] = getattr(config, key, None)
        self.webstract = webstract
        if Eprint._gen is None:
            Eprint._gen = PackagePageGenerator()

    def make_html_dir(self, target: Path) -> Path:
        os.makedirs(target, exist_ok=True)
        ret = target / "index.html"
        ctx = dict(doc=self.webstract.facade, **self._html_ctx)
        assert self._gen
        self._gen.render_file("article.html.jinja", ret, ctx)
        self._gen.render_file("issues.html.jinja", target / "issues.html", ctx)
        Eprint._clone_static_dir(target / "static")
        self.webstract.source.copy_resources(target)
        return ret

    @staticmethod
    def _clone_static_dir(target: Path) -> None:
        shutil.rmtree(target, ignore_errors=True)
        Eprint.copy_static_dir(target)

    @staticmethod
    def copy_static_dir(target: Path) -> None:
        quasidir = resources.files(__package__).joinpath("static")
        with resources.as_file(quasidir) as tmp_path:
            copytree_nostat(tmp_path, target)

    @staticmethod
    def html_to_pdf(source: Path, target: Path) -> None:
        import weasyprint

        options = {'presentational_hints': True, 'full_fonts': True}
        weasyprint.HTML(source).write_pdf(target, **options)

    @staticmethod
    def stable_html_to_pdf(
        html_path: Path, target: Path, source_date: dict[str, str]
    ) -> None:
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

    def make_pdf(self, target: Path) -> None:
        html_path = self.make_html_dir(self._tmp)
        Eprint.stable_html_to_pdf(html_path, target, self._source_date_epoch())

    def make_html_and_pdf(self, html_target: Never, pdf_target: None = None) -> None:
        warn("Call method make and set EprinterConfig.show_pdf_icon", DeprecationWarning)
        self.make(html_target)

    def make(self, html_target: Path, pdf_target: Never | None = None) -> None:
        if pdf_target is not None:
            msg = "pdf_target argument is ignored; use EprinterConfig.show_pdf_icon"
            warn(msg, DeprecationWarning)
        html_path = self.make_html_dir(html_target)
        if self._add_pdf:
            pdf_path = html_target / "article.pdf"
            Eprint.stable_html_to_pdf(html_path, pdf_path, self._source_date_epoch())

    def _source_date_epoch(self) -> dict[str, str]:
        ret = dict()
        date_str = self.webstract.get('date')
        if date_str is not None:
            d = date.fromisoformat(date_str)
            doc_date = datetime.combine(d, time(0), timezone.utc)
            source_mtime = doc_date.timestamp()
            if source_mtime:
                ret["SOURCE_DATE_EPOCH"] = "{:.0f}".format(source_mtime)
        return ret


def eprint_dir(
    config: EprinterConfig,
    src: Path | str,
    target_dir: Path | str,
    pdf_target: Never | None = None,
) -> None:
    target_dir = Path(target_dir)
    if pdf_target is not None:
        msg = "pdf_target argument is ignored; use EprinterConfig.show_pdf_icon"
        warn(msg, DeprecationWarning)
    with tempfile.TemporaryDirectory() as tmpdir:
        webstract = webstract_from_jats(src)
        eprint = Eprint(webstract, Path(tmpdir), config)
        eprint.make(target_dir)
