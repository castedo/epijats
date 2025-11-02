from __future__ import annotations

from enum import StrEnum

from .tree import ArrayParent, ArrayContent, Element, MixedParent, StartTag


MATHML_NAMESPACE_PREFIX = "{http://www.w3.org/1998/Math/MathML}"


class MathmlElement(MixedParent):
    def __init__(self, tag: str | StartTag):
        super().__init__(tag)
        mathml_tag = self.xml.name[len(MATHML_NAMESPACE_PREFIX) :]
        self.html = StartTag(mathml_tag, self.xml.attrib)


class FormulaStyle(StrEnum):
    INLINE = 'inline'
    DISPLAY = 'display'

    @property
    def jats_tag(self) -> str:
        return 'inline-formula' if self == FormulaStyle.INLINE else 'disp-formula'


class FormulaElement(Element):
    formula_style: FormulaStyle
    tex: str | None
    mathml: MathmlElement | None

    def __init__(self, formula_style: FormulaStyle):
        super().__init__(formula_style.jats_tag)
        self.formula_style = formula_style
        self.tex = None
        self.mathml = None

    @property
    def content(self) -> ArrayContent:
        alts = ArrayParent("alternatives")
        if self.tex:
            alts.append(MixedParent('tex-math', self.tex))
        if self.mathml:
            alts.append(self.mathml)
        return ArrayContent((alts,))
