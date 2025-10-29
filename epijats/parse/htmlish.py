from __future__ import annotations

from typing import TYPE_CHECKING

from .. import dom
from .. import condition as fc
from ..tree import (
    DataElement,
    Element,
    Inline,
    MarkupElement,
    StartTag,
)

from . import kit
from .content import (
    ArrayContentModel,
    DataContentModel,
    MixedModel,
    PendingMarkupBlock,
    UnionMixedModel,
    parse_array_content,
)
from .tree import (
    BiformModel,
    EmptyElementModel,
    EmptyInlineModel,
    MixedParentElementModel,
    ItemModel,
    MarkupMixedModel,
    TagMold,
)
from .kit import Log, Model, Sink

if TYPE_CHECKING:
    from ..typeshed import XmlElement


def markup_model(
    tag: str, content: MixedModel, *, jats_tag: str | None = None
) -> MixedModel:
    tm = TagMold(tag, jats_tag=jats_tag)
    return MarkupMixedModel(tm, content)


def minimally_formatted_text_model(content: MixedModel) -> MixedModel:
    ret = UnionMixedModel()
    ret |= markup_model('b', content, jats_tag='bold')
    ret |= markup_model('i', content, jats_tag='italic')
    ret |= markup_model('sub', content)
    ret |= markup_model('sup', content)
    return ret


def preformat_model(hypertext: MixedModel) -> Model[Element]:
    tm = TagMold('pre', jats_tag='preformat')
    return MixedParentElementModel(tm, hypertext)


def blockquote_model(roll_content_mold: ArrayContentModel) -> Model[Element]:
    """<disp-quote> Quote, Displayed
    Like HTML <blockquote>.

    https://jats.nlm.nih.gov/archiving/tag-library/1.4/element/disp-quote.html
    """
    tm = TagMold('blockquote', jats_tag='disp-quote')
    return BiformModel(tm, roll_content_mold)


def break_model() -> MixedModel:
    """<break> Line Break
    Like HTML <br>.

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/break.html
    """

    return EmptyInlineModel(TagMold('br', jats_tag='break'), dom.LineBreak)


def code_model(hypertext: MixedModel) -> MixedModel:
    return markup_model('code', hypertext)


def formatted_text_model(content: MixedModel) -> MixedModel:
    ret = UnionMixedModel()
    ret |= minimally_formatted_text_model(content)
    ret |= markup_model('tt', content, jats_tag='monospace')
    return ret


def hypotext_model() -> MixedModel:
    # Corresponds to {HYPOTEXT} in BpDF spec ed.2
    # https://perm.pub/DPRkAz3vwSj85mBCgG49DeyndaE/2
    ret = UnionMixedModel()
    ret |= formatted_text_model(ret)
    return ret


class JatsExtLinkModel(MixedModel):
    def __init__(self, content_model: MixedModel):
        self.content_model = content_model

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'ext-link'

    def parse(self, log: Log, e: XmlElement, sink: Sink[str | Inline]) -> None:
        link_type = e.attrib.get("ext-link-type")
        if link_type and link_type != "uri":
            log(fc.UnsupportedAttributeValue.issue(e, "ext-link-type", link_type))
            raise ValueError
        k_href = "{http://www.w3.org/1999/xlink}href"
        href = e.attrib.get(k_href)
        kit.check_no_attrib(log, e, ["ext-link-type", k_href])
        if href is None:
            log(fc.MissingAttribute.issue(e, k_href))
            self.parse_content(log, e, sink)
        else:
            ret = dom.ExternalHyperlink(href)
            self.content_model.parse_content(log, e, ret.append)
            sink(ret)


class HtmlExtLinkModel(MixedModel):
    def __init__(self, content_model: MixedModel):
        self.stag = StartTag('a', {'rel': 'external'})
        self.content_model = content_model

    def match(self, xe: XmlElement) -> bool:
        return self.stag.issubset(xe)

    def parse(self, log: Log, xe: XmlElement, sink: Sink[str | Inline]) -> None:
        kit.check_no_attrib(log, xe, ['rel', 'href'])
        href = xe.attrib.get('href')
        if href is None:
            log(fc.MissingAttribute.issue(xe, 'href'))
        elif not href.startswith('https:') and not href.startswith('http:'):
            log(fc.InvalidAttributeValue.issue(xe, 'href', href))
        else:
            ret = dom.ExternalHyperlink(href)
            self.content_model.parse_content(log, xe, ret.append)
            sink(ret)


def ext_link_model(content_model: MixedModel) -> MixedModel:
    return JatsExtLinkModel(content_model) | HtmlExtLinkModel(content_model)


