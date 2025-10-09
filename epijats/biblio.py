from __future__ import annotations

import xml.etree.ElementTree
from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from importlib import resources
from html import escape
from typing import TYPE_CHECKING, TypeAlias, assert_type
from warnings import warn

from . import dom
from . import metadata as bp
from .elements import Citation
from .metadata import BiblioRefItem

if TYPE_CHECKING:
    from .typeshed import JsonData
    import citeproc
    from .typeshed import XmlElement

    CslJson: TypeAlias = dict[str, JsonData]


class BiblioRefPool:
    def __init__(self, orig: Iterable[BiblioRefItem]):
        self._orig = list(orig)
        self.used: list[BiblioRefItem] = []
        self._orig_order = True

    def is_bibr_rid(self, rid: str | None) -> bool:
        return bool(rid) and any(rid == ref.id for ref in self._orig)

    def cite(self, rid: str, ideal_rord: int | None = None) -> Citation | None:
        for zidx, ref in enumerate(self.used):
            if rid == ref.id:
                return Citation(rid, zidx + 1)
        for zidx, ref in enumerate(self._orig):
            if rid == ref.id:
                if self._orig_order:
                    if zidx + 1 == ideal_rord:
                        for j in range(len(self.used), zidx):
                            self.used.append(self._orig[j])
                    else:
                        self._orig_order = False
                self.used.append(ref)
                return Citation(rid, len(self.used))
        return None

    def get_by_rord(self, rord: int) -> BiblioRefItem:
        """Get using one-based index of 'rord' value"""

        return self.used[rord - 1]


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


CSLJSON_NOT_SUPPORTED = {
    '<i>',
    '</i>',
    '<b>',
    '</b>',
    '<sub>',
    '</sub>',
    '<sup>',
    '</sup>',
    '<span style="font-variant: small-caps;">',
    '<span class="nocase">',
    '</span>',
}


def get_str_or_none(cj: CslJson, key: str) -> str | None:
    val = cj.get(key)
    if not isinstance(val, str):
        return None
    if any(bad in val for bad in CSLJSON_NOT_SUPPORTED):
        warn("HTML-like CSLJSON formatting not supported")
    return val


def set_csljson_titles(dest: CslJson, src: BiblioRefItem) -> None:
    if src.article_title:
        # add json null even if source title is missing
        # this way solitary article title will roundtrip through CSLJSON
        dest['container-title'] = src.source_title
        dest['title'] = src.article_title
    elif src.source_title:
        dest['title'] = src.source_title


def set_ref_item_titles(dest: BiblioRefItem, src: CslJson) -> None:
    if 'container-title' in src:
        container_title = src['container-title']
        if container_title is None:
            # literally null is the JSON value for 'container-title' key
            dest.article_title = get_str_or_none(src, 'title')
        elif isinstance(container_title, str):
            dest.source_title = container_title
            dest.article_title = get_str_or_none(src, 'title')
        else:
            warn("CSLJSON container-title is not of string type")
    else:
        dest.source_title = get_str_or_none(src, 'title')


def csljson_from_date(src: bp.Date) -> JsonData:
    parts: list[JsonData] = [src.year]
    if src.month:
        parts.append(src.month)
        if src.day:
            parts.append(src.day)
    return {'date-parts': [parts]}


def date_from_csljson(src: JsonData) -> bp.Date | None:
    if not isinstance(src, dict):
        return None
    dates = src.get('date-parts')
    if not isinstance(dates, list) or len(dates) < 1:
        return None
    if len(dates) > 1:
        warn(f"CSLJSON date range unsupported: {dates}")
    parts = dates[0]
    if not isinstance(parts, list) or len(parts) < 1:
        return None
    if len(parts) > 3:
        warn(f"CSLJSON date has too many parts: {parts}")
    year = parts[0]
    if not isinstance(year, int):
        return None
    ret = bp.Date(year)
    if len(parts) > 1:
        month = parts[1]
        if isinstance(month, int):
            ret.month = month
            if len(parts) > 2:
                day = parts[2]
                if isinstance(day, int):
                    ret.day = day
    return ret


def set_csljson_dates(dest: CslJson, src: BiblioRefItem) -> None:
    if src.date:
        dest['issued'] = csljson_from_date(src.date)
    if src.access_date:
        dest['accessed'] = csljson_from_date(src.access_date)


def set_ref_item_dates(dest: BiblioRefItem, src: CslJson) -> None:
    if issued := date_from_csljson(src.get('issued')):
        dest.date = issued
    if accessed := date_from_csljson(src.get('accessed')):
        dest.access_date = accessed


def csljson_from_person_group(src: bp.PersonGroup) -> JsonData:
    ret = list['JsonData']()
    for person in src.persons:
        a: dict[str, JsonData] = {}
        if isinstance(person, bp.PersonName):
            if person.surname:
                a['family'] = person.surname
            if person.given_names:
                a['given'] = person.given_names
        else:
            assert_type(person, str)
            a['literal'] = person
        ret.append(a)
    if src.etal:
        ret.append({'literal': 'others'})
    return ret


