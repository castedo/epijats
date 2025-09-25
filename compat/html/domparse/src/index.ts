#!/usr/bin/env node

import { program } from 'commander';
import { JSDOM } from 'jsdom';
import serialize from 'w3c-xmlserializer';
import fs from 'node:fs';

program
  .description("Test parse Baseprint XML with DOMParser")
  .option(
    '-i, --inpath <inpath>',
    'path to Baseprint XML file to parse',
    'baseprint/article.xml',
  );

program
  .parse(process.argv);

try {

  const data = fs.readFileSync(program.opts().inpath, 'utf8');
  const dom = new JSDOM(data);
  const { document } = dom.window;
  const article = document.body.firstElementChild;
  if (article) {
    const xmlText = serialize(article, { requireWellFormed: true });
    process.stdout.write(xmlText);
  }

} catch (err) {
  console.error(err);
}

