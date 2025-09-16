const parser = new DOMParser();
const xsltProcessor = new XSLTProcessor();
const serializer = new XMLSerializer();

const baseprintXMLToHTML = `<xsl:transform version="1.0"
  xmlns:ali="http://www.niso.org/schemas/ali/1.0/"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="html" encoding="UTF-8"/>

    <!-- JATS tag names that do not interoperate HTML/CSS -->
    <xsl:template match="body">
      <jats-body><xsl:apply-templates/></jats-body>
    </xsl:template>
    <xsl:template match="source">
      <jats-source><xsl:apply-templates/></jats-source>
    </xsl:template>
    <xsl:template match="ali:license_ref">
      <license_ref><xsl:apply-templates/></license_ref>
    </xsl:template>

    <!-- JATS tag names also used in HTML with negligible issues -->
    <xsl:template match="article|code|p|sub|sup|title">
      <xsl:copy>
        <xsl:apply-templates/>
      </xsl:copy>
    </xsl:template>

    <!-- the rest of the JATS tag names -->
    <xsl:template match="abstract|article-meta|article-title|back|comment|copyright-statement|contrib|contrib-id|date-in-citation|day|contrib-group|edition|element-citation|email|etal|front|given-names|license|license-p|month|name|pub-id|permissions|person-group|ref|ref-list|string-name|suffix|surname|title-group|xref">
      <xsl:copy>
        <xsl:copy-of select="@*"/>
        <xsl:apply-templates/>
      </xsl:copy>
    </xsl:template>

    <!-- HTML tag names not used in JATS -->
    <xsl:template match="a">
      <a>
        <xsl:copy-of select="@href"/>
        <xsl:copy-of select="@rel"/>
        <xsl:apply-templates/>
      </a>
    </xsl:template>
    <xsl:template match="section">
      <xsl:copy>
        <xsl:copy-of select="@id"/>
        <xsl:apply-templates/>
      </xsl:copy>
    </xsl:template>
    <xsl:template match="b|blockquote|br|dd|div|dl|dt|i|li|h2|h3|h4|h5|h6|ol|pre|ul|tt">
      <xsl:copy><xsl:apply-templates/></xsl:copy>
    </xsl:template>
  </xsl:transform>
`;

export function parseXML(xmlText) {
  const dom = parser.parseFromString(xmlText, "application/xml");
  if (dom.getElementsByTagName('parsererror').length) {
    return { error: serializer.serializeToString(dom) };
  }
  return { dom };
}

export function transformXML(xmlText) {
  const xml = parseXML(xmlText);
  if (xml.error) {
    return { error: "Error parsing XML:\n" + xml.error };
  }
  const xsl = parseXML(baseprintXMLToHTML);
  if (xsl.error) {
    return { error: "Error parsing XSL.\n\n" + xsl.error };
  }
  xsltProcessor.importStylesheet(xsl.dom);
  const dom = xsltProcessor.transformToFragment(xml.dom, document);
  return { dom };
}

export async function fetchBaseprintHTML(resource) {
  const resp = await fetch(resource);
  if (!resp.ok) {
    return { error: `HTTP ${resp.status} ${resp.statusText} ${resp.url}` }
  }
  return transformXML(await resp.text());
}
