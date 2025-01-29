import os, subprocess
from pathlib import Path
from importlib import resources
from typing import Any, Iterable

from .parse import parse_baseprint
from .html import HtmlGenerator
from .webstract import Webstract, Source
from .condition import FormatIssue


def run_pandoc(args: Iterable[Any], echo: bool = True) -> str:
    cmd = ["pandoc"] + [str(a) for a in args]
    if echo:
        print(" ".join(cmd))
    return subprocess.check_output(cmd).decode()


def pandoc_jats_to_webstract(jats_src: Path | str) -> str:
    rp = resources.files(__package__).joinpath("pandoc")
    with (
        resources.as_file(rp.joinpath("epijats.yaml")) as defaults_file,
        resources.as_file(rp.joinpath("epijats.csl")) as csl_file,
    ):
        args = ["-d", defaults_file, "--csl", csl_file]
        return run_pandoc(args + [jats_src])


def webstract_from_jats(src: Path | str) -> Webstract:
    src = Path(src)
    jats_src = src / "article.xml" if src.is_dir() else src
    issues: list[FormatIssue] = []
    bp = parse_baseprint(jats_src, issues.append)
    if bp is None:
        raise ValueError()
    gen = HtmlGenerator()
    ret = Webstract()
    if "EPIJATS_NO_PANDOC" in os.environ:
        ret['body'] = gen.proto_section_to_str(bp.body)
    else:
        ret['body'] = pandoc_jats_to_webstract(jats_src)
    ret['source'] = Source(path=src)
    ret['title'] = gen.content_to_str(bp.title)
    ret['contributors'] = list()
    if bp.abstract :
        ret['abstract'] = gen.proto_section_to_str(bp.abstract)
    for a in bp.authors:
        d: dict[str, Any] = {'surname': a.surname, 'type': 'author'}
        if a.given_names:
            d['given-names'] = a.given_names
        if a.email:
            d['email'] = [a.email]
        if a.orcid:
            d['orcid'] = a.orcid.as_19chars()
        ret['contributors'].append(d)
    ret['issues'] = [i.as_pod() for i in issues]
    return ret
