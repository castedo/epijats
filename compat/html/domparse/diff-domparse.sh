#!/usr/bin/bash
set -o errexit -o nounset -o pipefail

if [[ ! -v 1 ]]; then
    COMMAND=$'\u001b[1m'$(basename "$0")$'\u001b[0m'
    echo "Usage:"
    echo "  $COMMAND baseprint_xml_file_path"
fi

# Slow alternative without build:
# npx ts-node src/index.ts --inpath $1 \

# Faster alternative after 'npm run build':

npx domparse --inpath $1 \
  | sed 's/ xmlns="http:\/\/www.w3.org\/1999\/xhtml"//' \
  | xmllint --encode ascii - \
  | sed -E 's/<(\w+)\/>/<\1 \/>/g' \
  | tail -n +2 \
  | diff --report-identical-files - $1
