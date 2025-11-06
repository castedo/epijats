from __future__ import annotations

from typing import TYPE_CHECKING

from .. import condition as fc
from .. import dom
from .. import metadata as bp
from ..biblio import edition_int_or_none
from ..tree import StartTag

from .content import ArrayContentSession
from . import kit
from .kit import Log, LoaderTagModel as tag_model
from .tree import TrivialElementModel

if TYPE_CHECKING:
    from ..typeshed import XmlElement


def load_person_name(log: Log, e: XmlElement) -> bp.PersonName | None:
    kit.check_no_attrib(log, e)
    sess = ArrayContentSession()
    surname = sess.one(tag_model('surname', kit.load_string))
    given_names = sess.one(tag_model('given-names', kit.load_string))
    suffix = sess.one(tag_model('suffix', kit.load_string))
    sess.parse_content(log, e)
    if not surname.out and not given_names.out:
        log(fc.MissingContent.issue(e, "Missing surname or given-names element."))
        return None
    return bp.PersonName(surname.out, given_names.out, suffix.out)


class PersonGroupModel(kit.TagModelBase[bp.PersonGroup]):
    """<person-group> Person Group for a Cited Publication
    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/person-group.html
    """

    def __init__(self, group_type: str) -> None:
        super().__init__(StartTag('person-group', {'person-group-type': group_type}))

    def load(self, log: Log, e: XmlElement) -> bp.PersonGroup | None:
        ret = bp.PersonGroup()
        k = 'person-group-type'
        kit.check_no_attrib(log, e, [k])
        sess = ArrayContentSession()
        sess.bind(tag_model('name', load_person_name), ret.persons.append)
        sess.bind(tag_model('string-name', kit.load_string), ret.persons.append)
        etal = sess.one(TrivialElementModel('etal'))
        sess.parse_content(log, e)
        ret.etal = bool(etal.out)
        return ret


class PositiveIntModel(kit.LoadModelBase[int]):
    def __init__(self, tag: str, max_int: int, *, strip_trailing_period: bool = False):
        self.tag = tag
        self.max_int = max_int
        self.strip_trailing_period = strip_trailing_period

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == self.tag

    def load(self, log: Log, e: XmlElement) -> int | None:
        kit.check_no_attrib(log, e)
        ret = kit.load_int(log, e, strip_trailing_period=self.strip_trailing_period)
        if ret and ret not in range(1, self.max_int + 1):
            log(fc.UnsupportedAttributeValue.issue(e, self.tag, str(ret)))
            ret = None
        return ret


class DateBuilder:
    def __init__(self, sess: ArrayContentSession):
        self.year = sess.one(tag_model('year', kit.load_int))
        self.month = sess.one(PositiveIntModel('month', 12))
        self.day = sess.one(PositiveIntModel('day', 31))

    def build(self) -> bp.Date | None:
        ret = None
        if self.year.out:
            ret = bp.Date(self.year.out)
            if self.month.out:
                ret.month = self.month.out
                if self.day.out:
                    ret.day = self.day.out
        return ret


class AccessDateModel(kit.TagModelBase[bp.Date]):
    """<date-in-citation> Date within a Citation

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/date-in-citation.html
    """

    def __init__(self) -> None:
        super().__init__('date-in-citation')

    def load(self, log: Log, xe: XmlElement) -> bp.Date | None:
        kit.check_no_attrib(log, xe, ['content-type'])
        if xe.attrib.get('content-type') != 'access-date':
            return None
        sess = ArrayContentSession()
        date = DateBuilder(sess)
        sess.parse_content(log, xe)
        return date.build()


class PubIdParser(kit.Parser[dict[bp.PubIdType, str]]):
    """<pub-id> Publication Identifier for a Cited Publication

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/pub-id.html
    """

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'pub-id'

    def parse(self, log: Log, e: XmlElement, dest: dict[bp.PubIdType, str]) -> bool:
        kit.check_no_attrib(log, e, ['pub-id-type'])
        pub_id_type = kit.get_enum_value(log, e, 'pub-id-type', bp.PubIdType)
        if not pub_id_type:
            log(fc.InvalidPubId.issue(e))
            return False
        if pub_id_type in dest:
            log(fc.ExcessElement.issue(e))
            return False
        value = kit.load_string_content(log, e)
        if not value:
            log(fc.MissingContent.issue(e))
            return False
        match pub_id_type:
            case bp.PubIdType.DOI:
                if not value.startswith("10."):
                    log(fc.InvalidDoi.issue(e, "DOIs begin with '10.'"))
                    https_prefix = "https://doi.org/"
                    if value.startswith(https_prefix):
                        value = value[len(https_prefix) :]
                    else:
                        return False
            case bp.PubIdType.PMID:
                try:
                    int(value)
                except ValueError as ex:
                    log(fc.InvalidPmid.issue(e, str(ex)))
                    return False
        dest[pub_id_type] = value
        return True


