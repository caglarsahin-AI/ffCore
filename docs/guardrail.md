# Guardrails and PII (FFCore Guard, package 08-lite)

## PII quality report (regex recognizers)

Measured on the synthetic 13a set `data/samples/pii/pii-100.jsonl` (100 sentences, 10 negatives).
A prediction counts when it overlaps a gold span of the same category. Regenerate with
`docker compose run --rm tools sh -c "cd backend && python -m ffcore.guardrails.quality ../data/samples/pii/pii-100.jsonl"`;
a test keeps this table equal to the measurement.

| Category | Support | Predicted | Recall | Precision |
|---|---|---|---|---|
| `TR_NATIONAL_ID` | 9 | 9 | 1.00 | 1.00 |
| `TR_PHONE` | 9 | 9 | 1.00 | 1.00 |
| `TR_IBAN` | 6 | 6 | 1.00 | 1.00 |
| `EMAIL_ADDRESS` | 8 | 8 | 1.00 | 1.00 |
| `CREDIT_CARD` | 5 | 5 | 1.00 | 1.00 |

Limits of this measurement:

- Support is small (9 national IDs, 9 phones): one miss drops recall to 0.89. The acceptance
  threshold (national ID and phone recall ≥ 0.98, brief 08) is met only with 9 of 9.
- The set and the recognizers were written by the same team; the formats in the set are known.
  Treat 1.00 as "no regression on the known formats", not as a field recall.
- `PERSON`, `ORGANIZATION` and `LOCATION` need the Turkish NER model (08 full); they are not
  measured here.
