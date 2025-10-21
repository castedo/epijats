from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from .. import dom
from .. import condition as fc
from ..biblio import BiblioRefPool
from ..elements import Citation, CitationTuple
from ..tree import Element, Inline, MixedContent

from . import kit
from .kit import Log, Model
from .content import (
    ContentMold,
    PendingMarkupBlock,
    MixedContentMold,
    RollContentMold,
    parse_mixed_content,
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
    table_wrap_model,
)
from .tree import MarkupBlockModel, MixedContentModelBase
from .math import disp_formula_model, inline_formula_model


if TYPE_CHECKING:
    from ..typeshed import XmlElement


def hypertext_model(biblio: BiblioRefPool | None) -> Model[Inline]:
    # Corresponds to {HYPERTEXT} in BpDF spec ed.2
    # but with experimental inline math element too
    hypotext = hypotext_model()
    hypertext = kit.UnionModel[Inline]()
    if biblio:
        # model for <sup>~CITE must preempt regular <sup> model
        hypertext |= AutoCorrectCitationModel(biblio)
        hypertext |= CitationTupleModel(biblio)
    hypertext |= formatted_text_model(hypertext)
    hypertext |= ext_link_model(hypotext)
    hypertext |= cross_reference_model(hypotext, biblio)
    hypertext |= code_model(hypertext)
    hypertext |= inline_formula_model()
    return hypertext


class CoreModels:
    def __init__(self, biblio: BiblioRefPool | None) -> None:
        self.hypertext = hypertext_model(biblio)
        self.heading = MixedContentMold(self.hypertext | break_model())
        block = kit.UnionModel[Element]()
        roll_content = RollContentMold(block, self.hypertext)
        block |= HtmlParagraphModel(self.hypertext, block)
        block |= MarkupBlockModel(self.hypertext)
        block |= disp_formula_model()
        block |= preformat_model(self.hypertext)
        block |= ListModel(roll_content)
        block |= def_list_model(self.hypertext, roll_content)
        block |= blockquote_model(roll_content)
        block |= table_wrap_model(self.hypertext)
        self.block = block


class CitationModel(kit.LoadModel[Citation]):
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


class AutoCorrectCitationModel(kit.LoadModel[Inline]):
    def __init__(self, biblio: BiblioRefPool):
        submodel = CitationModel(biblio)
        self._submodel = submodel

    def match(self, xe: XmlElement) -> bool:
        return self._submodel.match(xe)

    def load(self, log: Log, e: XmlElement) -> Inline | None:
        citation = self._submodel.load(log, e)
        if citation:
            return CitationTuple([citation])
        else:
            return None


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


class CitationTupleModel(kit.LoadModel[Inline]):
    def __init__(self, biblio: BiblioRefPool):
        super().__init__()
        self._submodel = CitationModel(biblio)

    def match(self, xe: XmlElement) -> bool:
        # Minor break of backwards compat to BpDF ed.1 where
        # xref inside sup might be what is now <a href="#...">
        # But no known archived baseprint did this.
        return xe.tag == 'sup' and any(c.tag == 'xref' for c in xe)

    def load(self, log: Log, e: XmlElement) -> Inline | None:
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
                ret.extend(range_helper.get_range(child, citation))
                citation.tail = ''
                ret.append(citation)
            range_helper.new_start(child)
        return ret if len(ret) else None


class JatsCrossReferenceModel(kit.LoadModel[Inline]):
    def __init__(self, content_model: Model[Inline], biblio: BiblioRefPool | None):
        self.content_model = content_model
        self.biblio = biblio

    def match(self, xe: XmlElement) -> bool:
        # CitationModel is the opposing <xref> model to JatsCrossReferenceModel
        if xe.tag != 'xref':
            return False
        if xe.attrib.get('ref-type') == 'bibr':
            return False
        return not (self.biblio and self.biblio.is_bibr_rid(xe.attrib.get("rid")))

    def load(self, log: Log, e: XmlElement) -> Inline | None:
        alt = e.attrib.get("alt")
        if alt and alt == e.text and not len(e):
            del e.attrib["alt"]
        kit.check_no_attrib(log, e, ["rid"])
        rid = e.attrib.get("rid")
        if rid is None:
            log(fc.MissingAttribute.issue(e, "rid"))
            return None
        ret = dom.CrossReference(rid)
        parse_mixed_content(log, e, self.content_model, ret.content)
        return ret


