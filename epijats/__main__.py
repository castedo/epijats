from .jats import JatsEprint, EprinterConfig

# std lib
import argparse, os, tempfile
from pathlib import Path


parser = argparse.ArgumentParser(description="Eprint JATS")
parser.add_argument("source", type=Path, metavar="source_dir", help="source directory")
parser.add_argument("target", type=Path, metavar="target_dir", help="target directory")
args = parser.parse_args()

config = EprinterConfig(dsi_base_url="https://perm.pub")

with tempfile.TemporaryDirectory() as tempdir:
    eprint = JatsEprint(args.source / "article.xml", tempdir, config)
    os.makedirs(target.parent, exist_ok=True)
    eprint.make_html(args.target / "article.html")
    eprint.make_pdf(args.target / "article.pdf")