def person_group_from_csljson(src: JsonData) -> bp.PersonGroup | None:
    if not isinstance(src, list):
        return None
    ret = bp.PersonGroup()
    for person in src:
        if isinstance(person, dict):
            str_name = get_str_or_none(person, 'literal')
            if str_name is not None:
                if str_name == 'others':
                    ret.etal = True
                else:
                    ret.persons.append(str_name)
            else:
                family = get_str_or_none(person, 'family')
                given = get_str_or_none(person, 'given')
                if family is None and given is None:
                    msg = f"CSLJSON missing literal, family, or given value: {person}"
                    ValueError(msg)
                ret.persons.append(bp.PersonName(family, given))
        else:
            ValueError(f"Unrecognized CSLJSON: {person}")
    return ret


def set_csjson_persons(dest: CslJson, src: BiblioRefItem) -> None:
    if src.authors:
        dest['author'] = csljson_from_person_group(src.authors)
    if src.editors:
        dest['editor'] = csljson_from_person_group(src.editors)


def set_ref_item_persons(dest: BiblioRefItem, src: CslJson) -> None:
    if group := person_group_from_csljson(src.get('author')):
        dest.authors = group
    if group := person_group_from_csljson(src.get('editor')):
        dest.editors = group


def set_csljson_pages(dest: CslJson, src: BiblioRefItem) -> None:
    if fpage := src.biblio_fields.get('fpage'):
        page = fpage
        if lpage := src.biblio_fields.get('lpage'):
            page += f"-{lpage}"
        dest['page'] = page


def set_ref_item_pages(dest: BiblioRefItem, src: CslJson) -> None:
    if page := get_str_or_none(src, 'page'):
        pages = page.split('-')
        dest.biblio_fields['fpage'] = pages[0]
        if len(pages) > 1:
            dest.biblio_fields['lpage'] = pages[1]


def csljson_from_ref_item(src: BiblioRefItem) -> CslJson:
    ret = dict[str, 'JsonData']()
    ret['type'] = ''
    ret['id'] = src.id
    for jats_key, value in src.biblio_fields.items():
        if csl_key := JATS_TO_CSL_VAR.get(jats_key):
            ret[csl_key] = value
    set_csljson_titles(ret, src)
    set_csljson_dates(ret, src)
    set_csjson_persons(ret, src)
    set_csljson_pages(ret, src)
    if src.edition is not None:
        ret['edition'] = str(src.edition)
    for pub_id_type, value in src.pub_ids.items():
        ret[pub_id_type.upper()] = value
    return ret


def csljson_refs_from_baseprint(src: dom.Article) -> list[CslJson] | None:
    if not src.ref_list:
        return None
    return [csljson_from_ref_item(r) for r in src.ref_list.references]


def ref_item_from_csljson(csljson: JsonData) -> BiblioRefItem | None:
    if not isinstance(csljson, dict):
        return None
    ret = BiblioRefItem()
    ret.id = str(csljson.get('id', ''))
    for jats_key, csl_key in JATS_TO_CSL_VAR.items():
        value = csljson.get(csl_key)
        if isinstance(value, str):
            ret.biblio_fields[jats_key] = value
        elif value is not None:
            warn(f"CSLJSON entry {csl_key} is not of string type")
    set_ref_item_titles(ret, csljson)
    set_ref_item_dates(ret, csljson)
    set_ref_item_persons(ret, csljson)
    if edition := get_str_or_none(csljson, 'edition'):
        ret.edition = int(edition)
    set_ref_item_pages(ret, csljson)
    for pub_id_type in bp.PubIdType:
        pub_id = get_str_or_none(csljson, pub_id_type.upper())
        if pub_id is not None:
            ret.pub_ids[pub_id_type] = pub_id
    return ret


def ref_list_from_csljson(csljson: JsonData) -> dom.BiblioRefList | None:
    if not isinstance(csljson, list):
        return None
    ret = dom.BiblioRefList()
    for j_item in csljson:
        if r_item := ref_item_from_csljson(j_item):
            ret.references.append(r_item)
    return ret


class BiblioFormatter(ABC):
    @abstractmethod
    def to_element(self, refs: Sequence[BiblioRefItem]) -> XmlElement: ...


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


def htmlize_csljson(jd: CslJson) -> CslJson:
    for key, value in jd.items():
        if isinstance(value, str):
            value = escape(value, quote=False)
            match key:
                case 'URL':
                    value = hyperlink(value)
                case 'DOI':
                    value = hyperlink(value, "https://doi.org/")
            jd[key] = value
    return {k: v for k, v in jd.items() if v is not None}


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
        from .parse.baseprint import get_ET

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

    def to_element(self, refs: Sequence[BiblioRefItem]) -> XmlElement:
        import citeproc

        csljson = [htmlize_csljson(csljson_from_ref_item(r)) for r in refs]
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

    def to_str(self, refs: Sequence[BiblioRefItem]) -> str:
        e = self.to_element(refs)
        ret = self._ET.tostring(e, encoding='unicode', method='html')
        return ret  # type: ignore[no-any-return]
