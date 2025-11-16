from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from .. import dom
from .. import condition as fc
from ..biblio import BiblioRefPool
from ..elements import Citation, CitationTuple
from ..tree import Element, MutableMixedContent

from . import kit
from .kit import Log, Model, Sink
from .content import (
    ArrayContentModel,
    MixedModel,
    PendingMarkupBlock,
    RollContentModel,
    UnionMixedModel,
)
from .htmlish import (
    HtmlParagraphModel,
    ListModel,
    blockquote_model,
    break_model,
    code_model,
    def_list_model,
    ext_link_model,
    formatted_text_model,
    hypotext_model,
    preformat_model,
)
from .table import table_or_wrap_model
from .tree import MarkupBlockModel
from .math import disp_formula_model, inline_formula_model


if TYPE_CHECKING:
    from ..typeshed import XmlElement


def hypertext_model(biblio: BiblioRefPool | None, *, math: bool = True) -> MixedModel:
    # Corresponds to {HYPERTEXT} in BpDF spec ed.2
    # but with experimental inline math element too
    hypotext = hypotext_model()
    hypertext = UnionMixedModel()
    if biblio:
        # model for <sup>~CITE must preempt regular <sup> model
        hypertext |= AutoCorrectCitationModel(biblio)
        hypertext |= CitationTupleModel(biblio)
    hypertext |= formatted_text_model(hypertext)
    hypertext |= ext_link_model(hypotext)
    hypertext |= cross_reference_model(hypotext, biblio)
    hypertext |= code_model(hypertext)
    if math:
        hypertext |= inline_formula_model()
    return hypertext


class CoreModels:
    def __init__(
        self,
        biblio: BiblioRefPool | None,
        *,
        math: bool = True,
        tables: bool = True,
    ) -> None:
        self.inline = hypertext_model(biblio, math=True) | break_model()
        self.block = kit.UnionModel[Element]()
        self.roll = RollContentModel(self.block, self.inline)
        self.block |= HtmlParagraphModel(self.inline, self.block)
        self.block |= MarkupBlockModel(self.inline)
        self.block |= preformat_model(self.inline)
        self.block |= ListModel(self.roll)
        self.block |= def_list_model(self.inline, self.roll)
        self.block |= blockquote_model(self.roll)
        if math:
            self.block |= disp_formula_model()
        if tables:
            self.block |= table_or_wrap_model(self.roll)


def roll_model(
    biblio: BiblioRefPool | None, *, math: bool = True, tables: bool = True
) -> ArrayContentModel:
    core = CoreModels(biblio, math=math, tables=tables)
    return core.roll


class CitationModel(kit.LoadModelBase[Citation]):
    def __init__(self, biblio: BiblioRefPool):
        self.biblio = biblio

    def match(self, xe: XmlElement) -> bool:
        # JatsCrossReferenceModel is the opposing <xref> model to CitationModel
        if xe.tag != 'xref':
            return False
        if xe.attrib.get('ref-type') == 'bibr':
            return True
        return self.biblio.is_bibr_rid(xe.attrib.get("rid"))

    def load(self, log: Log, e: XmlElement) -> Citation | None:
        alt = e.attrib.get("alt")
        if alt and alt == e.text and not len(e):
            del e.attrib["alt"]
        kit.check_no_attrib(log, e, ["rid", "ref-type"])
        rid = e.attrib.get("rid")
        if rid is None:
            log(fc.MissingAttribute.issue(e, "rid"))
            return None
        for s in e:
            log(fc.UnsupportedElement.issue(s))
        try:
            rord = int(e.text or '')
        except ValueError:
            rord = None
        ret = self.biblio.cite(rid, rord)
        if not ret:
            log(fc.InvalidCitation.issue(e, rid))
        elif e.text and not ret.matching_text(e.text):
            log(fc.IgnoredText.issue(e))
        return ret


