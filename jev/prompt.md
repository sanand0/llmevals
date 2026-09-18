# Classification prompt

For ordinary chat models, each request gets this prompt. `LABELS_JSON` is the sorted list of all 77 BANKING77 routing labels and `REQUEST` is the support request.

```text
Classify this customer request into exactly one of the allowed labels below.

Allowed labels:
LABELS_JSON

Request:
REQUEST

Return ONLY JSON with label (exactly one allowed label) and confidence (integer 0-100): your probability that your chosen label exactly matches the gold routing label. Treat confidence as a probability of correctness, not a vague feeling.
```

Jev uses OpenRouter's Decisions endpoint instead. The customer request is the state, and the same 77 labels are supplied as `choice` criteria with humanized label names. Its chosen-label probability is used as the comparable confidence score.
