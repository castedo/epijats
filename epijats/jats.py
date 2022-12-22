from .util import up_to_date, copytree_nostat, git_hash_object
from .jinja import JatsVars, WebPageGenerator
from .elife import parseJATS, meta_article_id_text

import weasyprint
from lxml import etree

import json, os, sys, shutil, subprocess
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


class PandocJatsReader:
    def __init__(self, jats_src, tmp, pandoc_opts):
        self.src = Path(jats_src)
        self._tmp = Path(tmp)
        self._pandoc_opts = list(pandoc_opts)
        self._json = self._tmp / "article.json"
        if not up_to_date(self._json, self.src):
            shutil.rmtree(self._tmp, ignore_errors=True)
            os.makedirs(self._tmp)
            run_pandoc([self.src, "--from=jats", "-s", "--output", self._json])
        with open(self._json) as file:
            self.has_abstract = "abstract" in json.load(file)["meta"]

    def get_html_template_var(self, name):
        p = self._tmp / (name + ".html")
        if not p.exists():
            args = [self._json, '--to', 'html', '--output', p]
            tmpl = resource_filename(__name__, "templates/{}.pandoc".format(name))
            args += ["--template", tmpl, "--citeproc", "--filter=pandoc-katex-filter"]
            #args += ["--template", tmpl, "--filter=pandoc-katex-filter"]
            args += ["--shift-heading-level-by=1"]
            run_pandoc(args + self._pandoc_opts)
        with open(p) as f:
            return f.read()


class JatsBaseprint:
    def __init__(self, src, tmp, pandoc_opts):
        self.jats_src = Path(src) / "article.xml"
        self._pandoc = PandocJatsReader(self.jats_src, tmp, pandoc_opts)
        self.has_abstract = self._pandoc.has_abstract
        soup = parseJATS.parse_document(self.jats_src)
        self.dsi = meta_article_id_text(soup, "dsi")
        self._dates = parseJATS.pub_dates(soup)
        self._contributors = parseJATS.contributors(soup)
        #TODO: generaize to work with folder based baseprint, not just single file
        self.git_hash = git_hash_object(self.jats_src)

    def symlink_pass_dir(self, target_dir):
        pass_dir = self.jats_src.with_name("pass")
        symlink = target_dir / "pass"
        if symlink.exists():
            os.unlink(symlink)
        if pass_dir.exists():
            os.symlink(pass_dir.resolve(), symlink)

    @property
    def title_html(self):
        return self._pandoc.get_html_template_var('title')

    @property
    def abstract_html(self):
        if self.has_abstract:
            return self._pandoc.get_html_template_var('abstract') 
        return None

    @property
    def body_html(self):
        return self._pandoc.get_html_template_var('body')

    @property
    def date(self):
        ret = None
        if self._dates:
            ret = datetime.fromtimestamp(mktime(self._dates[0]["date"])).date()
        return ret

    @property
    def authors(self):
        ret = []
        for c in self._contributors:
            ret.append(c["given-names"] + " " + c["surname"])
        return ret

    @property
    def contributors(self):
        ret = []
        return self._contributors


class JatsEprint:
    def __init__(self, baseprint, tmp, config=None):
        if config is None:
            config = EprinterConfig()
        self._tmp = Path(tmp)
        self._html_ctx = config.urls
        self._html_ctx["article_style"] = config.article_style
        self._html_ctx["embed_web_fonts"] = config.embed_web_fonts
        self._gen = config._gen
        self._basep = baseprint

    def _get_static_dir(self):
        return Path(resource_filename(__name__, "static/"))

    def _get_html(self):
        html_dir = self._tmp
        os.makedirs(html_dir, exist_ok=True)
        ret = html_dir / "article.html"
        # for now just assume math is always needed
        ctx = dict(jats=JatsVars(self._basep), **self._html_ctx, has_math=True)
        self._gen.render_file('article.html.jinja', ret, ctx)
        if not ret.with_name("static").exists():
            os.symlink(self._get_static_dir(), ret.with_name("static"))
        self._basep.symlink_pass_dir(html_dir)
        return ret

    def make_html_dir(self, target):
        copytree_nostat(self._get_html().parent, target)

    def make_pdf(self, target):
        target = Path(target)
        os.environ.update(self._source_date_epoch())
        weasyprint.HTML(self._get_html()).write_pdf(target)
        return target

    def _source_date_epoch(self):
        ret = dict()
        assert isinstance(self._basep.date, date)
        doc_date = datetime.combine(self._basep.date, time(0), timezone.utc)
        source_mtime = doc_date.timestamp()
        if source_mtime:
            ret["SOURCE_DATE_EPOCH"] = "{:.0f}".format(source_mtime)
        return ret
