from __future__ import annotations

from typing import TYPE_CHECKING

from .. import dom
from .. import condition as fc
from ..tree import (
    Element,
    Parent,
    StartTag,
)

from . import kit
from .content import (
    ArrayContentModel,
    ArrayContentSession,
    ContentModel,
    DataContentModel,
    MixedModel,
    PendingMarkupBlock,
    UnionMixedModel,
)
from .tree import (
    ArrayParentModel,
    DataParentModel,
    EmptyElementModel,
    MixedParentModel,
    TagModel,
)
from .kit import Log, Model, Sink

if TYPE_CHECKING:
    from ..typeshed import XmlElement


def markup_model(
    tag: str | StartTag,
    content_model: ContentModel[str | Element],
    *,
    jats_name: str | None = None,
) -> Model[Parent[str | Element]]:
    tm = TagModel(dom.MarkupInline, tag=tag, jats_name=jats_name)
    return MixedParentModel(tm, content_model)


def minimally_formatted_text_model(content: MixedModel) -> MixedModel:
    ret = UnionMixedModel()
    ret |= markup_model('b', content, jats_name='bold')
    ret |= markup_model('i', content, jats_name='italic')
    ret |= markup_model('sub', content)
    ret |= markup_model('sup', content)
    return ret


def preformat_model(hypertext: MixedModel) -> Model[Element]:
    tm = TagModel(dom.Preformat, jats_name='preformat')
    return MixedParentModel(tm, hypertext)


def blockquote_model(roll_content_model: ArrayContentModel) -> Model[Element]:
    """<disp-quote> Quote, Displayed
    Like HTML <blockquote>.

    https://jats.nlm.nih.gov/archiving/tag-library/1.4/element/disp-quote.html
    """
    tm = TagModel(dom.BlockQuote, jats_name='disp-quote')
    return ArrayParentModel(tm, roll_content_model)


def break_model() -> Model[Element]:
    """<break> Line Break
    Like HTML <br>.

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/break.html
    """

    return EmptyElementModel(TagModel(dom.LineBreak, jats_name='break'))


def code_model(hypertext: MixedModel) -> Model[Element]:
    return markup_model('code', hypertext)


def formatted_text_model(content: MixedModel) -> MixedModel:
    ret = UnionMixedModel()
    ret |= minimally_formatted_text_model(content)
    ret |= markup_model('tt', content, jats_name='monospace')
    return ret


def hypotext_model() -> MixedModel:
    # Corresponds to {HYPOTEXT} in BpDF spec ed.2
    # https://perm.pub/DPRkAz3vwSj85mBCgG49DeyndaE/2
    ret = UnionMixedModel()
    ret |= formatted_text_model(ret)
    return ret


class ExtLinkModelBase(MixedModel):
    def __init__(self, content_model: MixedModel):
        self.content_model = content_model

    def parse_url(
        self, log: Log, xe: XmlElement, key: str, out: Sink[str | Element]
    ) -> bool:
        url = xe.attrib.get(key)
        if url is None:
            log(fc.MissingAttribute.issue(xe, key))
            # parse per model with hyperlinks (not within), to allow hyperlinks
            self.parse_content(log, xe, out)
        elif not url.startswith('https:') and not url.startswith('http:'):
            log(fc.InvalidAttributeValue.issue(xe, key, url))
            self.content_model.parse_content(log, xe, out)
        else:
            ret = dom.ExternalHyperlink(url)
            self.content_model.parse_content(log, xe, ret.append)
            out(ret)
        return True


class JatsExtLinkModel(ExtLinkModelBase):
    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'ext-link'

    def parse(self, log: Log, e: XmlElement, out: Sink[str | Element]) -> bool:
        link_type = e.attrib.get("ext-link-type")
        if link_type and link_type != "uri":
            log(fc.UnsupportedAttributeValue.issue(e, "ext-link-type", link_type))
            return False
        k_href = "{http://www.w3.org/1999/xlink}href"
        kit.check_no_attrib(log, e, ["ext-link-type", k_href])
        return self.parse_url(log, e, k_href, out)


