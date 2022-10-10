from .elife import parseJATS, meta_article_id_text

import json, os, sys, shutil, subprocess
from pathlib import Path
from datetime import datetime, date, time, timezone
from time import mktime
from pkg_resources import resource_filename
from ruamel.yaml import YAML


def run_pandoc(args, echo=True):
    cmd = ['pandoc'] + args
    if echo:
        print(' '.join([str(s) for s in cmd]))
    subprocess.run(cmd, check=True, stdout=sys.stdout, stderr=sys.stderr)


def git_hash_object(path):
    ret = subprocess.run(['git', 'hash-object', path],
        check=True, text=True, stdout=subprocess.PIPE, stderr=sys.stderr)
    return ret.stdout.rstrip()


def read_markdown_meta(path : Path):
    with open(path, 'r') as file:
        yaml = YAML(typ='safe')
        # only parse the first XML doc in file
        return next(yaml.load_all(file))


class EprinterConfig:
    def __init__(self, theme_dir=None):
        self.pandoc_opts = []
        if theme_dir:
            self.pandoc_opts = ["--data-dir", theme_dir, "--defaults", "pandoc.yaml"]


class JatsEprint:
    def __init__(self, config, jats_src, tmp):
        self.config = config
        self.src = Path(jats_src)
        self.tmp = Path(tmp) / "epijats"
        self.git_hash = git_hash_object(self.src)
        self._json = self.tmp / "article.json"
        self._meta = None
        soup = parseJATS.parse_document(self.src)
        self.dsi = meta_article_id_text(soup, "dsi")
        self._dates = parseJATS.pub_dates(soup)
        self._contributors = parseJATS.contributors(soup)

    @property
    def title_html(self):
        return self._get_html_template_var('title')

    @property
    def has_abstract(self):
        self._load()
        return 'abstract' in self._meta

    @property
    def abstract_html(self):
        return self._get_html_template_var('abstract')

    @property
    def body_html(self):
        return self._get_html_template_var('body')

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

    def _convert_to(self, dst):
        cmd = 'pandoc {} --from jats --standalone --output "{}"'.format(self.src, dst)
        print(cmd)
        subprocess.run(cmd, shell=True, check=True,
                       stdout=sys.stdout, stderr=sys.stderr)

    def _load(self):
        tmp_markdown = self.tmp / 'article.md'
        last_update = os.path.getmtime(self._json) if self._json.exists() else 0
        if last_update < os.path.getmtime(self.src):
            self._meta = None
            shutil.rmtree(self.tmp, ignore_errors=True)
            os.makedirs(self.tmp)
            self._convert_to(self._json)
        if not tmp_markdown.exists():
            run_pandoc([self._json, '-so', tmp_markdown])
        if self._meta is None:
            self._meta = read_markdown_meta(tmp_markdown)

    def make_extra_metadata(self):
        extra = self.tmp / 'extra_metadata.json'
        metadata = dict(contributors=self._contributors, dsi=self.dsi)
        with open(extra, 'w') as file:
            json.dump(metadata, file)
        return extra

    def make_latex(self, target):
        self._load()
        target = Path(target)
        os.makedirs(target.parent, exist_ok=True)
        pass_dir = self.src.with_name("pass")
        symlink = target.with_name("pass")
        if symlink.exists():
            os.unlink(symlink)
        if pass_dir.exists():
            os.symlink(pass_dir.resolve(), symlink)
        args = [self._json, '--to=latex', '--citeproc', '-so', target]
        args += ['--metadata-file', self.make_extra_metadata()]
        run_pandoc(args + self.config.pandoc_opts)
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
        tmp_pdf = self.tmp / "pdf"
        self._load() # need to make sure _load does not delete tmp_pdf later
        os.makedirs(tmp_pdf, exist_ok=True)
        tex = self.make_latex(self.tmp / "tex" / "article.tex")
        cmd = "rubber --pdf --into {} {}".format(tmp_pdf, tex)
        print(cmd)
        subprocess.run(cmd, shell=True, check=True,
                       stdout=sys.stdout, stderr=sys.stderr, env=env)
        os.makedirs(target.parent, exist_ok=True)
        shutil.copy(tmp_pdf / "article.pdf", target)
        return target

    def _get_html_template_var(self, name):
        self._load()
        p = self.tmp / (name + ".html")
        if not p.exists():
            args = [self._json, '--to', 'html', '--mathjax', '--output', p]
            tmpl = resource_filename(__name__, "templates/{}.pandoc".format(name))
            args += ['--citeproc', '--template', tmpl]
            args += self.config.pandoc_opts
            run_pandoc(args)
        with open(p) as f:
            return f.read()
