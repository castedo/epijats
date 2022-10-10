from .jats import JatsEprint, EprinterConfig
from weasyprint import HTML

# std lib
import argparse, os, shutil, tempfile
from pathlib import Path


parser = argparse.ArgumentParser(description="Eprint JATS")
parser.add_argument("source", type=Path, metavar="source_dir", help="source directory")
parser.add_argument("target", type=Path, metavar="target_dir", help="target directory")
args = parser.parse_args()

config = EprinterConfig(dsi_base_url="https://perm.pub")

with tempfile.TemporaryDirectory() as tempdir:
    stage = Path(tempdir) / "stage.html"
    JatsEprint(args.source / "article.xml", tempdir, config).make_web_page(stage)
    # make_web_page streams data to file
    # so copy the file data all at once
    # otherwise auto-reload/watch/live web servers will serve partial files
    html_target = args.target / "article.html"
    shutil.copy(stage, html_target)
    HTML(html_target).write_pdf(args.target / "article.pdf")