class HtmlCrossReferenceModel(kit.LoadModel[Inline]):
    def __init__(self, content_model: Model[Inline]):
        self.content_model = content_model

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'a' and 'rel' not in xe.attrib

    def load(self, log: Log, xe: XmlElement) -> Inline | None:
        kit.check_no_attrib(log, xe, ['href'])
        href = xe.attrib.get("href")
        if href is None:
            log(fc.MissingAttribute.issue(xe, "href"))
            return None
        href = href.strip()
        if not href.startswith("#"):
            log(fc.InvalidAttributeValue.issue(xe, 'href', href))
            return None
        ret = dom.CrossReference(href[1:])
        parse_mixed_content(log, xe, self.content_model, ret.content)
        return ret


def cross_reference_model(
    content_model: Model[Inline], biblio: BiblioRefPool | None
) -> Model[Inline]:
    jats_xref = JatsCrossReferenceModel(content_model, biblio)
    return jats_xref | HtmlCrossReferenceModel(content_model)


class SectionTitleMonoModel(MixedContentModelBase):
    def __init__(self, content_mold: ContentMold[MixedContent]):
        super().__init__(content_mold)

    def match(self, xe: XmlElement) -> bool:
        return xe.tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'title']


class ProtoSectionParser:
    def __init__(self, models: CoreModels, section_model: SectionModel):
        self.inline_model = models.hypertext
        self.block_model = models.block
        self.section_model = section_model
        self._title_model = SectionTitleMonoModel(models.heading)

    def parse(
        self,
        log: Log,
        xe: XmlElement,
        target: dom.ProtoSection,
        title: MixedContent | None,
    ) -> None:
        title_parser = None
        if title is not None:
            title_parser = self._title_model.mono_parser(log, title)
        pending = PendingMarkupBlock(target.presection.append)
        if xe.text and xe.text.strip():
            pending.content.append_text(xe.text)
        for s in xe:
            tail = s.tail
            s.tail = None
            if title_parser and title_parser.parse_element(s):
                title_parser = None
            elif self.block_model.match(s):
                pending.close()
                self.block_model.parse(log, s, target.presection.append)
            elif self.section_model.match(s):
                pending.close()
                self.section_model.parse(log, s, target.subsections.append)
            elif self.inline_model.match(s):
                self.inline_model.parse(log, s, pending.content.append)
            else:
                log(fc.UnsupportedElement.issue(s))
            if tail and tail.strip():
                pending.content.append_text(tail)
        pending.close()


class SectionModel(kit.LoadModel[dom.Section]):
    """<sec> Section
    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/sec.html
    """

    def __init__(self, models: CoreModels):
        self._proto = ProtoSectionParser(models, self)

    def match(self, xe: XmlElement) -> bool:
        return xe.tag in ['section', 'sec']

    def load(self, log: Log, e: XmlElement) -> dom.Section | None:
        kit.check_no_attrib(log, e, ['id'])
        ret = dom.Section(e.attrib.get('id'))
        self._proto.parse(log, e, ret, ret.title)
        if ret.title.blank():
            log(fc.MissingSectionHeading.issue(e))
        return ret


class BodyModel(kit.MonoModel[dom.ProtoSection]):
    def __init__(self, models: CoreModels):
        self._proto = ProtoSectionParser(models, SectionModel(models))

    @property
    def parsed_type(self) -> type[dom.ProtoSection]:
        return dom.ProtoSection

    def check(self, log: Log, e: XmlElement) -> None:
        kit.check_no_attrib(log, e)

    def read(self, log: Log, xe: XmlElement, target: dom.ProtoSection) -> None:
        self.check(log, xe)
        self._proto.parse(log, xe, target, None)

    def match(self, xe: XmlElement) -> bool:
        # JATS and HTML conflict in use of <body> tag
        # DOMParser moves <body> position when parsed as HTML
        return xe.tag in ['article-body', 'body']
