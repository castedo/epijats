from .util import up_to_date
from .jinja import JatsVars, WebPageGenerator

from .elife import parseJATS, meta_article_id_text

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


def git_hash_object(path):
    ret = subprocess.run(['git', 'hash-object', path],
        check=True, text=True, stdout=subprocess.PIPE, stderr=sys.stderr)
    return ret.stdout.rstrip()


class EprinterConfig:
    def __init__(self, theme_dir=None):
        self.pandoc_opts = []
        if theme_dir:
            self.pandoc_opts = ["--data-dir", theme_dir, "--defaults", "pandoc.yaml"]


class PandocJatsReader:
    def __init__(self, jats_src, tmp, config=None):
        self.src = jats_src
        self._tmp = Path(tmp) / "cache"
        self.config = config
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
            args = [self._json, '--to', 'html', '--mathjax', '--output', p]
            tmpl = resource_filename(__name__, "templates/{}.pandoc".format(name))
            args += ['--citeproc', '--template', tmpl]
            if self.config:
                args += self.config.pandoc_opts
            run_pandoc(args)
        with open(p) as f:
            return f.read()

    def make_latex(self, target, extra_metadata):
        target = Path(target)
        os.makedirs(target.parent, exist_ok=True)
        pass_dir = self.src.with_name("pass")
        symlink = target.with_name("pass")
        if symlink.exists():
            os.unlink(symlink)
        if pass_dir.exists():
            os.symlink(pass_dir.resolve(), symlink)
        args = [self._json, '--to=latex', '--citeproc', '-so', target]
        args += ['--metadata-file', self._make_metadata_file(extra_metadata)]
        if self.config:
            args += self.config.pandoc_opts
        run_pandoc(args)
        return target

    def _make_metadata_file(self, extra_metadata):
        extra_path = self._tmp / 'extra_metadata.json'
        with open(extra_path, 'w') as file:
            json.dump(extra_metadata, file)
        return extra_path


class JatsEprint:
    def __init__(self, jats_src, tmp, config=None):
        self.src = Path(jats_src)
        self._tmp = Path(tmp)
        self.git_hash = git_hash_object(self.src)
        soup = parseJATS.parse_document(self.src)
        self.dsi = meta_article_id_text(soup, "dsi")
        self._dates = parseJATS.pub_dates(soup)
        self._contributors = parseJATS.contributors(soup)
        self._pandoc = PandocJatsReader(self.src, self._tmp / "pandoc", config)
        self.has_abstract = self._pandoc.has_abstract
        self._gen = WebPageGenerator()

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

    def make_web_page(self, target):
        target = Path(target)
        os.makedirs(target.parent, exist_ok=True)
        ctx = dict(jats=JatsVars(self))
        self._gen.render_file('article.html.jinja', target, ctx)
        return target

    def make_pdf(self, target):
        assert isinstance(self.date, date)
        doc_date = datetime.combine(self.date, time(0), timezone.utc)
        source_mtime = doc_date.timestamp()
        if source_mtime:
            env = os.environ.copy()
            env["SOURCE_DATE_EPOCH"] = "{:.0f}".format(source_mtime)
        else:
            env = None
        tmp_pdf = self._tmp / "pdf"
        os.makedirs(tmp_pdf, exist_ok=True)
        metadata = dict(contributors=self._contributors, dsi=self.dsi)
        tex = self._pandoc.make_latex(self._tmp / "tex" / "article.tex", metadata)
        cmd = "rubber --pdf --into {} {}".format(tmp_pdf, tex)
        print(cmd)
        subprocess.run(cmd, shell=True, check=True,
                       stdout=sys.stdout, stderr=sys.stderr, env=env)
        os.makedirs(target.parent, exist_ok=True)
        shutil.copy(tmp_pdf / "article.pdf", target)
        return target