def load_edition(log: Log, e: XmlElement) -> int | None:
    for s in e:
        log(fc.UnsupportedElement.issue(s))
        if s.tail and s.tail.strip():
            log(fc.IgnoredText.issue(e))
    text = e.text or ""
    ret = edition_int_or_none(text)
    if ret is None:
        log(fc.InvalidInteger.issue(e, text))
    return ret


class SourceTitleModel(kit.LoadModelBase[str]):
    def match(self, xe: XmlElement) -> bool:
        # JATS/HTML conflict in use of <source> tag
        return xe.tag in ['source-title', 'source']

    def load(self, log: Log, xe: XmlElement) -> str | None:
        return kit.load_string(log, xe)


class ElementCitationParser(kit.Parser[bp.BiblioRefItem]):
    """<element-citation> Element Citation

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/element-citation.html
    """

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'element-citation'

    def parse(self, log: Log, e: XmlElement, dest: bp.BiblioRefItem) -> bool:
        kit.check_no_attrib(log, e)
        sess = ArrayContentSession()
        source_title = sess.one(SourceTitleModel())
        title = sess.one(tag_model('article-title', kit.load_string))
        authors = sess.one(PersonGroupModel('author'))
        editors = sess.one(PersonGroupModel('editor'))
        edition = sess.one(tag_model('edition', load_edition))
        date = DateBuilder(sess)
        access_date = sess.one(AccessDateModel())
        fields = {}
        for key in bp.BiblioRefItem.BIBLIO_FIELD_KEYS:
            fields[key] = sess.one(tag_model(key, kit.load_string))
        elocation_id = sess.one(tag_model('elocation-id', kit.load_string))
        sess.bind(PubIdParser(), dest.pub_ids)
        sess.parse_content(log, e)
        dest.source_title = source_title.out
        dest.article_title = title.out
        if authors.out:
            dest.authors = authors.out
        if editors.out:
            dest.editors = editors.out
        dest.edition = edition.out
        dest.date = date.build()
        dest.access_date = access_date.out
        for key, parser in fields.items():
            if parser.out:
                dest.biblio_fields[key] = parser.out
        if elocation_id.out:
            if 'fpage' in dest.biblio_fields:
                msg = "elocation-id dropped since fpage present"
                log(fc.ElementFormatCondition.issue(e, msg))
            else:
                dest.biblio_fields['fpage'] = elocation_id.out
        return True


class BiblioRefItemModel(kit.TagModelBase[bp.BiblioRefItem]):
    """<ref> Reference Item

    https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/ref.html
    """

    def __init__(self) -> None:
        super().__init__('ref')

    def load(self, log: Log, xe: XmlElement) -> bp.BiblioRefItem | None:
        ret = bp.BiblioRefItem()
        kit.check_no_attrib(log, xe, ['id'])
        sess = ArrayContentSession()
        label = PositiveIntModel('label', 1048576, strip_trailing_period=True)
        sess.one(label)  # ignoring if it's a valid integer
        sess.bind_once(ElementCitationParser(), ret)
        sess.parse_content(log, xe)
        ret.id = xe.attrib.get('id', "")
        return ret


class RefListModel(kit.TagModelBase[dom.BiblioRefList]):
    def __init__(self) -> None:
        super().__init__('ref-list')

    def load(self, log: Log, e: XmlElement) -> dom.BiblioRefList | None:
        ret = dom.BiblioRefList()
        kit.check_no_attrib(log, e)
        sess = ArrayContentSession()
        title = sess.one(tag_model('title', kit.load_string))
        sess.bind(BiblioRefItemModel(), ret.references.append)
        sess.parse_content(log, e)
        if title.out and title.out != "References":
            log(fc.IgnoredText.issue(e, 'ref-list/title ignored'))
        return ret
