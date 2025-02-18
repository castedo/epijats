#!/usr/bin/python3

import argparse
from datetime import date
from pathlib import Path

from fastindex import make_index


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Make PubMed Central Data Fast Index")
    parser.add_argument("pmcpath", type=Path, help="path to PMC S3 data dump")
    parser.add_argument("begin", type=date.fromisoformat, help="inclusive begin date")
    parser.add_argument("end", type=date.fromisoformat, help="exclusive day past last")
    args = parser.parse_args()
    make_index(args.pmcpath, args.begin, args.end)
    print("Done.")
