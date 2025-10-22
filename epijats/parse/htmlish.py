from __future__ import annotations

from typing import TYPE_CHECKING

from .. import dom
from .. import condition as fc
from ..elements import Paragraph
from ..tree import (
    DataElement,
    Element,
    HtmlVoidElement,
    Inline,
    MarkupElement,
    StartTag,
)

from . import kit
from .content import (
    ArrayContentMold,
    DataContentMold,
    MixedContentMold,
    PendingMarkupBlock,
    parse_array_content,
    parse_mixed_content,
)
from .tree import (
    EmptyElementModel,
    InlineModel,
    ItemModel,
    TagMold,
)
from .kit import Log, Model, Sink

if TYPE_CHECKING:
    from ..typeshed import XmlElement


def markup_model(
    tag: str, child_model: Model[Inline], *, jats_tag: str | None = None
) -> Model[Inline]:
    tm = TagMold(tag, jats_tag=jats_tag)
    return InlineModel(tm, MixedContentMold(child_model))


def minimally_formatted_text_model(content: Model[Inline]) -> Model[Inline]:
    ret = kit.UnionModel[Inline]()
    ret |= markup_model('b', content, jats_tag='bold')
    ret |= markup_model('i', content, jats_tag='italic')
    ret |= markup_model('sub', content)
    ret |= markup_model('sup', content)
    return ret


def preformat_model(hypertext: Model[Inline]) -> Model[Element]:
    tm = TagMold('pre', jats_tag='preformat')
    return ItemModel(tm, MixedContentMold(hypertext))


def blockquote_model(roll_content_mold: ArrayContentMold) -> Model[Element]:
    """<disp-quote> Quote, Displayed
    Like HTML <blockquote>.

    https://jats.nlm.nih.gov/archiving/tag-library/1.4/element/disp-quote.html
    """
    tm = TagMold('blockquote', jats_tag='disp-quote')
    return ItemModel(tm, roll_content_mold)


class BreakModel(kit.LoadModel[Inline]):
    def match(self, xe: XmlElement) -> bool:
        return xe.tag in ['br', 'break']

    def load(self, log: Log, e: XmlElement) -> Inline | None:
        return HtmlVoidElement('br')


def break_model() -> Model[Inline]:
    """<break> Line Break
    Like HTML <br>.

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/break.html
    """
    return BreakModel()


def code_model(hypertext: Model[Inline]) -> Model[Inline]:
    return InlineModel(TagMold('code'), MixedContentMold(hypertext))


def formatted_text_model(content: Model[Inline]) -> Model[Inline]:
    ret = kit.UnionModel[Inline]()
    ret |= minimally_formatted_text_model(content)
    ret |= markup_model('tt', content, jats_tag='monospace')
    return ret


def hypotext_model() -> Model[Inline]:
    # Corresponds to {HYPOTEXT} in BpDF spec ed.2
    # https://perm.pub/DPRkAz3vwSj85mBCgG49DeyndaE/2
    ret = kit.UnionModel[Inline]()
    ret |= formatted_text_model(ret)
    return ret


class JatsExtLinkModel(kit.TagModelBase[Inline]):
    def __init__(self, content_model: Model[Inline]):
        super().__init__('ext-link')
        self.content_model = content_model

    def load(self, log: Log, e: XmlElement) -> Inline | None:
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
            ret = dom.ExternalHyperlink(href)
            parse_mixed_content(log, e, self.content_model, ret.content)
            return ret


class HtmlExtLinkModel(kit.TagModelBase[Inline]):
    def __init__(self, content_model: Model[Inline]):
        super().__init__(StartTag('a', {'rel': 'external'}))
        self.content_model = content_model

    def load(self, log: Log, xe: XmlElement) -> Inline | None:
        kit.check_no_attrib(log, xe, ['rel', 'href'])
        href = xe.attrib.get('href')
        if href is None:
            log(fc.MissingAttribute.issue(xe, 'href'))
            return None
        elif not href.startswith('https:') and not href.startswith('http:'):
            log(fc.InvalidAttributeValue.issue(xe, 'href', href))
            return None
        else:
            ret = dom.ExternalHyperlink(href)
            parse_mixed_content(log, xe, self.content_model, ret.content)
            return ret


def ext_link_model(content_model: Model[Inline]) -> Model[Inline]:
    return JatsExtLinkModel(content_model) | HtmlExtLinkModel(content_model)