class HtmlExtLinkModel(ExtLinkModelBase):
    def __init__(self, content_model: MixedModel):
        super().__init__(content_model)
        self.stag = StartTag('a', {'rel': 'external'})

    def match(self, xe: XmlElement) -> bool:
        return self.stag.issubset(xe)

    def parse(self, log: Log, xe: XmlElement, out: Sink[str | Element]) -> bool:
        kit.check_no_attrib(log, xe, ['rel', 'href'])
        return self.parse_url(log, xe, 'href', out)


def ext_link_model(content_model: MixedModel) -> MixedModel:
    return JatsExtLinkModel(content_model) | HtmlExtLinkModel(content_model)


class HtmlParagraphModel(Model[Element]):
    def __init__(self, hypertext: MixedModel, block: Model[Element]):
        self.inline_model = hypertext
        self.block_model = block

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'p'

    def parse(self, log: Log, xe: XmlElement, out: Sink[Element]) -> bool:
        # ignore JATS <p specific-use> attribute from BpDF ed.1
        kit.check_no_attrib(log, xe, ['specific-use'])
        pending = PendingMarkupBlock(out, dom.Paragraph())
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
                self.block_model.parse(log, s, out)
                if s.tail and not s.tail.strip():
                    s.tail = None
            else:
                log(fc.UnsupportedElement.issue(s))
                self.inline_model.parse_content(log, s, pending.append)
            if s.tail:
                pending.append(s.tail)
        if not pending.close() or autoclosed:
            out(dom.Paragraph(" "))
        if xe.tail:
            log(fc.IgnoredTail.issue(xe))
        return True


class ListModel(kit.LoadModelBase[Element]):
    def __init__(self, roll_content_model: ArrayContentModel):
        li_tag_model = TagModel(dom.ListItem, jats_name='list-item')
        li_element_model = ArrayParentModel(li_tag_model, roll_content_model)
        self._list_content = DataContentModel(li_element_model)

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
        ret = dom.List(ordered=(tag == 'ol'))
        self._list_content.parse_content(log, xe, ret.append)
        return ret


def def_term_model(term_text: MixedModel) -> Model[dom.DTerm]:
    """<term> Definition List: Term

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/term.html
    """
    tm = TagModel(dom.DTerm, jats_name='term')
    return MixedParentModel(tm, term_text)


def def_def_model(def_content: ArrayContentModel) -> Model[dom.DDefinition]:
    """<def> Definition List: Definition

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/def.html
    """
    tm = TagModel(dom.DDefinition, jats_name='def')
    return ArrayParentModel(tm, def_content)


class DefListItemModel(kit.LoadModelBase[dom.DItem]):
    """Description list item. HTML a <div> under <dl>, in JATS a <def-item>."""

    def __init__(self, term_text: MixedModel, def_content: ArrayContentModel):
        self.dt_element_model = def_term_model(term_text)
        self.dd_element_model = def_def_model(def_content)

    def match(self, xe: XmlElement) -> bool:
        return xe.tag in ['div', 'def-item']

    def load(self, log: Log, xe: XmlElement) -> dom.DItem | None:
        kit.check_no_attrib(log, xe)
        sess = ArrayContentSession()
        term = sess.one(self.dt_element_model)
        definitions: list[dom.DDefinition] = []
        sess.bind(self.dd_element_model, definitions.append)
        sess.parse_content(log, xe)
        if term.out is None:
            log(fc.MissingContent.issue(xe, "Definition/description term missing"))
            return None
        return dom.DItem(term.out, definitions)


def def_list_model(
    hypertext_model: MixedModel, roll_content: ArrayContentModel
) -> Model[Parent[dom.DItem]]:
    tm = TagModel(dom.DList, jats_name='def-list')
    child_model = DefListItemModel(hypertext_model, roll_content)
    return DataParentModel(tm, child_model)
