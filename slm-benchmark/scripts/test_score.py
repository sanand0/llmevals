#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from score import score_answer

CASES = [
    ("14%", "14%", True),
    ("0.14", "14%", True),
    ("14", "14%", True),
    ("13.4%", "14%", False),
    ("240.41", "$ 240.41", True),
    ("yes", "yes", True),
    ("no", "yes", False),
    ("7989", "$ 7989 thousand", True),
]

for prediction, gold, expected in CASES:
    actual = score_answer(prediction, gold)
    assert actual == expected, (prediction, gold, expected, actual)

print(f"OK: {len(CASES)} scorer cases")
