import io, subprocess
from pathlib import Path
from importlib import resources
from typing import Any, Iterable

from .baseprint import BaseprintParse
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
    parse = BaseprintParse()
    bp = parse.baseprint(jats_src)
    if bp is None:
        raise ValueError()
    ret['title'] = bp.title.inner_html()
    ret['contributors'] = list()
    for a in bp.authors:
        d: dict[str, Any] = {'surname': a.surname, 'type': 'author'}
        if a.given_names:
            d['given-names'] = a.given_names
        if a.email:
            d['email'] = [a.email]
        if a.orcid:
            d['orcid'] = a.orcid.as_19chars()
        ret['contributors'].append(d)

    return ret
