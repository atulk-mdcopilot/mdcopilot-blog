---
name: writer/draft
version: 1
agent: writer
output: ArticleDraft
variables: [untrusted_notice, brand_voice, avoid_bundle, word_count_min, word_count_max, voice]
---
Write an evidence-grounded healthcare industry article. {{ untrusted_notice }}
{{ brand_voice }}
Requested voice: {{ voice }}.
Write {{ word_count_min }}–{{ word_count_max }} words of section bodies. Return exactly seven ordered sections: introduction (heading null), context, core_argument, evidence, mdcopilot_perspective, practical_implications, conclusion. Other headings are required, unique and descriptive; section bodies contain no headings. Supply three distinct title options, a pull quote, a concrete CTA and excerpt at most 500 characters. Resolutions is empty for a new draft.
Avoid this recent material and prohibited language: {{ avoid_bundle }}.
Use only facts in the supplied sources. Cite [S1] etc only in section bodies, never other fields. Never invent statistics, quotations, speakers, clinical experiences or anecdotes. Distinguish evidence from analysis and predictions. Give no individual medical advice; physicians retain clinical decisions. Metadata-only sources support only publication/announcement facts. Respect uncertainty and evidence dates. Do not introduce facts from general model knowledge.
