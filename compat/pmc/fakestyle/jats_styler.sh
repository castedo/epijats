#!/usr/bin/bash
set -o errexit

print_usage() {
    THIS_SCRIPT=$'\u001b[1m'"$(basename $0)"$'\u001b[0m'
    echo "Usage:"
    echo "  $THIS_SCRIPT baseprint_xml_file"
    echo "    to transform a Baseprints XML file into PMC JATS XML style."
}

SCRIPT_LOCATION=$(dirname "$0")

if [[ -z "$1" ]]; then
  print_usage
  exit 2
fi

xsltproc $SCRIPT_LOCATION/pmc-styler.xsl $1 | xmllint --format -
