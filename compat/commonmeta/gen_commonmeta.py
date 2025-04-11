#!/usr/bin/python3

import argparse, json, sys
from pathlib import Path
from typing import Any

from epijats.baseprint import Author, Baseprint
from epijats.parse import parse_baseprint
from epijats.util import swhid_from_files
from epijats.html import HtmlGenerator


HTML = HtmlGenerator()


def commonmeta_for_author(author: Author) -> dict[str, Any]:
    ret = {
        'type': "Person",
        'contributorRoles': ["Author"],
    }
    if author.name.surname:
        ret['familyName'] = author.name.surname
    if author.name.given_names:
        ret['givenName'] = author.name.given_names
    if author.orcid:
        ret['id'] = "https://orcid.org/" + author.orcid.isni
    return ret


def extract_commonmeta(bdom: Baseprint) -> dict[str, Any]:
    ret: dict[str, Any] = dict()
    ret['titles'] = {'title': HTML.content_to_str(bdom.title)}
    ret['descriptions'] = [
        {
            'description': HTML.proto_section_to_str(bdom.abstract),
            'type': "Abstract",
        },
    ]
    ret['contributors'] = [commonmeta_for_author(a) for a in bdom.authors]
    if bdom.permissions:
        ret['license'] = {
            'id': str(bdom.permissions.license.cc_license_type),
            'url': bdom.permissions.license.license_ref,
        }
    return ret


def commonmeta_from_snapshot(path: Path) -> dict[str, Any]:
    ret = {
        'id': swhid_from_files(path),
    }
    bdom = parse_baseprint(path)
    if bdom is None:
        raise ValueError(f"Invalid XML file {path}")
    ret.update(extract_commonmeta(bdom))
    return ret


def main(cmd_line_args: Any = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inpath", type=Path, help="input directory/path")
    parser.add_argument("outpath", type=Path, help="output directory/path")
    args = parser.parse_args(cmd_line_args)
    try:
        meta = commonmeta_from_snapshot(args.inpath)
    except ValueError as ex:
        print(ex, file=sys.stderr)
        return 1
    with open(args.outpath, 'w') as fout:
        json.dump(meta, fout)
        fout.write("\n")
    return 0


if __name__ == "__main__":
    exit(main())
