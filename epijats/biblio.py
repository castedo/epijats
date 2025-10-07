from __future__ import annotations

import xml.etree.ElementTree
from abc import ABC, abstractmethod
from collections.abc import Sequence
from importlib import resources
from html import escape
from typing import TYPE_CHECKING, TypeAlias, assert_type
from warnings import warn

from . import baseprint as bp
from . import dom
from .xml import get_ET

if TYPE_CHECKING:
    from .typeshed import JSONType as JsonData
    import citeproc
    from .xml import XmlElement

    CslJson: TypeAlias = dict[str, JsonData]


JATS_TO_CSL_VAR = {
    'comment': 'note',
    'isbn': 'ISBN',
    'issn': 'ISSN',
    'issue': 'issue',
    'publisher-loc': 'publisher-place',
    'publisher-name': 'publisher',
    'uri': 'URL',
    'volume': 'volume',
}


def hyperlink(xhtml_content: str, prepend: str | None = None) -> str:
    ele = xml.etree.ElementTree.fromstring(f"<root>{xhtml_content}</root>")
    if not ele.text or not ele.text.strip():
        return xhtml_content
    url = ele.text
    if prepend:
        url = prepend + url
    element = xml.etree.ElementTree.Element('a', {'href': url})
    element.text = url
    return xml.etree.ElementTree.tostring(element, encoding='unicode', method='html')


def hyperlinkize_csljson(jd: CslJson) -> CslJson:
    for key, value in jd.items():
        match key:
            case 'URL':
                jd[key] = hyperlink(str(value))
            case 'DOI':
                jd[key] = hyperlink(str(value), "https://doi.org/")
    return jd


def set_str(cj: CslJson, key: str, val: str | int | None) -> None:
    if val is not None:
        if isinstance(val, int):
            val = str(val)
        cj[key] = escape(val, quote=False)


def csljson_from_date(src: bp.Date) -> JsonData:
    parts: list[JsonData] = [src.year]
    if src.month:
        parts.append(src.month)
        if src.day:
            parts.append(src.day)
    return {'date-parts': [parts]}


def set_csljson_dates(dest: CslJson, src: bp.BiblioRefItem) -> None:
    if src.date:
        dest['issued'] = csljson_from_date(src.date)
    if src.access_date:
        dest['accessed'] = csljson_from_date(src.access_date)


def csljson_from_person_group(src: bp.PersonGroup) -> JsonData:
    ret = list['JsonData']()
    for person in src.persons:
        a: dict[str, JsonData] = {}
        if isinstance(person, bp.PersonName):
            if person.surname:
                a['family'] = escape(person.surname, quote=False)
            if person.given_names:
                a['given'] = escape(person.given_names, quote=False)
        else:
            assert_type(person, str)
            a['literal'] = escape(str(person), quote=False)
        ret.append(a)
    if src.etal:
        ret.append({'literal': 'others'})
    return ret


def set_csjson_persons(dest: CslJson, src: bp.BiblioRefItem) -> None:
    if src.authors:
        dest['author'] = csljson_from_person_group(src.authors)
    if src.editors:
        dest['editor'] = csljson_from_person_group(src.editors)


def set_csljson_titles(dest: CslJson, src: bp.BiblioRefItem) -> None:
    if src.article_title:
        set_str(dest, 'container-title', src.source_title)
        set_str(dest, 'title', src.article_title)
    else:
        set_str(dest, 'title', src.source_title)


def set_csljson_pages(dest: CslJson, src: bp.BiblioRefItem) -> None:
    if fpage := src.biblio_fields.get('fpage'):
        page = fpage
        if lpage := src.biblio_fields.get('lpage'):
            page += f"-{lpage}"
        set_str(dest, 'page', page)


def csljson_from_ref_item(src: bp.BiblioRefItem) -> CslJson:
    ret = dict[str, 'JsonData']()
    ret['type'] = ''
    set_str(ret, 'id', src.id)
    for jats_key, value in src.biblio_fields.items():
        if csl_key := JATS_TO_CSL_VAR.get(jats_key):
            set_str(ret, csl_key, value)
    set_csljson_titles(ret, src)
    set_csljson_dates(ret, src)
    set_csjson_persons(ret, src)
    set_str(ret, 'edition', src.edition)
    set_csljson_pages(ret, src)
    for pub_id_type, value in src.pub_ids.items():
        set_str(ret, pub_id_type.upper(), value)
    return ret


def csljson_refs_from_baseprint(src: dom.Article) -> list[CslJson] | None:
    if not src.ref_list:
        return None
    return [csljson_from_ref_item(r) for r in src.ref_list.references]


class BiblioFormatter(ABC):
    @abstractmethod
    def to_element(self, refs: Sequence[bp.BiblioRefItem]) -> XmlElement: ...


def put_tags_on_own_lines(e: XmlElement) -> None:
    e.text = "\n{}".format(e.text or '')
    s = None
    for s in e:
        pass
    if s is None:
        e.text += "\n"
    else:
        s.tail = "{}\n".format(s.tail or '')


class CiteprocBiblioFormatter(BiblioFormatter):
    def __init__(self, *, abridged: bool = False, use_lxml: bool = False):
        import citeproc

        if use_lxml:
            warn("Option use_lxml will be removed", DeprecationWarning)

        self._abridged = abridged
        filename = "abridged.csl" if abridged else "full-preview.csl"
        r = resources.files(__package__) / f"csl/{filename}"
        with resources.as_file(r) as csl_file:
            self._style = citeproc.CitationStylesStyle(csl_file, validate=False)
        self._ET = get_ET(use_lxml=use_lxml)

    def _divs_from_citeproc_bibliography(
        self, biblio: citeproc.CitationStylesBibliography
    ) -> list[XmlElement]:
        ret: list[XmlElement] = []
        for item in biblio.bibliography():
            s = str(item).replace("..\n", ".\n").strip()
            s = s.replace("others.\n", "et al.\n")
            s = s.replace("and et al.\n", "et al.\n")
            div = self._ET.fromstring("<div>" + s + "</div>")
            put_tags_on_own_lines(div)
            div.tail = "\n"
            ret.append(div)
        return ret

    def to_element(self, refs: Sequence[bp.BiblioRefItem]) -> XmlElement:
        import citeproc

        csljson = [hyperlinkize_csljson(csljson_from_ref_item(r)) for r in refs]
        bib_source = citeproc.source.json.CiteProcJSON(csljson)
        biblio = citeproc.CitationStylesBibliography(
            self._style, bib_source, citeproc.formatter.html
        )
        for ref_item in refs:
            c = citeproc.Citation([citeproc.CitationItem(ref_item.id)])
            biblio.register(c)
        divs = self._divs_from_citeproc_bibliography(biblio)
        if len(divs) != len(refs):
            warn("Unable to generate HTML for proper number of references")
        ret: XmlElement = self._ET.Element('ol')
        ret.text = "\n"
        for i in range(len(divs)):
            li = self._ET.Element('li')
            li.attrib['id'] = refs[i].id
            li.text = "\n"
            li.append(divs[i])
            if not self._abridged:
                if comment := refs[i].biblio_fields.get('comment'):
                    div2 = self._ET.Element('div')
                    div2.text = comment
                    div2.tail = "\n"
                    li.append(div2)
            li.tail = "\n"
            ret.append(li)
        return ret

    def to_str(self, refs: Sequence[bp.BiblioRefItem]) -> str:
        e = self.to_element(refs)
        ret = self._ET.tostring(e, encoding='unicode', method='html')
        return ret  # type: ignore[no-any-return]
