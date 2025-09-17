epijats
=======

`epijats` converts [Baseprint](https://baseprints.singlesource.pub)
XML to HTML/PDF in three independent stages:

```
          XML (Baseprint or JATS)
Stage 1:   ▼
          Baseprint XML
Stage 2:   ▼
          HTML
Stage 3:   ▼
          PDF
```

Choose `--to=xml` to reformat XML input to Baseprint XML output.

```
usage: epijats [-h] [--version] [--to {xml,html,html+pdf,pdf}] [--no-web-fonts]
               inpath outpath

Eprint JATS

positional arguments:
  inpath                input directory/path
  outpath               output directory/path

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  --to {xml,html,html+pdf,pdf}
                        format of target
  --no-web-fonts        Do not use online web fonts
```


Installation
------------

```
python3 -m pip install epijats[pdf]
```
with the `[pdf]` suffix optional and only needed of PDF generation.


Option Trade-offs
-----------------

### `--no-web-fonts`

<dl>
  <dt> Advantages: </dt>
  <dd>
+ works offline
  </dd>
  <dt> Disadvantages: </dt>
  <dd>
- fonts need to be installed locally<br>
- font rendering may vary
  </dd>
</dl>
