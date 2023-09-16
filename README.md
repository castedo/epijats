epijats
=======

`epijats` converts [baseprint](https://baseprints.singlesource.pub)
JATS XML to PDF in three independent stages:

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
                   [--to {json,yaml,jsoml,html,html+pdf,pdf}] [--no-web-fonts]
                   inpath outpath

Eprint JATS

positional arguments:
  inpath                input directory/path
  outpath               output directory/path

options:
  -h, --help            show this help message and exit
  --from {jats,json,yaml,jsoml,html}
                        format of source
  --to {json,yaml,jsoml,html,html+pdf,pdf}
                        format of target
  --no-web-fonts        Do not use online web fonts
```


Installation
------------

```
python3 -m pip install epijats[format1,format2,...]
```
where each `formatN` etc.. is one of `jats`, `html`, `pdf`, `yaml`, or `jsoml`.
Json support is automatic.


### Non-Python requirements

If you are converting from JATS, the following dependencies must be installed:

<ul>
  <li> <a href="https://pandoc.org">pandoc</a>
  <li> pandoc-katex-filter Node.js NPM package
  <li> git
</ul>

All other dependencies will be automatically installed by `pip`.
