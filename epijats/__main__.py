import epijats
from epijats.jats import webstract_from_jats

from weasyprint import LOGGER

# std lib
import argparse, logging, os, subprocess, sys, tempfile
from pathlib import Path


parser = argparse.ArgumentParser(description="Eprint JATS")
parser.add_argument("source", type=Path, metavar="source_dir", help="source directory")
parser.add_argument("target", type=Path, metavar="target_dir", help="target directory")
parser.add_argument(
    "--no-web-fonts",
    default=False,
    action="store_true",
    help="Do not use online web fonts",
)
args = parser.parse_args()

LOGGER.setLevel(logging.INFO)
LOGGER.addHandler(logging.StreamHandler())

config = epijats.EprinterConfig(dsi_base_url="https://perm.pub")
config.embed_web_fonts = not args.no_web_fonts

with tempfile.TemporaryDirectory() as tempdir:
    webstract = webstract_from_jats(args.source, config.pandoc_opts)
    eprint = epijats.Eprint(webstract, Path(tempdir) / "html", config)
    os.makedirs(args.target , exist_ok=True)
    eprint.make_html_dir(args.target)
    eprint.make_pdf(args.target / "article.pdf")
