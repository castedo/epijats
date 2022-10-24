class DocLoader:
    def __init__(self, cache, eprinter_config=None):
        self.cache = cache
        self.eprinter_config = eprinter_config

    def __call__(self, edition):
        work_path = self.cache / "arc" / str(edition.dsi)
        if not work_path.exists():
            edition.work_copy(work_path)
        if work_path.is_dir():
            from .jats import JatsEprint

            xml = work_path / "article.xml"
            subcache = self.cache / "epijats" / str(edition.dsi)
            ret = JatsEprint(xml, subcache, self.eprinter_config)
        else:
            from .pdf import PdfDocument

            ret = PdfDocument(work_path)
        return ret

    @staticmethod
    def is_jats(obj):
        from .jats import JatsEprint

        return isinstance(obj, JatsEprint)

    @staticmethod
    def is_pdf(obj):
        from .pdf import PdfDocument

        return isinstance(obj, PdfDocument)
