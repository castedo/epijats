import argparse, importlib, logging, shutil, tempfile
from pathlib import Path
from sys import stderr
from typing import Any

from . import Eprint, EprinterConfig, Webstract
from . import restyle
from .parse import parse_baseprint
from .util import copytree_nostat


def enable_weasyprint_logging() -> None:
    from weasyprint import LOGGER

    LOGGER.setLevel(logging.INFO)
    LOGGER.addHandler(logging.StreamHandler())


def version() -> str:
    try:
        from ._version import version
        return str(version)
    except ImportError:
        return "0.0.0"


class Main:
    inpath: Path
    outpath: Path
    inform: str
    outform: str
    no_web_fonts: bool

    def __init__(self, cmd_line_args: Any = None):
        self.parser = argparse.ArgumentParser(description="Eprint JATS")
        self.parser.add_argument("--version", action="version", version=version())
        self.parser.add_argument("inpath", type=Path, help="input directory/path")
        self.parser.add_argument("outpath", type=Path, help="output directory/path")
        self.parser.add_argument(
            "--from",
            dest="inform",
            choices=["jats", "json", "html"],
            default="jats",
            help="format of source",
        )
        self.parser.add_argument(
            "--to",
            dest="outform",
            choices=["jats", "json", "html", "html+pdf", "pdf"],
            default="pdf",
            help="format of target",
        )
        self.parser.add_argument(
            "--no-web-fonts",
            action="store_true",
            help="Do not use online web fonts",
        )

        self.parser.parse_args(cmd_line_args, self)

        self.config = EprinterConfig(dsi_domain="perm.pub")
        self.config.embed_web_fonts = not self.no_web_fonts

    def run(self) -> int:
        self.check_conversion()
        if self.just_copy():
            return 0
        if self.inform == "jats" and self.outform == "jats":
            bdom = parse_baseprint(self.inpath)
            if bdom is None:
                print(f"Invalid XML file {self.inpath}", file=stderr)
                return 1
            restyle.write_baseprint(bdom, self.outpath)
            return 0
        webstract = self.load_webstract()
        if webstract is None:
            assert self.inform == "html" and self.outform == "pdf"
            Eprint.html_to_pdf(self.inpath, self.outpath)
            return 0
        self.convert(webstract)
        return 0

    def check_conversion(self) -> None:
        format_stages = {
            'jats': 0,
            'json': 1,
            'html': 2,
            'html+pdf': 2,
            'pdf': 2,
        }
        source_stage = format_stages[self.inform]
        target_stage = format_stages[self.outform]
        if source_stage > target_stage:
            msg = (
                "Conversion direction must be jats -> json -> (html|html+pdf|pdf)"
            )
            self.parser.error(msg)
        if self.inpath == self.outpath:
            self.parser.error(f"Output path must not equal input path: {self.inpath}")

    def just_copy(self) -> bool:
        if self.inform == self.outform:
            if self.inform not in ["jats", "json"]:
                if self.inpath.is_dir():
                    copytree_nostat(self.inpath, self.outpath)
                else:
                    shutil.copy(self.inpath, self.outpath)
                return True
        return False

    def check_weasyprint(self) -> None:
        try:
            importlib.import_module("weasyprint")
        except ImportError:
            self.parser.error("weasyprint must be installed to write pdf")

    def load_webstract(self) -> Webstract | None:
        if self.inform == "jats":
            from epijats.jats import webstract_from_jats
            return webstract_from_jats(self.inpath)
        elif self.inform == "json":
            return Webstract.load_json(self.inpath)
        return None

    def convert(self, webstract: Webstract) -> None:
        if self.outform == "json":
            webstract.dump_json(self.outpath)
        else:
            assert self.outform in ["html", "html+pdf", "pdf"]
            with tempfile.TemporaryDirectory() as tempdir:
                if self.outform == "html+pdf":
                    self.config.show_pdf_icon = True
                eprint = Eprint(webstract, Path(tempdir) / "html", self.config)
                if self.outform == "html":
                    eprint.make_html_dir(self.outpath)
                else:
                    self.check_weasyprint()
                    enable_weasyprint_logging()
                    if self.outform == "html+pdf":
                        eprint.make_html_and_pdf(
                            self.outpath,
                            self.outpath / "article.pdf"
                        )
                    elif self.outform == "pdf":
                        eprint.make_pdf(self.outpath)


def main(args: Any = None) -> int:
    return Main(args).run()


if __name__ == "__main__":
    exit(main())
