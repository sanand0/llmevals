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

Decision-model systems use their native typed-choice endpoints instead of the chat prompt. They receive the same 77 label values and the same humanized label descriptions:

- Jev via OpenRouter Decisions (`choice.criteria`)
- GPT-6 Luna via OpenAI Decisions (`choice.choices`)
- Clef and Clef-flash via Cloudflare Workers AI (`choice.criteria`)

The customer request is supplied as the shared input/state required by each API. For comparability, the chosen label's probability is used as the confidence score.
