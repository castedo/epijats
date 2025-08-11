from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

from .. import baseprint as bp
from .. import condition as fc
from ..tree import Element, MarkupElement

from . import kit
from .content import ArrayContentSession
from .tree import (
    DataElementModel,
    TextElementModel,
    EmptyElementModel,
    parse_mixed_content,
)
from .kit import Log, Model

if TYPE_CHECKING:
    from ..xml import XmlElement


EModel: TypeAlias = Model[Element]


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

    def check(self, log: Log, e: XmlElement) -> None:
        kit.check_no_attrib(log, e, ('toggle',))
        kit.confirm_attrib_value(log, e, 'toggle', ('yes', None))


def formatted_text_model(content: EModel) -> EModel:
    simple_tags = {'bold', 'monospace', 'sub', 'sup'}
    return ItalicModel(content) | TextElementModel(simple_tags, content)


class ExtLinkModel(kit.TagModelBase[Element]):
    def __init__(self, content_model: EModel):
        super().__init__('ext-link')
        self.content_model = content_model

    def load(self, log: Log, e: XmlElement) -> Element | None:
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


class HtmlParagraphModel(TextElementModel):
    def __init__(self, hypertext_model: EModel, block_model: EModel):
        super().__init__({'p'}, hypertext_model | block_model)


class ListModel(kit.TagModelBase[Element]):
    def __init__(self, p_elements_model: EModel):
        super().__init__('list')
        # https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/pe/list-item-model.html
        # %list-item-model
        p = TextElementModel({'p'}, p_elements_model)
        list_item_content = p | self
        self._list_content_model = DataElementModel('list-item', list_item_content)

    def load(self, log: Log, xe: XmlElement) -> Element | None:
        kit.check_no_attrib(log, xe, ['list-type'])
        list_type = kit.get_enum_value(log, xe, 'list-type', bp.ListTypeCode)
        ret = bp.List(list_type)
        sess = ArrayContentSession(log)
        sess.bind(self._list_content_model, ret.append)
        sess.parse_content(xe)
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


class TableCellModel(kit.TagModelBase[Element]):
    def __init__(self, content_model: EModel, *, header: bool):
        super().__init__('th' if header else 'td')
        self.content_model = content_model
        self._ok_attrib_keys = {'align', 'colspan', 'rowspan'}

    def load(self, log: Log, e: XmlElement) -> Element | None:
        align_attribs = {'left', 'right', 'center', 'justify', None}
        kit.confirm_attrib_value(log, e, 'align', align_attribs)
        assert e.tag == self.tag
        if isinstance(e.tag, str):
            ret = MarkupElement(e.tag)
            kit.copy_ok_attrib_values(log, e, self._ok_attrib_keys, ret.xml.attrib)
        parse_mixed_content(log, e, self.content_model, ret.content)
        return ret


def table_wrap_model(p_elements: EModel) -> EModel:
    col = EmptyElementModel('col', attrib={'span', 'width'})
    colgroup = DataElementModel('colgroup', col, attrib={'span', 'width'})
    br = break_model()
    th = TableCellModel(p_elements | br, header=True)
    td = TableCellModel(p_elements | br, header=False)
    tr = DataElementModel('tr', th | td)
    thead = DataElementModel('thead', tr)
    tbody = DataElementModel('tbody', tr)
    table = DataElementModel(
        'table', colgroup | thead | tbody, attrib={'frame', 'rules'}
    )
    return DataElementModel('table-wrap', table)
