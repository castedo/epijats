from __future__ import annotations

from typing import Iterable

from lxml import etree

from ..tree import CdataElement, Element, MarkupElement, StartTag

from . import kit
from .kit import (
    IssueCallback,
)
from .tree import (
    EModel,
    ElementModelBase,
    HtmlDataElementModel,
    TagElementModelBase,
    parse_mixed_content,
)


MATHML_NAMESPACE_PREFIX = "{http://www.w3.org/1998/Math/MathML}"

# Unknown MathML element per https://www.w3.org/TR/mathml-core/
# but found in PMC data:
# maligngroup, malignmark, menclose, mfenced, mlabeledtr, msubsub, none,

MATHML_TAGS = [
    'maction',
    'merror',
    'mfrac',
    'mi',
    'mmultiscripts',
    'mn',
    'mo',
    'mover',
    'mpadded',
    'mphantom',
    'mprescripts',
    'mroot',
    'mrow',
    'mspace',
    'msqrt',
    'mstyle',
    'msub',
    'msubsup',
    'msup',
    'mtable',
    'mtd',
    'mtext',
    'mtr',
    'munder',
    'munderover',
]


class AnyMathmlModel(ElementModelBase):
    @property
    def stags(self) -> Iterable[StartTag]:
        return (StartTag(MATHML_NAMESPACE_PREFIX + tag) for tag in MATHML_TAGS)

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        ret = None
        if isinstance(e.tag, str) and e.tag.startswith(MATHML_NAMESPACE_PREFIX):
            ret = MarkupElement(StartTag(e.tag, dict(e.attrib)))
            mathml_tag = e.tag[len(MATHML_NAMESPACE_PREFIX) :]
            ret.html = StartTag(mathml_tag, ret.xml.attrib)
            parse_mixed_content(log, e, self, ret.content)
        return ret


class TexMathElementModel(TagElementModelBase):
    def __init__(self) -> None:
        super().__init__('tex-math')

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        tex = kit.load_string_content(log, e)
        return CdataElement(self.tag, tex)


class MathmlElementModel(TagElementModelBase):
    def __init__(self, mathml_tag: str):
        super().__init__(MATHML_NAMESPACE_PREFIX + mathml_tag)
        self._model = AnyMathmlModel()
        self.mathml_tag = mathml_tag

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        ret = MarkupElement(StartTag(self.tag, dict(e.attrib)))
        ret.html = StartTag(self.mathml_tag, ret.xml.attrib)
        parse_mixed_content(log, e, self._model, ret.content)
        return ret


def math_model() -> EModel:
    """<mml:math> Math (MathML Tag Set)

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/mml-math.html
    """
    return MathmlElementModel('math')


def inline_formula_model() -> EModel:
    """<inline-formula> Formula, Inline

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/inline-formula.html
    """
    mathml = MathmlElementModel('math')
    alts = HtmlDataElementModel('alternatives', mathml | TexMathElementModel())
    return HtmlDataElementModel('inline-formula', mathml | alts)


def disp_formula_model() -> EModel:
    """<disp-formula> Formula, Display

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/disp-formula.html
    """
    mathml = MathmlElementModel('math')
    alts = HtmlDataElementModel('alternatives', mathml | TexMathElementModel())
    return HtmlDataElementModel('disp-formula', mathml | alts)
