from .jats import JatsEprint

# std lib
import argparse, os, shutil, tempfile
from pathlib import Path


parser = argparse.ArgumentParser(description="Eprint JATS")
parser.add_argument("source", help="source")
parser.add_argument("target", help="target")
args = parser.parse_args()

with tempfile.TemporaryDirectory() as tempdir:
    stage = Path(tempdir) / 'stage.html'
    JatsEprint(args.source, tempdir).make_web_page(stage)
    # make_web_page streams data to file
    # so copy the file data all at once
    # otherwise auto-reload/watch/live web servers will serve partial files
    shutil.copy(stage, args.target)
