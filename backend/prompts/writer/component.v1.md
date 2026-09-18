---
name: writer/component
version: 1
agent: writer
output: ComponentDraft
variables: [untrusted_notice, brand_voice, avoid_bundle, word_count_min, word_count_max, voice]
---
Regenerate exactly the requested component. {{ untrusted_notice }}
{{ brand_voice }} Voice: {{ voice }}.
Return component and sectionKey exactly as requested. Set only the matching output field; every other field is null. For introduction its section.key is introduction, heading null and sectionKey null. For section use the requested section key and a meaningful heading. Preserve the article's overall {{ word_count_min }}–{{ word_count_max }} word budget. Use only supplied [S<n>] citations in body content. Never invent statistics, quotations, clinical experiences or anecdotes. Avoid: {{ avoid_bundle }}.
