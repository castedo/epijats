#!/usr/bin/env node

import fs from 'node:fs';
import { program } from 'commander';
import { JSDOM } from 'jsdom';
import serialize from 'w3c-xmlserializer';

const { window } = new JSDOM("<!doctype html><title>Mock reader app</title>");


program
  .description("Test parse Baseprint XML with DOMParser")
  .option(
    '-i, --inpath <inpath>',
    'path to Baseprint XML file to parse',
    'baseprint/article.xml',
  );

program.parse(process.argv);


try {

  const data = fs.readFileSync(program.opts().inpath, 'utf8');
  const parser = new window.DOMParser();
  const dom = parser.parseFromString(data, "text/html");
  const article = dom.body.firstElementChild;
  if (article) {
    const xmlText = serialize(article, { requireWellFormed: true });
    process.stdout.write(xmlText);
    process.stdout.write("\n");
  }

} catch (err) {
  console.error(err);
}

