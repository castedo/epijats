from .webstract import Webstract

import pikepdf

# standard library
import html
from datetime import datetime
from pathlib import Path


def is_pdf(src_path):
    src_path = Path(src_path)
    if src_path.is_dir():
        return False
    try:
        pikepdf.open(src_path).close()
    except pikepdf.PdfError:
        return False
    return True


def webstract_from_pdf(src_path):
    ret = Webstract(dict(source=Path(src_path)))
    with pikepdf.open(src_path) as pdf:
        title = pdf.open_metadata().get("dc:title")
        if title:
            ret['title'] = html.escape(title)
        md = pdf.docinfo[pikepdf.Name("/ModDate")]
        ret['date'] = datetime.strptime(str(md)[2:10], "%Y%m%d").date()
        #TODO: extract author and set authors/contributors
    return ret
