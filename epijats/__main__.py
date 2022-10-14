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

config = EprinterConfig(
    dsi_base_url="https://perm.pub",
    math_css_url="static/katex/katex.css",
)

with tempfile.TemporaryDirectory() as tempdir:
    eprint = JatsEprint(args.source / "article.xml", tempdir, config)
    os.makedirs(args.target , exist_ok=True)
    eprint.make_html(args.target / "article.html")
    eprint.make_pdf(args.target / "article.pdf")
    if not os.path.exists(args.target / "static"):
        # using shell cp -r to avoid copying permissions, especially SELinux context
        cmd = ["cp", "-r", eprint.get_static_dir(), args.target / "static"]
        subprocess.run(cmd, check=True, stdout=sys.stdout, stderr=sys.stderr)
