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
python3 -m epijats git+https://gitlab.com/perm.pub/epijats.git
```

#### Requirements per format

Different dependencies are required depending on which formats are processed.

JATS
: [pandoc](https://pandoc.org)
: `elifetools` Python package
: `pandoc-katex-filter` Node.js NPM package
: GitPython Python package

YAML
: `ruamel.yaml` Python package

JSOML
: [`jsoml`](gitlab.org/castedo/jsoml) Python package

HTML
: `jinja2` Python package

PDF
: `weasyprint` Python package
: `jinja2` Python package

