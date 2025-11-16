from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from .. import dom
from .. import condition as fc
from ..tree import (
    ArrayParent,
    Element,
    Parent,
)

from . import kit
from .kit import Log, Model
from .content import (
    ArrayContentModel,
    ArrayContentSession,
    DataContentModel,
)
from .tree import (
    DataParentModel,
    ElementLoadModelBase,
    EmptyElementModel,
    TagModel,
)

if TYPE_CHECKING:
    from ..typeshed import XmlContent, XmlElement


class TableCellModel(kit.LoadModelBase[dom.TableCell]):
    def __init__(self, content_model: ArrayContentModel, *, header: bool):
        self.header = header
        self.tag = 'th' if header else 'td'
        self.content_model = content_model
        self._ok_attrib_keys = {'align', 'colspan', 'rowspan'}

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == self.tag

    def load(self, log: Log, e: XmlElement) -> dom.TableCell | None:
        align_attribs = {'left', 'right', 'center', 'justify', None}
        kit.confirm_attrib_value(log, e, 'align', align_attribs)
        ret = dom.TableCell(header=self.header)
        for key, value in e.attrib.items():
            if key in self._ok_attrib_keys:
                ret.set_attrib(key, value)
            else:
                log(fc.UnsupportedAttribute.issue(e, key))
        self.content_model.parse_content(log, e, ret.append)
        return ret


class TableColumnGroupModel(ElementLoadModelBase[dom.TableColumnGroup]):
    def __init__(self) -> None:
        tm = TagModel(dom.TableColumnGroup, optional_attrib={'span', 'width'})
        super().__init__(tm)
        col = EmptyElementModel(
            TagModel(dom.TableColumn, optional_attrib={'span', 'width'})
        )
        self.content_model = DataContentModel(col)

    def parse_content(
        self, log: Log, xc: XmlContent, dest: Parent[dom.TableColumn]
    ) -> None:
        self.content_model.parse_content(log, xc, dest.append)


class TableRowModel(ElementLoadModelBase[dom.TableRow]):
    def __init__(self, cell_content: ArrayContentModel):
        super().__init__(TagModel(dom.TableRow))
        th = TableCellModel(cell_content, header=True)
        td = TableCellModel(cell_content, header=False)
        self.content_model = DataContentModel(th | td)

    def parse_content(
        self, log: Log, xc: XmlContent, dest: Parent[dom.TableCell]
    ) -> None:
        self.content_model.parse_content(log, xc, dest.append)


RowParentT = TypeVar('RowParentT', bound=Parent[dom.TableRow])


class RowParentModel(ElementLoadModelBase[RowParentT]):
    def __init__(
        self, tag_model: TagModel[RowParentT], child_model: Model[dom.TableRow]
    ):
        super().__init__(tag_model)
        self.content_model = DataContentModel(child_model)

    def parse_content(
        self, log: Log, xc: XmlContent, dest: Parent[dom.TableRow]
    ) -> None:
        self.content_model.parse_content(log, xc, dest.append)


class TableModel(kit.LoadModelBase[dom.Table]):
    def __init__(self, cell_content: ArrayContentModel):
        tr = TableRowModel(cell_content)
        self.colgroups = TableColumnGroupModel()
        self.thead = RowParentModel(TagModel(dom.TableHead), tr)
        self.tbody = RowParentModel(TagModel(dom.TableBody), tr)
        self.tfoot = RowParentModel(TagModel(dom.TableFoot), tr)

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'table'

    def load(self, log: Log, xe: XmlElement) -> dom.Table | None:
        attribs = {'frame', 'rules'}
        kit.check_no_attrib(log, xe, attribs)
        ret = dom.Table()
        for key, value in xe.attrib.items():
            if key not in attribs:
                log(fc.UnsupportedAttribute.issue(xe, key))
            else:
                ret.set_attrib(key, value)
        sess = ArrayContentSession()
        sess.bind(self.colgroups, ret.colgroups.append)
        head = sess.one(self.thead)
        foot = sess.one(self.tfoot)
        sess.bind(self.tbody, ret.bodies.append)
        sess.parse_content(log, xe)
        ret.head = head.out
        ret.foot = foot.out
        return ret


def data_element_model(tag: str, child_model: Model[Element]) -> Model[Element]:
    return DataParentModel(TagModel(ArrayParent, tag=tag), child_model)


def table_or_wrap_model(cell_content: ArrayContentModel) -> Model[Element]:
    table = TableModel(cell_content)
    return data_element_model('table-wrap', table) | table
