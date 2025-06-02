epijats
=======

`epijats` converts [baseprint](https://baseprints.singlesource.pub)
JATS XML to PDF in three independent stages:

```
          JATS
Stage 1:   ▼
          "webstract" interchange format (json)
Stage 2:   ▼
          HTML
Stage 3:   ▼
          PDF
```

Using the `epijats` command line tool, you can start and stop at any stage with the
`--from` and `--to` command line options. The output of `epijats --help` is:

```
usage: __main__.py [-h] [--from {jats,json,html}]
                   [--to {jats,json,html,html+pdf,pdf}] [--no-web-fonts]
                   inpath outpath

Eprint JATS

positional arguments:
  inpath                input directory/path
  outpath               output directory/path

options:
  -h, --help            show this help message and exit
  --from {jats,json,html}
                        format of source
  --to {jats, json,html,html+pdf,pdf}
                        format of target
  --no-web-fonts        Do not use online web fonts
```


Installation
------------

```
python3 -m pip install epijats[pdf]
```
with the `[pdf]` suffix optional and only needed of PDF generation.
