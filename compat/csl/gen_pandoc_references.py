#!/usr/bin/python3

import argparse, subprocess, sys
from pathlib import Path


STYLES = [
  Path(__file__).parent / "../../epijats/csl/full-preview.csl",
  'modern-language-association.csl',
  Path(__file__).parent / "../../epijats/csl/abridged.csl",
  'vancouver.csl',
  'ieee.csl',
  'iso690-numeric-en.csl',
  'apa.csl',
  'apa-annotated-bibliography.csl',
  'chicago-author-date.csl',
  'harvard-cite-them-right.csl',
  'howard-hughes-medical-institute.csl',
]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("csljson", type=str, help="path to CSL-JSON file")
    parser.add_argument("csldir", type=Path, help="path to CSL files")
    args = parser.parse_args()

    sys.stdout.write("<hthml>\n<head></head>\n<body>\n")
    for s in STYLES:
        sys.stdout.write(f"<h2>{s}</h2>\n")
        sys.stdout.flush()
        cmd = [
            'pandoc', args.csljson,
            '--from', 'csljson',
            '--citeproc',
            '--csl', str(args.csldir / s)
        ]
        subprocess.run(cmd, check=True)
    sys.stdout.write("</body>\n</html>\n")
