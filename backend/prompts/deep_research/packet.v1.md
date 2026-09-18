---
name: deep_research/packet
version: 1
agent: deep_research
output: ResearchPacket
variables: [untrusted_notice]
---
Build a focused research packet from the supplied topic and evidence. {{ untrusted_notice }}
Produce summary, keyFacts, statistics, primaryMarkers, supportingMarkers, counterarguments, industryContext, mdcopilotConnection, claimsNeedingVerification and sourceRefs. sourceRefs MUST be an empty list: application code fills immutable ledger references. Every source citation is an S marker from the provided list. Statistics require explicit supporting text and an asOf date when known; omit unsupported statistics. Explain conflicting evidence and limits. Metadata-only sources do not support substantive claims. Do not fabricate patient stories or quotations. Preserve clinician authority in every clinical framing.
