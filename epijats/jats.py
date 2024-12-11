import io, subprocess
from pathlib import Path
from importlib import resources
from typing import Any, Iterable

from elifetools import parseJATS

from .webstract import Webstract, Source


def run_pandoc(args: Iterable[Any], echo: bool = True) -> bytes:
    cmd = ["pandoc"] + [str(a) for a in args]
    if echo:
        print(" ".join(cmd))
    return subprocess.check_output(cmd)


def pandoc_jats_to_webstract(jats_src: Path | str) -> bytes:
    rp = resources.files(__package__).joinpath("pandoc")
    with (
        resources.as_file(rp.joinpath("epijats.yaml")) as defaults_file,
        resources.as_file(rp.joinpath("epijats.csl")) as csl_file,
        resources.as_file(rp.joinpath("webstract.tmpl")) as tmpl_file,
    ):
        args = ["-d", defaults_file, "--csl", csl_file, "--template", tmpl_file]
        return run_pandoc(args + [jats_src])


def webstract_from_jats(src: Path | str) -> Webstract:
    import jsoml

    src = Path(src)
    jats_src = src / "article.xml" if src.is_dir() else src
    xmlout = pandoc_jats_to_webstract(jats_src)
    data = jsoml.load(io.BytesIO(xmlout))
    if not isinstance(data, dict):
        raise ValueError("JSOML webstract must be object/dictionary.")
    ret = Webstract(data)
    ret['source'] = Source(path=src)

    soup = parseJATS.parse_document(jats_src)

    ret['contributors'] = parseJATS.contributors(soup)
    for c in ret['contributors']:
        if 'orcid' in c:
            c['orcid'] = c['orcid'].rsplit("/", 1)[-1]

    return ret
