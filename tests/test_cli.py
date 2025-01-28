from epijats import __main__ , Webstract

import pytest
from pathlib import Path


CASES_DIR = Path(__file__).parent / "cases"


def _run(src, dest, args=""):
    if isinstance(args, str):
        args = args.split()
    args = [str(src), str(dest)] + [str(a) for a in args]
    __main__.main(args)


def test_jats_to_json(tmp_path):
    subcase_dir = CASES_DIR / "webstract/basic1"
    dest = tmp_path / "output_file"
    _run(subcase_dir / "input", dest, "--to json")
    load_func = Webstract.load_json
    expect = Webstract.load_json(subcase_dir / "output.json")
    assert load_func(dest) == expect


INVALID_ARGS = [
    "--from html --to jats",
    "--from html --to json",
]

@pytest.mark.parametrize("case", INVALID_ARGS)
def test_invalid_order(case):
    with pytest.raises(SystemExit):
        cmd_line_args = case.split() + ["/dev/null", "/dev/null"]
        __main__.main(cmd_line_args)
