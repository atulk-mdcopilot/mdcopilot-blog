---
name: writer/revise
version: 1
agent: writer
output: ArticleDraft
variables: [untrusted_notice, brand_voice, avoid_bundle, word_count_min, word_count_max, voice]
---
Revise the supplied article against every F-numbered finding. {{ untrusted_notice }}
{{ brand_voice }} Voice: {{ voice }}.
Return the complete seven ordered sections with the original section keys, title options, pull quote, CTA and excerpt. Keep body word count between {{ word_count_min }} and {{ word_count_max }}. Return one resolution for each F marker with action fixed, removed or declined and a precise note. All required safety and evidence defects must be fixed or removed. Preserve unaffected material. Do not claim to have fixed a problem unless the text actually changes. Use only supplied S markers in section bodies. Remove invented statistics, invented quotes, unsupported anecdotes, autonomous clinical decision framing and prohibited phrases. Never invent new evidence. Avoid: {{ avoid_bundle }}.
