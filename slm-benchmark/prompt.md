# FinQA benchmark prompt

Each request supplies only the frozen FinQA question and its gold evidence snippets.
Retrieval is deliberately excluded from this benchmark.

Return only JSON matching the supplied schema:

    {"answer": "FINAL_ANSWER", "confidence": 0-100}

Rules:
- answer: give only the final answer, with the natural unit implied by the question/evidence. Use % for percentages and yes/no for yes/no questions.
- Do not include an explanation or reasoning in answer.
- confidence: your probability, as an integer from 0 to 100, that answer matches the correct FinQA answer.
- Treat confidence as a probability of correctness, not a vague feeling.
- Use only the supplied evidence.

OpenRouter JSON-schema structured output is used for all configured hosted models.
Reasoning/thinking is disabled for the first pass wherever supported.
