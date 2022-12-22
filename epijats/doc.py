class DocLoader:
    def __init__(self, cache, eprinter_config=None):
        self.cache = cache
        self.eprinter_config = eprinter_config

    def __call__(self, edition):
        work_path = self.cache / "arc" / str(edition.dsi)
        if not work_path.exists():
            edition.work_copy(work_path)
        if work_path.is_dir():
            from .jats import JatsBaseprint

            subcache = self.cache / "epijats" / str(edition.dsi) / "pandoc"
            ret = JatsBaseprint(work_path, subcache, self.eprinter_config.pandoc_opts)
        else:
            from .pdf import PdfDocument

            ret = PdfDocument(work_path)
        return ret

    @staticmethod
    def is_jats(obj):
        from .jats import JatsBaseprint

        return isinstance(obj, JatsBaseprint)

    @staticmethod
    def is_pdf(obj):
        from .pdf import PdfDocument

        return isinstance(obj, PdfDocument)
