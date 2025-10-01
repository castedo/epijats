from __future__ import annotations

import tempfile
from pathlib import Path

from epijats import dom, write_baseprint


def read_article_xml(art: dom.Article) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        write_baseprint(art, tmpdir)
        with open(Path(tmpdir) / "article.xml") as f:
            return f.read()


def test_simple_title():
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
