from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from ..tree import CdataElement, Element, MarkupElement, StartTag

from . import kit
from .kit import (
    IssueCallback,
)
from .tree import (
    EModel,
    ElementModelBase,
    DataElementModel,
    TagElementModelBase,
    parse_mixed_content,
)

if TYPE_CHECKING:
    from ..xml import XmlElement


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


class MathmlElement(MarkupElement):
    def __init__(self, xml_tag: str | StartTag):
        super().__init__(xml_tag)
        mathml_tag = self.xml.tag[len(MATHML_NAMESPACE_PREFIX) :]
        self.html = StartTag(mathml_tag, self.xml.attrib)


class AnyMathmlModel(ElementModelBase):
    @property
    def stags(self) -> Iterable[StartTag]:
        return (StartTag(MATHML_NAMESPACE_PREFIX + tag) for tag in MATHML_TAGS)

    def load(self, log: IssueCallback, e: XmlElement) -> Element | None:
        ret = None
        if isinstance(e.tag, str) and e.tag.startswith(MATHML_NAMESPACE_PREFIX):
            ret = MathmlElement(StartTag(e.tag, dict(e.attrib)))
            parse_mixed_content(log, e, self, ret.content)
        return ret


class TexMathElementModel(TagElementModelBase):
    def __init__(self) -> None:
        super().__init__('tex-math')

    def load(self, log: IssueCallback, e: XmlElement) -> Element | None:
        tex = kit.load_string_content(log, e)
        return CdataElement(self.tag, tex)


class MathmlElementModel(TagElementModelBase):
    def __init__(self, mathml_tag: str):
        super().__init__(MATHML_NAMESPACE_PREFIX + mathml_tag)
        self._model = AnyMathmlModel()
        self.mathml_tag = mathml_tag

    def load(self, log: IssueCallback, e: XmlElement) -> Element | None:
        ret = MathmlElement(StartTag(self.tag, dict(e.attrib)))
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
    alts = DataElementModel('alternatives', mathml | TexMathElementModel())
    return DataElementModel('inline-formula', mathml | alts)


def disp_formula_model() -> EModel:
    """<disp-formula> Formula, Display

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/disp-formula.html
    """
    mathml = MathmlElementModel('math')
    alts = DataElementModel('alternatives', mathml | TexMathElementModel())
    return DataElementModel('disp-formula', mathml | alts)
