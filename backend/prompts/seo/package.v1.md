---
name: seo/package
version: 1
agent: seo
output: SeoPackage
variables: [untrusted_notice, category, site_url]
---
Create SEO metadata and social copy grounded in the supplied article. {{ untrusted_notice }}
Site: {{ site_url }}. Category: {{ category }}.
Return seo and social. SEO title is at most 60 characters, metaDescription 120–160 characters, slug lowercase kebab-case at most 200. Include primaryKeyword, secondaryKeywords, ogTitle, ogDescription, nonempty tags and category. internalLinkSuggestions may use only supplied candidates; return [] if none are relevant. externalReferences must contain supplied S markers for sources actually cited. Never fabricate links. Social fields are linkedin, xPost and newsletterTeaser, with no invented claims, prohibited hype or fabricated experiences.
