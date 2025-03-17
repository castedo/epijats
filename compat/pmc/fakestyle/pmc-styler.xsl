<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">

  <xsl:output method="xml" encoding="UTF-8"
    doctype-public="-//NLM//DTD JATS (Z39.96) Journal Archiving and Interchange DTD with MathML3 v1.3 20210610//EN"
    doctype-system="https://jats.nlm.nih.gov/archiving/1.3/JATS-archivearticle1-3-mathml3.dtd"/>

  <xsl:template name="new-journal-meta">
    <journal-meta>
      <journal-id journal-id-type="archive">JJXT</journal-id>
      <journal-title-group>
        <journal-title>Journal of JATS XML Testing</journal-title>
      </journal-title-group>
      <issn pub-type="epub">0000-0000</issn>
      <publisher>
        <publisher-name>Random Madhouse</publisher-name>
      </publisher>
    </journal-meta>
  </xsl:template>

  <xsl:template name="new-article-categories">
    <article-categories>
      <subj-group subj-group-type="heading">
        <subject>JATS</subject>
      </subj-group>
    </article-categories>
  </xsl:template>

  <xsl:template name="new-pub-date">
    <pub-date pub-type="pub">
      <year>1700</year>
    </pub-date>
  </xsl:template>

  <xsl:template name="new-elocation-id">
    <elocation-id>0</elocation-id>
  </xsl:template>

  <!-- default transformation: just copy nodes and attributes -->
  <xsl:template match="* | @*">
    <xsl:copy>
      <xsl:apply-templates select="@*"/>
      <xsl:apply-templates/>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="/article">
    <xsl:copy>
      <xsl:apply-templates select="@*" />
      <xsl:if test="not(@article-type)">
        <xsl:attribute name="article-type">other</xsl:attribute>
      </xsl:if>
      <xsl:apply-templates/>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="/article/front">
    <xsl:copy>
      <xsl:apply-templates select="@*"/>
      <xsl:if test="not(journal-meta)">
        <xsl:call-template name="new-journal-meta"/>
      </xsl:if>
      <xsl:apply-templates/>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="/article/front/article-meta">
    <xsl:copy>
      <xsl:apply-templates select="@*"/>
      <xsl:if test="not(article-categories)">
        <xsl:call-template name="new-article-categories"/>
      </xsl:if>
      <xsl:apply-templates select="title-group | contrib-group"/>
      <xsl:if test="not(pub-date)">
        <xsl:call-template name="new-pub-date"/>
      </xsl:if>
      <xsl:if test="not(elocation-id)">
        <xsl:call-template name="new-elocation-id"/>
      </xsl:if>
      <xsl:apply-templates select="*[not(self::title-group | self::contrib-group)]"/>
    </xsl:copy>
  </xsl:template>

</xsl:stylesheet>
