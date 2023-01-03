from .webstract import Webstract

import pikepdf

# standard library
import html
from datetime import datetime
from pathlib import Path


class PdfDocument:
    def __init__(self, src_path):
        pdf = pikepdf.open(src_path)
        title = pdf.open_metadata().get("dc:title")
        self.title_html = html.escape(title) if title else None
        md = pdf.docinfo[pikepdf.Name("/ModDate")]
        self.date = datetime.strptime(str(md)[2:10], "%Y%m%d").date()
        self.abstract_html = None
        self.body_html = None
        #TODO: extract author and set authors/contributors
        self.webstract = Webstract(dict(source=Path(src_path)))
        if self.date:
            self.webstract['date'] = self.date
        if self.title_html:
            self.webstract['title'] = self.title_html
