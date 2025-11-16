from __future__ import annotations

import tempfile
from pathlib import Path

from epijats import dom, write_baseprint, SimpleFormatCondition
from epijats.xml.format import XmlFormatter
from epijats.xml.html import HtmlGenerator


XML = XmlFormatter(use_lxml=False)
HTML = HtmlGenerator()


def read_article_xml(art: dom.Article) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        write_baseprint(art, tmpdir)
        with open(Path(tmpdir) / "article.xml") as f:
            return f.read()


def test_simple_title() -> None:
    art = dom.Article()
    art.title = dom.MutableMixedContent("Do <b>not</b> tag me!")
    got = read_article_xml(art)
    assert got == """\
<article>
  <front>
    <article-meta>
      <title-group>
        <article-title>Do &lt;b&gt;not&lt;/b&gt; tag me!</article-title>
      </title-group>
    </article-meta>
  </front>
</article>
"""


def test_article_issues() -> None:
    art = dom.Article()
    div = dom.MarkupBlock()
    div.append("Something ")
    div.append(SimpleFormatCondition.issue("serious"))
    div.append(" happened.")
    art.body.presection.append(div)
    got = read_article_xml(art)
    assert got == """\
<article>
  <article-body>
    <div>Something  happened.</div>
  </article-body>
</article>
"""
    conditions = [i.condition for i in art.issues]
    assert conditions == [SimpleFormatCondition()]


def test_mixed_content() -> None:
    div = dom.MarkupBlock()
    div.append("hi")
    div.append(dom.MarkupInline('b', "ya"))
    div.append(SimpleFormatCondition.issue("serious"))
    expect_xml = "<div>hi<b>ya</b></div>"
    assert XML.to_str(div) == expect_xml
    expect_html = (
        '<div>hi<strong>ya</strong>'
        '<output class="format-issue">Format condition: serious</output>'
        '</div>'
    )
    assert HTML.elements_to_str([div]) == expect_html


def test_author():
    me = dom.Orcid.from_url("https://orcid.org/0000-0002-5014-4809")
    assert me.as_19chars() == "0000-0002-5014-4809"
    name = dom.PersonName("Pane", "Roy", "Senior")
    dom.Author(name, "joy@pane.com", me)


def test_permissions() -> None:
    license = dom.License()
    license.license_p.append("whatever")
    license.license_ref = 'https://creativecommons.org/licenses/by-nd/'
    license.cc_license_type = dom.CcLicenseType.from_url(license.license_ref)
    copyright = dom.Copyright()
    copyright.statement.append("Mine!")
    permissions = dom.Permissions(license, copyright)
    assert not permissions.blank()


def test_inline_elements() -> None:
    mc = dom.MutableMixedContent()
    mc.append("0")
    mc.append(dom.LineBreak())
    mc.append("1")
    mc.append(dom.WordBreak())
    mc.append("2")
    assert HTML.content_to_str(mc) == "0<br>1<wbr>2"


def test_block_element() -> None:
    bq = dom.BlockQuote()
    bq.append(dom.HorizontalRule())
    assert XML.to_str(bq) == """\
<blockquote>
  <hr />
</blockquote>"""


def test_dlist_element() -> None:
    dt = dom.DTerm('0')
    dd = dom.DDefinition([dom.MarkupBlock('nada')])
    di = dom.DItem(dt, [dd])
    dl = dom.DList([di])
    assert XML.to_str(dl) == """\
<dl>
  <div>
    <dt>0</dt>
    <dd>nada</dd>
  </div>
</dl>"""