class HtmlParagraphModel(Model[Element]):
    def __init__(self, hypertext: MixedModel, block: Model[Element]):
        self.inline_model = hypertext
        self.block_model = block

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'p'

    def parse(self, log: Log, xe: XmlElement, sink: Sink[Element]) -> None:
        # ignore JATS <p specific-use> attribute from BpDF ed.1
        kit.check_no_attrib(log, xe, ['specific-use'])
        pending = PendingMarkupBlock(sink, dom.Paragraph())
        autoclosed = False
        if xe.text:
            pending.append(xe.text)
        for s in xe:
            if self.inline_model.match(s):
                self.inline_model.parse(log, s, pending.append)
            elif self.block_model.match(s):
                pending.close()
                autoclosed = True
                log(fc.BlockElementInPhrasingContent.issue(s))
                self.block_model.parse(log, s, sink)
                if s.tail and not s.tail.strip():
                    s.tail = None
            else:
                log(fc.UnsupportedElement.issue(s))
                self.inline_model.parse_content(log, s, pending.append)
            if s.tail:
                pending.append(s.tail)
        if not pending.close() or autoclosed:
            sink(dom.Paragraph(" "))
        if xe.tail:
            log(fc.IgnoredTail.issue(xe))


class ListModel(kit.LoadModelBase[Element]):
    def __init__(self, item_content_mold: ArrayContentModel):
        tm = TagMold('li', jats_tag='list-item')
        self._list_content = BiformModel(tm, item_content_mold)

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
        parse_array_content(log, xe, self._list_content, ret.append)
        return ret


def def_term_model(term_text: MixedModel) -> Model[Element]:
    """<term> Definition List: Term

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/term.html
    """
    tm = TagMold('dt', jats_tag='term')
    return MixedParentElementModel(tm, term_text)


def def_def_model(def_content: ArrayContentModel) -> Model[Element]:
    """<def> Definition List: Definition

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/def.html
    """
    tm = TagMold('dd', jats_tag='def')
    return BiformModel(tm, def_content)


def def_item_model(
    term_text: MixedModel, def_content: ArrayContentModel
) -> Model[Element]:
    """<def-item> Definition List: Definition Item

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/def-item.html
    """
    tm = TagMold('div', jats_tag='def-item')
    child_model = def_term_model(term_text) | def_def_model(def_content)
    return ItemModel(tm, DataContentModel(child_model))


def def_list_model(
    hypertext_model: MixedModel, roll_content: ArrayContentModel
) -> Model[Element]:
    tm = TagMold('dl', jats_tag='def-list')
    child_model = def_item_model(hypertext_model, roll_content)
    return ItemModel(tm, DataContentModel(child_model))


class TableCellModel(kit.LoadModelBase[Element]):
    def __init__(self, content_model: MixedModel, *, header: bool):
        self.tag = 'th' if header else 'td'
        self.content_model = content_model
        self._ok_attrib_keys = {'align', 'colspan', 'rowspan'}

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == self.tag

    def load(self, log: Log, e: XmlElement) -> Element | None:
        align_attribs = {'left', 'right', 'center', 'justify', None}
        kit.confirm_attrib_value(log, e, 'align', align_attribs)
        ret = MarkupElement(self.tag)
        kit.copy_ok_attrib_values(log, e, self._ok_attrib_keys, ret.xml.attrib)
        self.content_model.parse_content(log, e, ret.append)
        if ret.content.empty():
            ret.content.text = ' '
        return ret


def data_element_model(tag: str, child_model: Model[Element]) -> Model[Element]:
    return ItemModel(TagMold(tag), DataContentModel(child_model))


def col_group_model() -> Model[Element]:
    tm = TagMold('col', optional_attrib={'span', 'width'})
    col = EmptyElementModel(tm, dom.TableColumn)
    tm = TagMold('colgroup', optional_attrib={'span', 'width'})
    return ItemModel(tm, DataContentModel(col))


def table_wrap_model(text: MixedModel) -> Model[Element]:
    br = break_model()
    th = TableCellModel(text | br, header=True)
    td = TableCellModel(text | br, header=False)
    tr = data_element_model('tr', th | td)
    thead = data_element_model('thead', tr)
    tbody = data_element_model('tbody', tr)
    table_mold = TagMold('table', optional_attrib={'frame', 'rules'})
    content_parser = DataContentModel(col_group_model() | thead | tbody)
    table = ItemModel(table_mold, content_parser)
    return data_element_model('table-wrap', table)
