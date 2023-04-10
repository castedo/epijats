from elifetools import parseJATS
from .webstract import Webstract, Source

#std library
import sys, subprocess
from pathlib import Path
from datetime import datetime
from time import mktime
from pkg_resources import resource_filename


def run_pandoc(args, echo=True):
    cmd = ["pandoc"] + args
    if echo:
        print(" ".join([str(s) for s in cmd]))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=sys.stderr)
    return proc.stdout


def pandoc_jats_to_webstract(jats_src, pandoc_opts):
    args = [jats_src, "--from=jats", "-s", '--to', 'html']
    tmpl = resource_filename(__name__, "templates/webstract.pandoc")
    args += ["--template", tmpl, "--citeproc", "--filter=pandoc-katex-filter"]
    args += ["--metadata", "reference-section-title=References"]
    args += ["--metadata", "link-citations=true"]
    args += ["--shift-heading-level-by=1", "--wrap=preserve"]
    return run_pandoc(args + pandoc_opts)


def webstract_from_jats(src, pandoc_opts):
    src = Path(src)
    jats_src = src / "article.xml" if src.is_dir() else src
    pipeout = pandoc_jats_to_webstract(jats_src, pandoc_opts)
    ret = Webstract.load_xml(pipeout)

    ret['source'] = Source(path=src)

    soup = parseJATS.parse_document(jats_src)

    dates = parseJATS.pub_dates(soup)
    if dates:
        date = datetime.fromtimestamp(mktime(dates[0]["date"])).date()
    else:
        date = None
    ret['date'] = date

    ret['contributors'] = parseJATS.contributors(soup)
    for c in ret['contributors']:
        if 'orcid' in c:
            c['orcid'] = c['orcid'].rsplit("/", 1)[-1]

    return ret
