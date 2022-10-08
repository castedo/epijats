from elifetools import parseJATS
from elifetools.utils import node_text


def meta_article_id_text(soup, pub_id_type):
    return node_text(meta_article_id(soup, pub_id_type))


from elifetools import rawJATS
from elifetools.utils import first

# copied from elife feature branch
def meta_article_id(soup, pub_id_type):
    tags = rawJATS.article_id(soup, pub_id_type)
    # the first article-id tag whose parent is article-meta
    return first([tag for tag in tags if tag.parent.name == "article-meta"])
