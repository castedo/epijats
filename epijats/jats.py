from .util import up_to_date, copytree_nostat, swhid_from_files

from .jinja import WebPageGenerator
from .elife import parseJATS
from .webstract import Webstract, Source

import weasyprint

import os, sys, shutil, subprocess
from pathlib import Path
from datetime import datetime, date, time, timezone
from time import mktime
from pkg_resources import resource_filename


def run_pandoc(args, echo=True):
    cmd = ['pandoc'] + args
    if echo:
        print(' '.join([str(s) for s in cmd]))
    subprocess.run(cmd, check=True, stdout=sys.stdout, stderr=sys.stderr)


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
        self._gen = WebPageGenerator()


def pandoc_jats_to_webstract(jats_src, dest, pandoc_opts):
    args = [jats_src, "--from=jats", "-s", '--to', 'html', "--output", dest]
    tmpl = resource_filename(__name__, "templates/webstract.pandoc")
    args += ["--template", tmpl, "--citeproc", "--filter=pandoc-katex-filter"]
    args += ["--shift-heading-level-by=1", "--wrap=preserve"]
    run_pandoc(args + pandoc_opts)


class JatsBaseprint:
    def __init__(self, src, tmp, pandoc_opts):
        src = Path(src)
        self.jats_src = src / "article.xml"

        dest = Path(tmp) / "webstract.jsoml"
        if not up_to_date(dest, self.jats_src):
            shutil.rmtree(tmp, ignore_errors=True)
            os.makedirs(tmp)
            pandoc_jats_to_webstract(self.jats_src, dest, pandoc_opts)
        self.webstract = Webstract.load_xml(dest)

        self.webstract['source'] = Source(path=src)
        soup = parseJATS.parse_document(self.jats_src)

        dates = parseJATS.pub_dates(soup)
        if dates:
            self.date = datetime.fromtimestamp(mktime(dates[0]["date"])).date()
        else:
            self.date = None
        self.webstract['date'] = self.date

        self.contributors = parseJATS.contributors(soup)
        for c in self.contributors:
            c['orcid'] = c['orcid'].rsplit("/", 1)[-1]
        self.webstract['contributors'] = self.contributors

    @property
    def title_html(self):
        return self.webstract.facade.title

    @property
    def has_abstract(self):
        return "abstract" in self.webstract

    @property
    def abstract_html(self):
        return self.webstract.facade.abstract

    @property
    def body_html(self):
        return self.webstract.facade.body

    @property
    def authors(self):
        ret = []
        for c in self.contributors:
            ret.append(c["given-names"] + " " + c["surname"])
        return ret

    def to_webstract(self):
        return self.webstract


class Eprint:
    def __init__(self, webstract, tmp, config=None):
        if config is None:
            config = EprinterConfig()
        self._tmp = Path(tmp)
        self._html_ctx = config.urls
        self._html_ctx["article_style"] = config.article_style
        self._html_ctx["embed_web_fonts"] = config.embed_web_fonts
        self._gen = config._gen
        self.webstract = webstract

    def _get_static_dir(self):
        return Path(resource_filename(__name__, "static/"))

    def _get_html(self):
        html_dir = self._tmp
        os.makedirs(html_dir, exist_ok=True)
        ret = html_dir / "article.html"
        # for now just assume math is always needed
        ctx = dict(doc=self.webstract.facade, **self._html_ctx, has_math=True)
        self._gen.render_file('article.html.jinja', ret, ctx)
        if not ret.with_name("static").exists():
            os.symlink(self._get_static_dir(), ret.with_name("static"))
        if self.webstract.source.subpath_exists("pass"):
            self.webstract.source.symlink_subpath(html_dir / "pass", "pass")
        return ret

    def make_html_dir(self, target):
        copytree_nostat(self._get_html().parent, target)

    def make_pdf(self, target):
        target = Path(target)
        os.environ.update(self._source_date_epoch())
        html_path = self._get_html()
        if os.environ.get("EPIJATS_SKIP_PDF"):
            return
        weasyprint.HTML(html_path).write_pdf(target)
        return target

    def _source_date_epoch(self):
        ret = dict()
        assert isinstance(self.webstract.date, date)
        doc_date = datetime.combine(self.webstract.date, time(0), timezone.utc)
        source_mtime = doc_date.timestamp()
        if source_mtime:
            ret["SOURCE_DATE_EPOCH"] = "{:.0f}".format(source_mtime)
        return ret
