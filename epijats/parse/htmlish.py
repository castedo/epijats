from __future__ import annotations

from lxml import etree

from .. import baseprint as bp
from .. import condition as fc
from ..tree import Element, MarkupElement

from . import kit
from .tree import (
    DataElementModel,
    EModel,
    TextElementModel,
    EmptyElementModel,
    TagElementModelBase,
    parse_mixed_content,
)
from .kit import IssueCallback


def disp_quote_model(p_elements: EModel) -> EModel:
    """<disp-quote> Quote, Displayed
    Like HTML <blockquote>.

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/disp-quote.html
    """
    p = TextElementModel({'p'}, p_elements)
    return DataElementModel('disp-quote', p)


def break_model() -> EModel:
    """<break> Line Break
    Like HTML <br>.

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/break.html
    """
    return EmptyElementModel('break')


class ItalicModel(TextElementModel):
    def __init__(self, content_model: EModel):
        super().__init__({'italic'}, content_model)

    def check(self, log: IssueCallback, e: etree._Element) -> None:
        kit.check_no_attrib(log, e, ('toggle',))
        kit.confirm_attrib_value(log, e, 'toggle', ('yes', None))


def formatted_text_model(content: EModel) -> EModel:
    simple_tags = {'bold', 'monospace', 'sub', 'sup'}
    return ItalicModel(content) | TextElementModel(simple_tags, content)


class ExtLinkModel(TagElementModelBase):
    def __init__(self, content_model: EModel):
        super().__init__('ext-link')
        self.content_model = content_model

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        link_type = e.attrib.get("ext-link-type")
        if link_type and link_type != "uri":
            log(fc.UnsupportedAttributeValue.issue(e, "ext-link-type", link_type))
            return None
        k_href = "{http://www.w3.org/1999/xlink}href"
        href = e.attrib.get(k_href)
        kit.check_no_attrib(log, e, ["ext-link-type", k_href])
        if href is None:
            log(fc.MissingAttribute.issue(e, k_href))
            return None
        else:
            ret = bp.Hyperlink(href)
            parse_mixed_content(log, e, self.content_model, ret.content)
            return ret


class ListModel(TagElementModelBase):
    def __init__(self, p_elements_model: EModel):
        super().__init__('list')
        # https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/list-item-model.html
        # %list-item-model
        p = TextElementModel({'p'}, p_elements_model)
        list_item_content = p | self
        self._list_content_model = DataElementModel(
            'list-item', list_item_content
        )

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        kit.check_no_attrib(log, e, ['list-type'])
        list_type = kit.get_enum_value(log, e, 'list-type', bp.ListTypeCode)
        ret = bp.List(list_type)
        self._list_content_model.bind(log, ret.append).parse_array_content(e)
        return ret


def def_term_model(term_text: EModel) -> EModel:
    """<term> Definition List: Term

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/term.html
    """
    return TextElementModel({'term'}, term_text)


def def_def_model(p_elements: EModel) -> EModel:
    """<def> Definition List: Definition

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/def.html
    """
    p = TextElementModel({'p'}, p_elements)
    return DataElementModel('def', p)


def def_item_model(term_text: EModel, p_elements: EModel) -> EModel:
    """<def-item> Definition List: Definition Item

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/def-item.html
    """
    content_model = def_term_model(term_text) | def_def_model(p_elements)
    return DataElementModel('def-item', content_model)


def def_list_model(term_text: EModel, p_elements: EModel) -> EModel:
    """<def-list> Definition List

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/def-list.html
    """
    content_model = def_item_model(term_text, p_elements)
    return DataElementModel('def-list', content_model)
