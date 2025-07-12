from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from ..math import (
    MATHML_NAMESPACE_PREFIX,
    MathmlElement,
    FormulaElement,
    FormulaStyle,
)
from ..tree import CdataElement, Element, StartTag

from . import kit
from .kit import IssueCallback
from .tree import (
    EModel,
    parse_mixed_content,
)

if TYPE_CHECKING:
    from ..xml import XmlElement


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


class AnyMathmlModel(kit.ModelBase[Element]):
    @property
    def stags(self) -> Iterable[StartTag]:
        return (StartTag(MATHML_NAMESPACE_PREFIX + tag) for tag in MATHML_TAGS)

    def load(self, log: IssueCallback, e: XmlElement) -> Element | None:
        ret = None
        if isinstance(e.tag, str):
            assert e.tag.startswith(MATHML_NAMESPACE_PREFIX)
            ret = MathmlElement(StartTag(e.tag, dict(e.attrib)))
            parse_mixed_content(log, e, self, ret.content)
        return ret


class TexMathElementModel(kit.TagModelBase[Element]):
    def __init__(self) -> None:
        super().__init__('tex-math')

    def load(self, log: IssueCallback, e: XmlElement) -> Element | None:
        tex = kit.load_string_content(log, e)
        return CdataElement(self.tag, tex)


class MathmlElementModel(kit.TagModelBase[Element]):
    """<mml:math> Math (MathML Tag Set)

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/mml-math.html
    """
    def __init__(self, mathml_tag: str):
        super().__init__(MATHML_NAMESPACE_PREFIX + mathml_tag)
        self._model = AnyMathmlModel()
        self.mathml_tag = mathml_tag

    def load(self, log: IssueCallback, e: XmlElement) -> Element | None:
        ret = MathmlElement(StartTag(self.tag, dict(e.attrib)))
        parse_mixed_content(log, e, self._model, ret.content)
        return ret


class FormulaAlternativesModel(kit.TagModelBase[Element]):
    """<alternatives> within the context of <inline-formula> and <disp-formula>

    https://jats.nlm.nih.gov/publishing/tag-library/1.4/element/alternatives.html
    """
    def __init__(self, formula_style: FormulaStyle):
        super().__init__('alternatives')
        self.formula_style = formula_style

    def load(self, log: IssueCallback, e: XmlElement) -> Element | None:
        kit.check_no_attrib(log, e)
        cp = kit.ContentParser(log)
        tex = cp.one(kit.tag_model('tex-math', kit.load_string))
        mathml = cp.one(MathmlElementModel('math'))
        cp.parse_array_content(e)
        if not tex.out:
            return None
        ret = FormulaElement(self.formula_style)
        if tex.out:
            ret.tex = tex.out
        if mathml.out:
            assert isinstance(mathml.out, MathmlElement)
            ret.mathml = mathml.out
        return ret


def formula_model(formula_style: FormulaStyle) -> EModel:
    alts = FormulaAlternativesModel(formula_style)
    return kit.tag_model(formula_style.jats_tag, kit.SingleSubElementLoader(alts))


def inline_formula_model() -> EModel:
    """<inline-formula> Formula, Inline

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/inline-formula.html
    """
    return formula_model(FormulaStyle.INLINE)


def disp_formula_model() -> EModel:
    """<disp-formula> Formula, Display

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/disp-formula.html
    """
    return formula_model(FormulaStyle.DISPLAY)
