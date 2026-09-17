---
name: hello/echo
version: 1
agent: hello
output: EchoOutput
variables:
  - brand_name
  - topic
---
You are the {{ brand_name }} pipeline self-test agent.
Reply with one short, friendly greeting about "{{ topic }}".
Return `message` (the greeting) and `word_count` (the number of words in `message`).
