import argparse, logging
from pathlib import Path
from sys import stderr
from typing import Any

from . import Eprint, EprinterConfig
from .eprint import SimpleIssuesPage
from .jats import webstract_from_jats
from .xml.baseprint import restyle_xml


def weasyprint_setup() -> bool:
    try:
        import weasyprint

        weasyprint.LOGGER.setLevel(logging.INFO)
        weasyprint.LOGGER.addHandler(logging.StreamHandler())
        return True
    except ImportError as ex:
        print(ex, file=stderr)
        print("weasyprint must be installed to write pdf", file=stderr)
        return False


def version() -> str:
    try:
        from ._version import version

        return str(version)
    except ImportError:
        return "0.0.0"


class Main:
    inpath: Path
    outpath: Path
    outform: str
    no_web_fonts: bool

    def __init__(self, cmd_line_args: Any = None):
        parser = argparse.ArgumentParser(prog="epijats", description="Eprint JATS")
        parser.add_argument("--version", action="version", version=version())
        parser.add_argument("inpath", type=Path, help="input directory/path")
        parser.add_argument("outpath", type=Path, help="output directory/path")
        parser.add_argument(
            "--to",
            dest="outform",
            choices=["xml", "html", "html+pdf", "pdf"],
            default="pdf",
            help="format of target",
        )
        parser.add_argument(
            "--no-web-fonts",
            action="store_true",
            help="Do not use online web fonts",
        )
        parser.parse_args(cmd_line_args, self)
        if self.inpath == self.outpath:
            parser.error(f"Output path must not equal input path: {self.inpath}")

    def run(self) -> int:
        return self.restyle() if self.outform == "xml" else self.convert()

    def restyle(self) -> int:
        if not restyle_xml(self.inpath, self.outpath):
            print(f"Invalid XML file {self.inpath}", file=stderr)
            return 1
        return 0

    def convert(self) -> int:
        config = EprinterConfig(dsi_domain="perm.pub")
        config.embed_web_fonts = not self.no_web_fonts
        webstract = webstract_from_jats(self.inpath)
        issues_page = SimpleIssuesPage(webstract)
        assert self.outform in ["html", "html+pdf", "pdf"]
        if self.outform == "html+pdf":
            config.show_pdf_icon = True
        eprint = Eprint(webstract, config=config, issues_page=issues_page)
        if self.outform in ["html+pdf", "pdf"]:
            if not weasyprint_setup():
                return 1
        if self.outform in ["html", "html+pdf"]:
            eprint.make(self.outpath)
        elif self.outform == "pdf":
            if not self.outpath.suffix == ".pdf":
                msg = "Writing PDF to filename without .pdf suffix: {}"
                print(msg.format(self.outpath.name), file=stderr)
            eprint.make_pdf(self.outpath)
        return 0


def main(args: Any = None) -> int:
    return Main(args).run()


if __name__ == "__main__":
    exit(main())
