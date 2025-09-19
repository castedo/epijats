from __future__ import annotations

from typing import TYPE_CHECKING

from .. import baseprint as bp
from .. import condition as fc
from ..tree import (
    DataElement,
    Element,
    EmptyElement,
    MarkupElement,
    MixedContent,
    StartTag,
)

from . import kit
from .content import ArrayContentSession
from .tree import (
    DataElementModel,
    EmptyElementModel,
    TextElementModel,
    parse_mixed_content,
)
from .kit import Log, Model, Sink

if TYPE_CHECKING:
    from ..xml import XmlElement


def minimally_formatted_text_model(content: Model[Element]) -> Model[Element]:
    ret = kit.UnionModel[Element]()
    ret |= TextElementModel('b', content, jats_tag='bold')
    ret |= TextElementModel('i', content, jats_tag='italic')
    ret |= TextElementModel('sub', content)
    ret |= TextElementModel('sup', content)
    return ret


def blockquote_model(p_elements: Model[Element]) -> Model[Element]:
    """<disp-quote> Quote, Displayed
    Like HTML <blockquote>.

    https://jats.nlm.nih.gov/archiving/tag-library/1.4/element/disp-quote.html
    """
    p = TextElementModel('p', p_elements)
    return DataElementModel('blockquote', p, jats_tag='disp-quote')


class BreakModel(kit.LoadModel[Element]):
    def match(self, xe: XmlElement) -> bool:
        return xe.tag in ['br', 'break']

    def load(self, log: Log, e: XmlElement) -> Element | None:
        return EmptyElement('br')


def break_model() -> Model[Element]:
    """<break> Line Break
    Like HTML <br>.

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/break.html
    """
    return BreakModel()


def formatted_text_model(content: Model[Element]) -> Model[Element]:
    ret = kit.UnionModel[Element]()
    ret |= minimally_formatted_text_model(content)
    ret |= TextElementModel('tt', content, jats_tag='monospace')
    return ret


class JatsExtLinkModel(kit.TagModelBase[Element]):
    def __init__(self, content_model: Model[Element]):
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
            ret = bp.ExternalHyperlink(href)
            parse_mixed_content(log, e, self.content_model, ret.content)
            return ret


class HtmlExtLinkModel(kit.TagModelBase[Element]):
    def __init__(self, content_model: Model[Element]):
        super().__init__(StartTag('a', {'rel': 'external'}))
        self.content_model = content_model

    def load(self, log: Log, xe: XmlElement) -> Element | None:
        kit.check_no_attrib(log, xe, ['rel', 'href'])
        href = xe.attrib.get('href')
        if href is None:
            log(fc.MissingAttribute.issue(xe, 'href'))
            return None
        elif not href.startswith('https:') and not href.startswith('http:'):
            log(fc.InvalidAttributeValue.issue(xe, 'href', href))
            return None
        else:
            ret = bp.ExternalHyperlink(href)
            parse_mixed_content(log, xe, self.content_model, ret.content)
            return ret


def ext_link_model(content_model: Model[Element]) -> Model[Element]:
    return JatsExtLinkModel(content_model) | HtmlExtLinkModel(content_model)


class PendingParagraph:
    def __init__(self, dest: Sink[Element]):
        self.dest = dest
        self._pending: MarkupElement | None = None

    def close(self) -> None:
        if self._pending is not None and not self._pending.content.blank():
            self.dest(self._pending)
            self._pending = None

    @property
    def content(self) -> MixedContent:
        if self._pending is None:
            self._pending = MarkupElement('p')
        return self._pending.content


class HtmlParagraphModel(Model[Element]):
    def __init__(
        self,
        hypertext_model: Model[Element],
        non_p_child_model: Model[Element] | None,
    ):
        self.hypertext_model = hypertext_model
        self.non_p_child_model = non_p_child_model

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'p'

    def parse(self, log: Log, xe: XmlElement, dest: Sink[Element]) -> bool:
        if xe.tag != 'p':
            return False
        # ignore JATS <p specific-use> attribute from BpDF ed.1
        kit.check_no_attrib(log, xe, ['specific-use'])
        paragraph_dest = PendingParagraph(dest)
        if xe.text:
            paragraph_dest.content.append_text(xe.text)
        for s in xe:
            if self.non_p_child_model and self.non_p_child_model.match(s):
                paragraph_dest.close()
                self.non_p_child_model.parse(log, s, dest)
                if s.tail and s.tail.strip():
                    paragraph_dest.content.append_text(s.tail)
            else:
                content_dest = paragraph_dest.content
                if self.hypertext_model.match(s):
                    self.hypertext_model.parse(log, s, content_dest.append)
                else:
                    log(fc.UnsupportedElement.issue(s))
                    parse_mixed_content(log, s, self.hypertext_model, content_dest)
                    content_dest.append_text(s.tail)
        paragraph_dest.close()
        if xe.tail:
            log(fc.IgnoredTail.issue(xe))
        return True


class ListModel(kit.LoadModel[Element]):
    def __init__(self, block_model: Model[Element]):
        self._list_content = DataElementModel('li', block_model, jats_tag='list-item')

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
        sess = ArrayContentSession(log)
        sess.bind(self._list_content, ret.append)
        sess.parse_content(xe)
        return ret


def def_term_model(term_text: Model[Element]) -> Model[Element]:
    """<term> Definition List: Term

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/term.html
    """
    return TextElementModel('dt', term_text, jats_tag='term')


def def_def_model(def_child: Model[Element]) -> Model[Element]:
    """<def> Definition List: Definition

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/def.html
    """
    return DataElementModel('dd', def_child, jats_tag='def')


def def_item_model(term_text: Model[Element], def_child: Model[Element]) -> Model[Element]:
    """<def-item> Definition List: Definition Item

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/def-item.html
    """
    content_model = def_term_model(term_text) | def_def_model(def_child)
    return DataElementModel('div', content_model, jats_tag='def-item')


def def_list_model(
    hypertext_model: Model[Element], block_model: Model[Element]
) -> Model[Element]:
    content_model = def_item_model(hypertext_model, block_model)
    return DataElementModel('dl', content_model, jats_tag='def-list')


class TableCellModel(kit.TagModelBase[Element]):
    def __init__(self, content_model: Model[Element], *, header: bool):
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


def table_wrap_model(p_elements: Model[Element]) -> Model[Element]:
    col = EmptyElementModel('col', attrib={'span', 'width'})
    colgroup = DataElementModel('colgroup', col, optional_attrib={'span', 'width'})
    br = break_model()
    th = TableCellModel(p_elements | br, header=True)
    td = TableCellModel(p_elements | br, header=False)
    tr = DataElementModel('tr', th | td)
    thead = DataElementModel('thead', tr)
    tbody = DataElementModel('tbody', tr)
    table = DataElementModel(
        'table', colgroup | thead | tbody, optional_attrib={'frame', 'rules'}
    )
    return DataElementModel('table-wrap', table)
