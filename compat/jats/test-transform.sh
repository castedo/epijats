#!/usr/bin/bash
set -o errexit

SCRIPT_LOCATION=$(dirname "$0")
BASEPRINT_XML=$SCRIPT_LOCATION/kitchen_sink_baseprint/article.xml
EXPECTED_JATS_XML=$SCRIPT_LOCATION/expected_jats.xml

echo "Transforming $BASEPRINT_XML to $EXPECTED_JATS_XML."

xsltproc $SCRIPT_LOCATION/baseprint-to-jats.xsl $BASEPRINT_XML | xmllint --format - > $EXPECTED_JATS_XML
