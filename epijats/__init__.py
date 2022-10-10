from .jats import EprinterConfig, JatsEprint


class DocLoader:
    def __init__(self, eprinter_config=None):
        self.eprinter_config = eprinter_config if eprinter_config else EprinterConfig()

    def __call__(self, src_path, cache_dir):
        ret = None
        if src_path.is_dir():
            xml = src_path / "article.xml"
            ret = JatsEprint(self.eprinter_config, xml, cache_dir)
        else:
            from .pdf import PdfDocument

            ret = PdfDocument(src_path)
        return ret

    @staticmethod
    def is_jats(obj):
        return isinstance(obj, JatsEprint)

    @staticmethod
    def is_pdf(obj):
        from .pdf import PdfDocument

        return isinstance(obj, PdfDocument)
