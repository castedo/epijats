import pikepdf
from .util import git_hash_object

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
        self.abstract_html = None
        self.body_html = None
        self.git_hash = git_hash_object(src_path)
        #TODO: extract author and set authors/contributors
