
class JatsVars:

    def __init__(self, jats):
        self.jats = jats

    @property
    def title(self):
        return self.jats.title_html

    @property
    def date(self):
        return self.jats.date

    @property
    def authors(self):
        return self.jats.authors

    @property
    def abstract(self):
        return self.jats.abstract_html

    @property
    def body(self):
        return self.jats.body_html

    @property
    def hexhash(self):
        return self.jats.git_hash

    @property
    def uri(self):
        return "swh:1:cnt:" + self.jats.git_hash

