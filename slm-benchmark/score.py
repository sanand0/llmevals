"""Normalized final-answer scoring for the frozen FinQA sample."""
from __future__ import annotations
import re
NUM_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")

def _number(text: str):
    match = NUM_RE.search(text.replace("$", ""))
    if not match:
        return None
    token = match.group(0).replace(",", "")
    value = float(token)
    decimals = len(token.split(".", 1)[1]) if "." in token else 0
    return value, decimals

def score_answer(prediction, gold) -> bool:
    pred = str(prediction).strip().lower()
    target = str(gold).strip().lower()
    if target in {"yes", "no"}:
        return pred == target
    if not pred:
        return False
    gold_num = _number(target)
    pred_num = _number(pred)
    if gold_num is None or pred_num is None:
        return pred == target
    gold_value, gold_decimals = gold_num
    pred_value, _ = pred_num
    tolerance = 0.5 * (10 ** (-gold_decimals)) + 1e-9
    if "%" in target:
        candidates = [pred_value]
        if "%" not in pred:
            candidates.append(pred_value * 100.0)
        return any(abs(gold_value - value) <= tolerance for value in candidates)
    if "%" in pred:
        return False
    return abs(gold_value - pred_value) <= tolerance
