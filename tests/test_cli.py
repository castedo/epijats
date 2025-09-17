from epijats import __main__

from pathlib import Path


CASES_DIR = Path(__file__).parent / "cases"


def _run(src, dest, args=""):
    if isinstance(args, str):
        args = args.split()
    args = [str(src), str(dest)] + [str(a) for a in args]
    __main__.main(args)


def test_cli_restyle(tmp_path):
    subcase_dir = CASES_DIR / "webstract/basic1"
    _run(subcase_dir / "input", tmp_path, "--to xml")
    with open(subcase_dir / "output" / "article.xml", "r") as f:
        expect = f.read().strip()
    with open(tmp_path / "article.xml", "r") as f:
        got = f.read().strip()
    assert got == expect
