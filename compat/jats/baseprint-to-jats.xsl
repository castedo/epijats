<xsl:stylesheet
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    xmlns:ali="http://www.niso.org/schemas/ali/1.0/"
    version="1.0">

  <xsl:output
    method="xml"
    doctype-public="-//NLM//DTD JATS (Z39.96) Journal Archiving and Interchange DTD with MathML3 v1.3 20210610//EN"
    doctype-system="JATS-archivearticle1-3-mathml3.dtd"/>

  <!-- default transformation: just copy nodes and attributes -->
  <xsl:template match="* | @*">
    <xsl:copy>
      <xsl:apply-templates select="node()|@*"/>
    </xsl:copy>
  </xsl:template>

  <!-- add required <atricle> attributes -->
  <xsl:template match="/article">
    <article xmlns:xlink="http://www.w3.org/1999/xlink" article-type="other">
      <xsl:apply-templates/>
    </article>
  </xsl:template>


  <!-- rename HTML-compatible tags to HTML-incompatible JATS counterparts -->

  <xsl:template match="article-body">
    <body>
      <xsl:apply-templates/>
    </body>
  </xsl:template>

  <xsl:template match="source-title">
    <source>
      <xsl:apply-templates/>
    </source>
  </xsl:template>


  <!-- Rename HTML elements to JATS counterparts -->

  <xsl:template match="a[@rel='external']">
    <ext-link ext-link-type="uri" xlink:href="{@href}">
      <xsl:apply-templates/>
    </ext-link>
  </xsl:template>

  <xsl:template match="a">
    <xref>
      <xsl:attribute name="rid">
        <xsl:value-of select="substring(@href, 2)"/>
      </xsl:attribute>
      <xsl:apply-templates/>
    </xref>
  </xsl:template>

  <xsl:template match="b">
    <bold>
      <xsl:apply-templates/>
    </bold>
  </xsl:template>

  <xsl:template match="blockquote">
    <disp-quote>
      <xsl:apply-templates/>
    </disp-quote>
  </xsl:template>

  <xsl:template match="br">
    <break/>
  </xsl:template>

  <xsl:template match="i">
    <italic>
      <xsl:apply-templates/>
    </italic>
  </xsl:template>

  <xsl:template match="pre">
    <preformat>
      <xsl:apply-templates/>
    </preformat>
  </xsl:template>

  <xsl:template match="tt">
    <monospace>
      <xsl:apply-templates/>
    </monospace>
  </xsl:template>


  <!-- Rename HTML section and heading elements to JATS -->

  <xsl:template match="section">
    <sec>
      <xsl:copy-of select="@id"/>
      <xsl:apply-templates/>
    </sec>
  </xsl:template>

  <xsl:template match="h1|h2|h3|h4|h5|h6">
    <title>
      <xsl:apply-templates/>
    </title>
  </xsl:template>


  <!-- Rename HTML list elements to JATS counterparts -->

  <xsl:template match="li">
    <list-item>
      <xsl:apply-templates/>
    </list-item>
  </xsl:template>

  <xsl:template match="ol">
    <list list-type="order">
      <xsl:apply-templates/>
    </list>
  </xsl:template>

  <xsl:template match="ul">
    <list list-type="bullet">
      <xsl:apply-templates/>
    </list>
  </xsl:template>


  <!-- Rename HTML description list elements to JATS counterparts -->

  <xsl:template match="dd">
    <def>
      <xsl:apply-templates/>
    </def>
  </xsl:template>

  <xsl:template match="dl">
    <def-list>
      <xsl:apply-templates/>
    </def-list>
  </xsl:template>

  <xsl:template match="dl/div">
    <def-item>
      <xsl:apply-templates/>
    </def-item>
  </xsl:template>

  <xsl:template match="dt">
    <term>
      <xsl:apply-templates/>
    </term>
  </xsl:template>


  <!-- Move required <def> children under non-HTML JATS <p> child element -->

  <xsl:template match="dd/code">
    <p>
      <code>
        <xsl:apply-templates/>
      </code>
    </p>
  </xsl:template>

  <xsl:template match="dd/dl">
    <p>
      <def-list>
        <xsl:apply-templates/>
      </def-list>
    </p>
  </xsl:template>

  <xsl:template match="dd/blockquote">
    <p>
      <disp-quote>
        <xsl:apply-templates/>
      </disp-quote>
    </p>
  </xsl:template>

  <xsl:template match="dd/ol">
    <p>
      <list list-type="order">
        <xsl:apply-templates/>
      </list>
    </p>
  </xsl:template>

  <xsl:template match="dd/ul">
    <p>
      <list>
        <xsl:apply-templates/>
      </list>
    </p>
  </xsl:template>

  <xsl:template match="dd/pre">
    <p>
      <preformat>
        <xsl:apply-templates/>
      </preformat>
    </p>
  </xsl:template>


  <!-- Move required <list-item> children under non-HTML JATS <p> child element -->

  <xsl:template match="li/code">
    <p>
      <code>
        <xsl:apply-templates/>
      </code>
    </p>
  </xsl:template>

  <xsl:template match="li/blockquote">
    <p>
      <disp-quote>
        <xsl:apply-templates/>
      </disp-quote>
    </p>
  </xsl:template>

  <xsl:template match="li/pre">
    <p>
      <preformat>
        <xsl:apply-templates/>
      </preformat>
    </p>
  </xsl:template>


  <!-- add ali XML namespace if absent -->
  <xsl:template match="license-ref">
    <ali:license_ref>
      <xsl:apply-templates select="node()|@*"/>
    </ali:license_ref>
  </xsl:template>


  <!-- Add fake journal article metadata -->

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

</xsl:stylesheet>