class AutoCorrectCitationModel(kit.LoadModelBase[CitationTuple]):
    def __init__(self, biblio: BiblioRefPool):
        submodel = CitationModel(biblio)
        self._submodel = submodel

    def match(self, xe: XmlElement) -> bool:
        return self._submodel.match(xe)

    def load(self, log: Log, e: XmlElement) -> CitationTuple | None:
        citation = self._submodel.load(log, e)
        return CitationTuple([citation]) if citation else None


class CitationRangeHelper:
    def __init__(self, log: Log, biblio: BiblioRefPool):
        self.log = log
        self._biblio = biblio
        self.starter: Citation | None = None
        self.stopper: Citation | None = None

    @staticmethod
    def is_tuple_open(text: str | None) -> bool:
        delim = text.strip() if text else ''
        return delim in {'', '[', '('}

    def _inner_range(self, before: Citation, after: Citation) -> Iterator[Citation]:
        for rord in range(before.rord + 1, after.rord):
            rid = self._biblio.get_by_rord(rord).id
            yield Citation(rid, rord)

    def get_range(self, child: XmlElement, citation: Citation) -> Iterator[Citation]:
        if citation.matching_text(child.text):
            self.stopper = citation
        if self.starter:
            if self.stopper:
                return self._inner_range(self.starter, self.stopper)
            else:
                msg = f"Invalid citation '{citation.rid}' to end range"
                self.log(fc.InvalidCitation.issue(child, msg))
        return iter(())

    def new_start(self, child: XmlElement) -> None:
        delim = child.tail.strip() if child.tail else ''
        if delim in {'-', '\u2010', '\u2011', '\u2012', '\u2013', '\u2014'}:
            self.starter = self.stopper
            if not self.starter:
                msg = "Invalid citation to start range"
                self.log(fc.InvalidCitation.issue(child, msg))
        else:
            self.starter = None
            if delim not in {'', ',', ';', ']', ')'}:
                self.log(fc.IgnoredTail.issue(child))
        self.stopper = None


class CitationTupleModel(kit.LoadModelBase[CitationTuple]):
    def __init__(self, biblio: BiblioRefPool):
        super().__init__()
        self._submodel = CitationModel(biblio)

    def match(self, xe: XmlElement) -> bool:
        # Minor break of backwards compat to BpDF ed.1 where
        # xref inside sup might be what is now <a href="#...">
        # But no known archived baseprint did this.
        return xe.tag == 'sup' and any(c.tag == 'xref' for c in xe)

    def load(self, log: Log, e: XmlElement) -> CitationTuple | None:
        kit.check_no_attrib(log, e)
        range_helper = CitationRangeHelper(log, self._submodel.biblio)
        if not range_helper.is_tuple_open(e.text):
            log(fc.IgnoredText.issue(e))
        ret = CitationTuple()
        for child in e:
            citation = self._submodel.load_if_match(log, child)
            if citation is None:
                log(fc.UnsupportedElement.issue(child))
            else:
                for implied in range_helper.get_range(child, citation):
                    ret.append(implied)
                ret.append(citation)
            range_helper.new_start(child)
        return ret if len(ret) else None


class JatsCrossReferenceModel(kit.LoadModelBase[dom.CrossReference]):
    def __init__(self, content_model: MixedModel, biblio: BiblioRefPool | None):
        self.content_model = content_model
        self.biblio = biblio

    def match(self, xe: XmlElement) -> bool:
        # CitationModel is the opposing <xref> model to JatsCrossReferenceModel
        if xe.tag != 'xref':
            return False
        if xe.attrib.get('ref-type') == 'bibr':
            return False
        return not (self.biblio and self.biblio.is_bibr_rid(xe.attrib.get("rid")))

    def load(self, log: Log, e: XmlElement) -> dom.CrossReference | None:
        alt = e.attrib.get("alt")
        if alt and alt == e.text and not len(e):
            del e.attrib["alt"]
        kit.check_no_attrib(log, e, ["rid"])
        rid = e.attrib.get("rid")
        if rid is None:
            log(fc.MissingAttribute.issue(e, "rid"))
            return None
        ret = dom.CrossReference(rid)
        self.content_model.parse_content(log, e, ret.append)
        return ret


