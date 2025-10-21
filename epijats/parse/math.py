from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from ..math import (
    MATHML_NAMESPACE_PREFIX,
    MathmlElement,
    FormulaElement,
    FormulaStyle,
)
from ..tree import Element, Inline, StartTag

from . import kit
from .content import ArrayContentSession
from .kit import Log
from .content import parse_mixed_content

if TYPE_CHECKING:
    from ..typeshed import XmlElement


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


class AnyMathmlModel(kit.LoadModel[Inline]):
    XML_TAGS = {(MATHML_NAMESPACE_PREFIX + tag) for tag in MATHML_TAGS}

    def match(self, xe: XmlElement) -> bool:
        return xe.tag in self.XML_TAGS

    def load(self, log: Log, e: XmlElement) -> Inline | None:
        ret = None
        if isinstance(e.tag, str):
            assert e.tag.startswith(MATHML_NAMESPACE_PREFIX)
            ret = MathmlElement(StartTag(e.tag, dict(e.attrib)))
            parse_mixed_content(log, e, self, ret.content)
        return ret


class MathmlElementModel(kit.TagModelBase[Inline]):
    """<mml:math> Math (MathML Tag Set)

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/mml-math.html
    """

    def __init__(self, mathml_tag: str):
        super().__init__(MATHML_NAMESPACE_PREFIX + mathml_tag)
        self._model = AnyMathmlModel()
        self.mathml_tag = mathml_tag

    def load(self, log: Log, e: XmlElement) -> Inline | None:
        ret = MathmlElement(StartTag(self.tag, dict(e.attrib)))
        parse_mixed_content(log, e, self._model, ret.content)
        return ret


class FormulaAlternativesModel(kit.TagModelBase[Inline]):
    """<alternatives> within the context of <inline-formula> and <disp-formula>

    https://jats.nlm.nih.gov/publishing/tag-library/1.4/element/alternatives.html
    """

    def __init__(self, formula_style: FormulaStyle):
        super().__init__('alternatives')
        self.formula_style = formula_style

    def load(self, log: Log, e: XmlElement) -> Inline | None:
        kit.check_no_attrib(log, e)
        cp = ArrayContentSession(log)
        tex = cp.one(kit.LoaderTagModel('tex-math', kit.load_string))
        mathml = cp.one(MathmlElementModel('math'))
        cp.parse_content(e)
        if not tex.out:
            return None
        ret = FormulaElement(self.formula_style)
        if tex.out:
            ret.tex = tex.out
        if mathml.out:
            assert isinstance(mathml.out, MathmlElement)
            ret.mathml = mathml.out
        return ret


InlineOrElement = TypeVar('InlineOrElement', Inline, Element)


class FormulaModel(kit.TagModelBase[InlineOrElement]):
    def __init__(self, formula_style: FormulaStyle):
        super().__init__(formula_style.jats_tag)
        self.child_model = FormulaAlternativesModel(formula_style)

    def load(self, log: Log, xe: XmlElement) -> InlineOrElement | None:
        kit.check_no_attrib(log, xe)
        sess = ArrayContentSession(log)
        result = sess.one(self.child_model)
        sess.parse_content(xe)
        return result.out


def inline_formula_model() -> kit.Model[Inline]:
    """<inline-formula> Formula, Inline

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/inline-formula.html
    """
    return FormulaModel(FormulaStyle.INLINE)


def disp_formula_model() -> kit.Model[Element]:
    """<disp-formula> Formula, Display

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/disp-formula.html
    """
    return FormulaModel(FormulaStyle.DISPLAY)
