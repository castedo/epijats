from .jats import JatsEprint, EprinterConfig

from weasyprint import LOGGER

# std lib
import argparse, logging, os, subprocess, sys, tempfile
from pathlib import Path


parser = argparse.ArgumentParser(description="Eprint JATS")
parser.add_argument("source", type=Path, metavar="source_dir", help="source directory")
parser.add_argument("target", type=Path, metavar="target_dir", help="target directory")
args = parser.parse_args()

LOGGER.setLevel(logging.INFO)
LOGGER.addHandler(logging.StreamHandler())

config = EprinterConfig(dsi_base_url="https://perm.pub")

with tempfile.TemporaryDirectory() as tempdir:
    eprint = JatsEprint(args.source / "article.xml", tempdir, config)
    os.makedirs(args.target , exist_ok=True)
    eprint.make_html_dir(args.target)
    eprint.make_pdf(args.target / "article.pdf")
