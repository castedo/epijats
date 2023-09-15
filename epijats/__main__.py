from epijats import Eprint, EprinterConfig, Webstract
from epijats.util import copytree_nostat

# std lib
import argparse, importlib, logging, os, shutil, subprocess, sys, tempfile
from pathlib import Path


def enable_weasyprint_logging():
    from weasyprint import LOGGER

    LOGGER.setLevel(logging.INFO)
    LOGGER.addHandler(logging.StreamHandler())


class Main:
    def __init__(self, cmd_line_args=None):
        self.parser = argparse.ArgumentParser(description="Eprint JATS")
        self.parser.add_argument("inpath", type=Path, help="input directory/path")
        self.parser.add_argument("outpath", type=Path, help="output directory/path")
        self.parser.add_argument(
            "--from",
            dest="inform",
            choices=["jats", "json", "yaml", "jsoml", "html"],
            default="jats",
            help="format of source",
        )
        self.parser.add_argument(
            "--to",
            dest="outform",
            choices=["json", "yaml", "jsoml", "html", "html+pdf", "pdf"],
            default="pdf",
            help="format of target",
        )
        self.parser.add_argument(
            "--no-web-fonts",
            default=False,
            action="store_true",
            help="Do not use online web fonts",
        )
        self.parser.parse_args(cmd_line_args, self)

        self.config = EprinterConfig(dsi_base_url="https://perm.pub")
        self.config.embed_web_fonts = not self.no_web_fonts

    def run(self):
        self.check_conversion_order()
        if self.just_copy():
            return

        webstract = self.load_webstract()
        if webstract is None:
            assert self.inform == "html" and self.outform == "pdf"
            Eprint.html_to_pdf(self.inpath, self.outpath)
            return
        self.convert(webstract)

    def check_conversion_order(self):
        format_stages = {
            'jats': 0,
            'json': 1,
            'yaml': 1,
            'jsoml': 1,
            'html': 2,
            'html+pdf': 2,
            'pdf': 2,
        }
        source_stage = format_stages[self.inform]
        target_stage = format_stages[self.outform]
        if source_stage > target_stage:
            msg = (
                "Conversion direction must be jats -> (json|yaml|jsoml) -> (html|html+pdf|pdf)"
            )
            self.parser.error(msg)

    def just_copy(self):
        if self.inform == self.outform:
            if self.inform not in ["json", "yaml", "jsoml"]:
                if self.inpath.is_dir():
                    copytree_nostat(self.inpath, self.outpath)
                else:
                    shutil.copy(self.inpath, self.outpath)
                return True
        return False

    def check_imports(self, import_names, act):
        form = self.inform if act == "read" else self.outform
        for name in import_names:
            try:
                importlib.import_module(name)
            except ImportError as e:
                msg = f"{e.name} must be installed to {act} {form}"
                self.parser.error(msg)

    def load_webstract(self):
        if self.inform == "jats":
            self.check_imports(["elifetools", "jsoml"], "read")
            from epijats.jats import webstract_from_jats
            return webstract_from_jats(self.inpath, self.config.pandoc_opts)
        elif self.inform == "json":
            return Webstract.load_json(self.inpath)
        elif self.inform == "yaml":
            self.check_imports(["ruamel.yaml"], "read")
            return Webstract.load_yaml(self.inpath)
        elif self.inform == "jsoml":
            self.check_imports(["jsoml"], "read")
            return Webstract.load_xml(self.inpath)
        return None

    def convert(self, webstract):
        if self.outform == "json":
            webstract.dump_json(self.outpath)
        elif self.outform == "yaml":
            self.check_imports(["ruamel.yaml"], "write")
            webstract.dump_yaml(self.outpath)
        elif self.outform == "jsoml":
            self.check_imports(["jsoml"], "write")
            webstract.dump_xml(self.outpath)
        else:
            assert self.outform in ["html", "html+pdf", "pdf"]
            self.check_imports(["jinja2"], "write")
            with tempfile.TemporaryDirectory() as tempdir:
                if self.outform == "html+pdf":
                    self.config.show_pdf_icon = True
                eprint = Eprint(webstract, Path(tempdir) / "html", self.config)
                if self.outform == "html":
                    eprint.make_html_dir(self.outpath)
                else:
                    self.check_imports(["weasyprint"], "write")
                    enable_weasyprint_logging()
                    if self.outform == "html+pdf":
                        eprint.make_html_and_pdf(
                            self.outpath,
                            self.outpath / "article.pdf"
                        )
                    elif self.outform == "pdf":
                        eprint.make_pdf(self.outpath)


def main(args=None):
    return Main(args).run()

if __name__ == "__main__":
    exit(main())
