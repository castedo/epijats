import pikepdf

# standard library
import html
from datetime import datetime


class PdfDocument:
    def __init__(self, src_path):
        pdf = pikepdf.open(src_path)
        title = pdf.open_metadata().get("dc:title")
        self.title_html = html.escape(title) if title else None
        md = pdf.docinfo[pikepdf.Name("/ModDate")]
        self.date = datetime.strptime(str(md)[2:10], "%Y%m%d").date()