class HtmlCrossReferenceModel(MixedModel):
    def __init__(self, content_model: MixedModel):
        self.content_model = content_model

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'a' and 'rel' not in xe.attrib

    def parse(self, log: Log, xe: XmlElement, out: Sink[str | Element]) -> bool:
        kit.check_no_attrib(log, xe, ['href'])
        href = xe.attrib.get("href")
        if href is None:
            log(fc.MissingAttribute.issue(xe, "href"))
            # parse per model with hyperlinks (not within), to allow hyperlinks
            self.parse_content(log, xe, out)
        else:
            href = href.strip()
            if not href.startswith("#"):
                log(fc.InvalidAttributeValue.issue(xe, 'href', href))
                self.content_model.parse_content(log, xe, out)
            else:
                ret = dom.CrossReference(href[1:])
                self.content_model.parse_content(log, xe, ret.append)
                out(ret)
        return True


def cross_reference_model(
    content_model: MixedModel, biblio: BiblioRefPool | None
) -> MixedModel:
    jats_xref = JatsCrossReferenceModel(content_model, biblio)
    return HtmlCrossReferenceModel(content_model) | jats_xref


class ProtoSectionParser:
    def __init__(self, section_model: SectionModel):
        self.section_model = section_model

    def parse(
        self,
        log: Log,
        xe: XmlElement,
        target: dom.ProtoSection,
        title: MutableMixedContent | None,
    ) -> None:
        inline_model = self.section_model.inline_model
        block_model = self.section_model.block_model
        pending = PendingMarkupBlock(target.presection.append)
        if xe.text and xe.text.strip():
            pending.append(xe.text)
        for s in xe:
            tail = s.tail
            s.tail = None
            if s.tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'title']:
                if title is None:
                    log(fc.ExcessElement.issue(s))
                else:
                    inline_model.parse_content(log, s, title)
                    title = None
            elif block_model.match(s):
                pending.close()
                block_model.parse(log, s, target.presection.append)
            elif self.section_model.match(s):
                pending.close()
                self.section_model.parse(log, s, target.subsections.append)
            elif inline_model.match(s):
                inline_model.parse(log, s, pending.append)
            else:
                log(fc.UnsupportedElement.issue(s))
            if tail and tail.strip():
                pending.append(tail)
        pending.close()


class SectionModel(kit.LoadModelBase[dom.Section]):
    """<sec> Section
    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/sec.html
    """

    def __init__(self, block_model: Model[Element], inline_model: MixedModel):
        self.block_model = block_model
        self.inline_model = inline_model
        self._proto = ProtoSectionParser(self)

    def match(self, xe: XmlElement) -> bool:
        return xe.tag in ['section', 'sec']

    def load(self, log: Log, e: XmlElement) -> dom.Section | None:
        kit.check_no_attrib(log, e, ['id'])
        ret = dom.Section(e.attrib.get('id'))
        self._proto.parse(log, e, ret, ret.title)
        if ret.title.blank():
            log(fc.MissingSectionHeading.issue(e))
        return ret


class BodyModel(kit.Parser[dom.ProtoSection]):
    def __init__(self, biblio: BiblioRefPool | None):
        core = CoreModels(biblio, math=True, tables=True)
        self._proto = ProtoSectionParser(SectionModel(core.block, core.inline))

    def parse(self, log: Log, xe: XmlElement, target: dom.ProtoSection) -> bool:
        kit.check_no_attrib(log, xe)
        self._proto.parse(log, xe, target, None)
        return True

    def match(self, xe: XmlElement) -> bool:
        # JATS and HTML conflict in use of <body> tag
        # DOMParser moves <body> position when parsed as HTML
        return xe.tag in ['article-body', 'body']
