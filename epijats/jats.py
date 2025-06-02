import os, subprocess, tempfile
from pathlib import Path
from importlib import resources
from typing import Any, Iterable

from .parse import parse_baseprint
from .html import HtmlGenerator
from .webstract import Webstract
from .condition import FormatIssue
from . import restyle


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
    if "EPIJATS_USE_PANDOC" not in os.environ:
        ret['body'] = gen.html_body_content(bp)
    else:
        with tempfile.TemporaryDirectory() as tempdir:
            if "EPIJATS_NO_RESTYLE" not in os.environ:
                restyle.write_baseprint(bp, Path(tempdir))
                jats_src = Path(tempdir) / "article.xml"
            ret['body'] = pandoc_jats_to_webstract(jats_src)
    ret.set_source_from_path(src)
    ret['title'] = gen.content_to_str(bp.title)
    ret['contributors'] = list()
    if bp.abstract :
        ret['abstract'] = gen.proto_section_to_str(bp.abstract)
    for a in bp.authors:
        d: dict[str, Any] = {'surname': a.name.surname, 'type': 'author'}
        if a.name.given_names:
            d['given-names'] = a.name.given_names
        if a.email:
            d['email'] = [a.email]
        if a.orcid:
            d['orcid'] = a.orcid.as_19chars()
        ret['contributors'].append(d)
    ret['issues'] = [i.as_pod() for i in issues]
    if bp.permissions:
        if bp.permissions.license:
            if bp.permissions.license.license_ref:
                ret['license_ref'] = bp.permissions.license.license_ref
            ret['license_p'] = gen.content_to_str(bp.permissions.license.license_p)
            if bp.permissions.license.cc_license_type:
                ret['cc_license_type'] = str(bp.permissions.license.cc_license_type)
        if bp.permissions.copyright:
            ret['copyright'] = gen.content_to_str(bp.permissions.copyright.statement)
    return ret
