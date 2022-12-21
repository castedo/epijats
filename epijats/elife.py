from elifetools import parseJATS
from elifetools.utils import node_text
from elifetools.rawJATS import meta_article_id


def meta_article_id_text(soup, pub_id_type):
    return node_text(meta_article_id(soup, pub_id_type))
