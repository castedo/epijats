from elifetools import parseJATS
from .webstract import Webstract, Source

#std library
import io, subprocess
from pathlib import Path
from datetime import datetime
from time import mktime
from importlib import resources
from warnings import warn


def run_pandoc(args, echo=True):
    cmd = ["pandoc"] + [str(a) for a in args]
    if echo:
        print(" ".join(cmd))
    return subprocess.check_output(cmd)


def pandoc_jats_to_webstract(jats_src):
    rp = resources.files(__package__).joinpath("pandoc")
    with (
        resources.as_file(rp.joinpath("epijats.yaml")) as defaults_file,
        resources.as_file(rp.joinpath("epijats.csl")) as csl_file,
        resources.as_file(rp.joinpath("webstract.tmpl")) as tmpl_file,
    ):
        args = ["-d", defaults_file, "--csl", csl_file, "--template", tmpl_file]
        return run_pandoc(args + [jats_src])


def webstract_from_jats(src, pandoc_opts=None):
    import jsoml

    if pandoc_opts is not None:
        warn("Stop passing pandoc_opts to webstract_from_jats.", DeprecationWarning)

    src = Path(src)
    jats_src = src / "article.xml" if src.is_dir() else src
    xmlout = pandoc_jats_to_webstract(jats_src)
    ret = Webstract(jsoml.load(io.BytesIO(xmlout)))
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
