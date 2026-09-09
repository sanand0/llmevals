"""Exact confidence-instruction fragments used by the BANKING77 experiments.

Keep these strings as the single source of truth for API runners and the explainer page.
Changing one creates a new experimental condition; do not silently edit an existing fragment.
"""

BASELINE = """your probability that your chosen label exactly matches the gold routing label. Treat confidence as a probability of correctness, not a vague feeling."""

FULL_VARIANTS = {
    "uncertainty_ok": """It is completely okay to be uncertain. Do not default to high confidence just because you must choose a label. If more than one label is genuinely plausible from the request, lower the confidence accordingly. Report your best estimate of the probability that the chosen label exactly matches the gold routing label.""",
    "frequency_calibrated": """Treat confidence as a literal long-run probability, not as emphasis or a feeling. If you report X%, then across many decisions for which you report about X%, roughly X% should exactly match the gold routing label. Use the full 0–100 range when warranted; 60%, 75%, or 85% are perfectly acceptable. Report your best probability estimate.""",
    "strongest_alternative": """Before assigning confidence, account for the strongest plausible competing label. Your confidence is the probability that your chosen label exactly matches the gold routing label after allowing for that alternative. If the best alternative is close, confidence should be correspondingly lower; reserve very high confidence for cases with little plausible ambiguity.""",
    "top_two_mass": """Silently identify the two most plausible allowed labels and allocate probability between them and any remaining plausible labels so the probabilities would sum to 100%. Choose the highest-probability label. Report that label's probability as confidence. Do not collapse uncertainty just because only one label can be returned.""",
}

SCREEN_VARIANTS = {
    "anchored_scale": """Use these calibration anchors when assigning confidence: 50% means the best two labels are about equally plausible; 70% means your choice is favored but there is a serious alternative; 85% means clearly favored but still plausibly wrong; 95% means only a small residual doubt; 99% means about one error in 100 comparable cases. Use values between the anchors as appropriate. Reserve 100% for cases where no allowed alternative is realistically plausible.""",
    "top_two_mass": FULL_VARIANTS["top_two_mass"],
    "independent_recheck": """First choose the most likely label. Then, as a separate second judgment, forget that you already chose it and estimate the probability that an independent expert with the gold routing guide would assign exactly that same label. Report that probability as confidence; do not defend the first choice.""",
    "evidence_balance": """Before assigning confidence, silently ask: what specific words in the request distinguish my chosen label from its strongest competitor, and what ambiguity remains? Strong discriminating evidence should raise confidence; missing or shared evidence should lower it. Report the probability that the chosen label exactly matches the gold routing label.""",
    "proper_score": """Your confidence will be evaluated with a proper probability scoring rule that penalizes both overconfidence and underconfidence. You gain nothing by sounding certain. Report the probability that minimizes your expected scoring loss: the chance that your chosen label exactly matches the gold routing label.""",
}
