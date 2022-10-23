class DocLoader:
    def __init__(self, cache, eprinter_config=None):
        self.cache = cache
        self.eprinter_config = eprinter_config

    def __call__(self, src_path, dsi):
        ret = None
        if src_path.is_dir():
            xml = src_path / "article.xml"
            subcache = self.cache / str(dsi)
            ret = JatsEprint(xml, subcache, self.eprinter_config)
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


from .jats import EprinterConfig, JatsEprint
