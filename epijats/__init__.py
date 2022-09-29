from .jats import EprinterConfig, JatsEprinter

# popular packages
import pikepdf

# standard library
import html
from datetime import datetime


class PdfDocument:
    def __init__(self, src_path):
        pdf = pikepdf.open(src_path)
        title = pdf.open_metadata().get('dc:title')
        self.title_html = html.escape(title) if title else None
        md = pdf.docinfo[pikepdf.Name("/ModDate")]
        self.date = datetime.strptime(str(md)[2:10], "%Y%m%d").date()
        self.is_jats = False


class DocLoader:
    def __init__(self, eprinter_config=None):
        self.eprinter_config = eprinter_config if eprinter_config else EprinterConfig()

    def __call__(self, src_path, cache_dir):
        ret = None
        if src_path.is_dir():
            xml = src_path / "article.xml"
            ret = JatsEprinter(self.eprinter_config, xml, cache_dir)
        else:
            ret = PdfDocument(src_path)
        return ret