class HtmlParagraphModel(Model[Element]):
    def __init__(self, hypertext: Model[Inline], block: Model[Element]):
        self.inline_model = hypertext
        self.block_model = block

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'p'

    def parse(self, log: Log, xe: XmlElement, dest: Sink[Element]) -> bool:
        # ignore JATS <p specific-use> attribute from BpDF ed.1
        kit.check_no_attrib(log, xe, ['specific-use'])
        pending = PendingMarkupBlock(dest, Paragraph())
        autoclosed = False
        if xe.text:
            pending.content.append_text(xe.text)
        for s in xe:
            if self.inline_model.match(s):
                self.inline_model.parse(log, s, pending.content.append)
            elif self.block_model.match(s):
                pending.close()
                autoclosed = True
                log(fc.BlockElementInPhrasingContent.issue(s))
                self.block_model.parse(log, s, dest)
                if s.tail and s.tail.strip():
                    pending.content.append_text(s.tail)
            else:
                log(fc.UnsupportedElement.issue(s))
                parse_mixed_content(log, s, self.inline_model, pending.content)
                pending.content.append_text(s.tail)
        if not pending.close() or autoclosed:
            dest(Paragraph())
        if xe.tail:
            log(fc.IgnoredTail.issue(xe))
        return True


class ListModel(kit.LoadModel[Element]):
    def __init__(self, item_content_mold: ArrayContentMold):
        tm = TagMold('li', jats_tag='list-item')
        self._list_content = ItemModel(tm, item_content_mold)

    def match(self, xe: XmlElement) -> bool:
        return xe.tag in ['ul', 'ol', 'list']

    def load(self, log: Log, xe: XmlElement) -> Element | None:
        if xe.tag == 'list':
            kit.check_no_attrib(log, xe, ['list-type'])
            list_type = xe.attrib.get('list-type')
            tag = 'ol' if list_type == 'order' else 'ul'
        else:
            kit.check_no_attrib(log, xe)
            tag = str(xe.tag)
        ret = DataElement(tag)
        parser = self._list_content.bound_parser(log, ret.content.append)
        parse_array_content(log, xe, parser)
        return ret


def def_term_model(term_text: Model[Inline]) -> Model[Element]:
    """<term> Definition List: Term

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/term.html
    """
    tm = TagMold('dt', jats_tag='term')
    return ItemModel(tm, MixedContentMold(term_text))


def def_def_model(def_content: ArrayContentMold) -> Model[Element]:
    """<def> Definition List: Definition

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/def.html
    """
    tm = TagMold('dd', jats_tag='def')
    return ItemModel(tm, def_content)


def def_item_model(
    term_text: Model[Inline], def_content: ArrayContentMold
) -> Model[Element]:
    """<def-item> Definition List: Definition Item

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/def-item.html
    """
    tm = TagMold('div', jats_tag='def-item')
    child_model = def_term_model(term_text) | def_def_model(def_content)
    return ItemModel(tm, DataContentMold(child_model))


def def_list_model(
    hypertext_model: Model[Inline], roll_content: ArrayContentMold
) -> Model[Element]:
    tm = TagMold('dl', jats_tag='def-list')
    child_model = def_item_model(hypertext_model, roll_content)
    return ItemModel(tm, DataContentMold(child_model))


class TableCellModel(kit.TagModelBase[Element]):
    def __init__(self, content_model: Model[Inline], *, header: bool):
        super().__init__('th' if header else 'td')
        self.content_model = content_model
        self._ok_attrib_keys = {'align', 'colspan', 'rowspan'}

    def load(self, log: Log, e: XmlElement) -> Element | None:
        align_attribs = {'left', 'right', 'center', 'justify', None}
        kit.confirm_attrib_value(log, e, 'align', align_attribs)
        ret = MarkupElement(self.tag)
        kit.copy_ok_attrib_values(log, e, self._ok_attrib_keys, ret.xml.attrib)
        parse_mixed_content(log, e, self.content_model, ret.content)
        if ret.content.empty():
            ret.content.text = ' '
        return ret


def data_element_model(tag: str, child_model: Model[Element]) -> Model[Element]:
    return ItemModel(TagMold(tag), DataContentMold(child_model))


def col_group_model() -> Model[Element]:
    col = EmptyElementModel('col', attrib={'span', 'width'}, is_html_tag=True)
    tm = TagMold('colgroup', optional_attrib={'span', 'width'})
    return ItemModel(tm, DataContentMold(col))


def table_wrap_model(text: Model[Inline]) -> Model[Element]:
    br = break_model()
    th = TableCellModel(text | br, header=True)
    td = TableCellModel(text | br, header=False)
    tr = data_element_model('tr', th | td)
    thead = data_element_model('thead', tr)
    tbody = data_element_model('tbody', tr)
    table_mold = TagMold('table', optional_attrib={'frame', 'rules'})
    content_parser = DataContentMold(col_group_model() | thead | tbody)
    table = ItemModel(table_mold, content_parser)
    return data_element_model('table-wrap', table)
