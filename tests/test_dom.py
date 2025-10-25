from __future__ import annotations

import tempfile
from pathlib import Path

from epijats import dom, write_baseprint
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
    art.title = dom.MixedContent("Do <b>not</b> tag me!")
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


def test_mixed_content() -> None:
    div = dom.MarkupBlock()
    mc = div.content
    mc.append_text("hi")
    mc.append(dom.MarkupElement('b', "ya"))
    mc.append(dom.IssueElement("serious"))
    assert len(list(mc)) == 2
    expect = "<div>hi<b>ya</b><format-issue>serious</format-issue></div>"
    assert XML.to_str(div) == expect


def test_author():
    me = dom.Orcid.from_url("https://orcid.org/0000-0002-5014-4809")
    assert me.as_19chars() == "0000-0002-5014-4809"
    name = dom.PersonName("Pane", "Roy", "Senior")
    dom.Author(name, "joy@pane.com", me)


def test_permissions() -> None:
    license = dom.License()
    license.license_p.append_text("whatever")
    license.license_ref = 'https://creativecommons.org/licenses/by-nd/'
    license.cc_license_type = dom.CcLicenseType.from_url(license.license_ref)
    copyright = dom.Copyright()
    copyright.statement.append_text("Mine!")
    permissions = dom.Permissions(license, copyright)
    assert not permissions.blank()


def test_inline_elements() -> None:
    mc = dom.MixedContent()
    mc.append_text("0")
    mc.append(dom.LineBreak())
    mc.append_text("1")
    mc.append(dom.WordBreak())
    mc.append_text("2")
    assert HTML.content_to_str(mc) == "0<br>1<wbr>2"


def test_block_elements() -> None:
    bq = dom.BlockQuote()
    bq.content.append(dom.HorizontalRule())
    assert XML.to_str(bq) == """\
<blockquote>
  <hr />
</blockquote>"""
