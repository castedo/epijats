import io, subprocess
from pathlib import Path
from importlib import resources
from typing import Any, Iterable

from lxml import etree

from .webstract import Webstract, Source


def extract_nodes(tree: etree.ElementTree, nodename: str) -> list[Any]:
    return [node for node in tree.iterdescendants() if node.tag == nodename]


def parse_authors(jats_src: Path) -> list[dict[str, Any]]:
    with open(jats_src, "rb") as f:
        tree = etree.parse(f).getroot()
    article_meta_tag = extract_nodes(tree, "article-meta")[0]
    ret = []
    for tag in extract_nodes(article_meta_tag, "contrib"):
        contributor: dict[str, Any] = {}
        contributor["type"] = tag.attrib["contrib-type"]
        assert "type" in contributor
        contrib_id_tag = extract_nodes(tag, "contrib-id")[0]
        assert "contrib-id-type" in contrib_id_tag.attrib
        assert contrib_id_tag.attrib["contrib-id-type"] == "orcid"
        contributor["orcid"] = contrib_id_tag.text
        for email_tag in extract_nodes(tag, "email"):
            contributor["email"] = [email_tag.text]
        contributor["surname"] = extract_nodes(tag, "surname")[0].text
        contributor["given-names"] = extract_nodes(tag, "given-names")[0].text
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
