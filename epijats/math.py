from __future__ import annotations

from enum import StrEnum

from .tree import DataElement, ArrayContent, Inline, MarkupElement, StartTag


MATHML_NAMESPACE_PREFIX = "{http://www.w3.org/1998/Math/MathML}"


class MathmlElement(MarkupElement):
    def __init__(self, xml_tag: str | StartTag):
        super().__init__(xml_tag)
        mathml_tag = self.xml.tag[len(MATHML_NAMESPACE_PREFIX) :]
        self.html = StartTag(mathml_tag, self.xml.attrib)


class FormulaStyle(StrEnum):
    INLINE = 'inline'
    DISPLAY = 'display'

    @property
    def jats_tag(self) -> str:
        return 'inline-formula' if self == FormulaStyle.INLINE else 'disp-formula'


class FormulaElement(Inline):
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
        alts = DataElement("alternatives")
        if self.tex:
            alts.content.append(MarkupElement('tex-math', self.tex))
        if self.mathml:
            alts.content.append(self.mathml)
        return ArrayContent((alts,))
