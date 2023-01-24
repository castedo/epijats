epijats
=======

`epijats` converts a primitive JATS XML to PDF in three independent stages:

```
          JATS
Stage 1:   ▼
          "webstract" interchange format (json, yaml, or jsoml)
Stage 2:   ▼
          HTML
Stage 3:   ▼
          PDF
```

Using the `epijats` command line tool, you can start and stop at any stage with the
`--from` and `--to` command line options. The output of `epijats --help` is:

```
usage: __main__.py [-h] [--from {jats,json,yaml,jsoml,html}]
                   [--to {json,yaml,jsoml,html,pdf}] [--no-web-fonts]
                   [--style {boston,lyon}]
                   inpath outpath

Eprint JATS

positional arguments:
  inpath                input directory/path
  outpath               output directory/path

options:
  -h, --help            show this help message and exit
  --from {jats,json,yaml,jsoml,html}
                        format of source
  --to {json,yaml,jsoml,html,pdf}
                        format of target
  --no-web-fonts        Do not use online web fonts
  --style {boston,lyon}
                        Article style
```



Installation
------------

```
python3 -m pip install git+https://gitlab.com/perm.pub/epijats.git
```

#### Requirements per format

Different dependencies are required depending on which formats are processed.

<dl>
<dt>JATS</dt>
<dd><ul>
  <li> [pandoc](https://pandoc.org)
  <li> elifetools Python package
  <li> pandoc-katex-filter Node.js NPM package
  <li> GitPython Python package
</ul></dd>
<dt>YAML</dt>
<dd><ul>
  <li> ruamel.yaml Python package
</ul></dd>
<dt>JSOML</dt>
<dd><ul>
  <li> [jsoml](gitlab.org/castedo/jsoml) Python package
</ul></dd>
<dt>HTML</dt>
<dd><ul>
  <li> jinja2 Python package
</ul><dd>
<dt>PDF</dt>
<dd><ul>
  <li> weasyprint Python package
  <li> jinja2 Python package
</ul></dd>
</dl>
