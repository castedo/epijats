import io, subprocess
from pathlib import Path
from importlib import resources
from typing import Any, Iterable

from .webstract import Webstract, Source


def parse_authors(jats_src: Path) -> list[dict[str, Any]]:
    import bs4
    from elifetools import utils

    with open(jats_src, "rb") as f:
        soup = bs4.BeautifulSoup(f, "lxml-xml")

    article_meta_tag = utils.extract_first_node(soup, "article-meta")
    assert article_meta_tag
    contributor_tags = utils.extract_nodes(article_meta_tag, "contrib")
    contrib_tags = [tag for tag in contributor_tags if tag.parent.name == "contrib-group"]

    ret = []
    for tag in contrib_tags:
        contributor: dict[str, Any] = {}
        utils.copy_attribute(tag.attrs, "contrib-type", contributor, "type")
        assert "type" in contributor
        contrib_id_tag = utils.first(utils.extract_nodes(tag, "contrib-id"))
        assert contrib_id_tag
        assert "contrib-id-type" in contrib_id_tag.attrs
        assert contrib_id_tag["contrib-id-type"] == "orcid"
        contributor["orcid"] = utils.node_contents_str(contrib_id_tag)
        for email_tag in utils.extract_nodes(tag, "email"):
            contributor["email"] = [email_tag.text]
        utils.set_if_value(
            contributor, "surname", utils.first_node_str_contents(tag, "surname")
        )
        utils.set_if_value(
            contributor,
            "given-names",
            utils.first_node_str_contents(tag, "given-names"),
        )
        ret.append(contributor)
    return ret


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
    ret['contributors'] = parse_authors(jats_src)
    for c in ret['contributors']:
        if 'orcid' in c:
            c['orcid'] = c['orcid'].rsplit("/", 1)[-1]

    return ret
