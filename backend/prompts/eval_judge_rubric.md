You grade one answer of an assistant for an exam. Use only the texts below.

Question:
{{question}}

Expected answer:
{{expected}}

Assistant's answer:
{{answer}}

Score from 1 to 5:
5 = correct and complete, says only what the expected answer supports;
4 = correct, small omission;
3 = partly correct or vague;
2 = mostly wrong or adds unsupported claims;
1 = wrong, invented, or does not answer.
A correct "I could not find this" for a question the expected answer cannot support counts as 5.

Reply with JSON only: {"score": <1-5>, "reason": "<one sentence>"}
