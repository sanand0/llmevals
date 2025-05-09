# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "pandas",
# ]
# ///
import json
import pandas as pd
from itertools import combinations

# Load evals.json
with open("evals.json", "r") as f:
    data = json.load(f)

# Extract records: query, expected, provider, predicted
records = []
for r in data["results"]["results"]:
    query = r["vars"].get("query")
    expected = r["testCase"]["assert"][0]["value"]
    predicted = r.get("response", {}).get("output", None)
    provider = r["provider"]["id"]
    if query is not None and predicted is not None:
        records.append(
            {"query": query, "expected": expected, "provider": provider, "predicted": predicted}
        )

df = pd.DataFrame(records)
# Drop gemma
df = df[df["provider"] != "google/gemma-3-27b-it"]

# Pivot to wide: one row per query, columns are providers
pivot = df.pivot_table(
    index=["query", "expected"], columns="provider", values="predicted", aggfunc="first"
).reset_index()

# List of model/provider names
models = [col for col in pivot.columns if col not in ["query", "expected"]]
total = len(pivot)


# Function to compute metrics for any ensemble size k
def compute_ensemble(k):
    results = []
    for combo in combinations(models, k):
        preds = pivot[list(combo)]
        # Disagreement: queries where not all predictions in combo agree
        dis_count = (preds.nunique(axis=1) > 1).sum()
        # Missed error: all agree & that agreed value != expected
        agree_mask = preds.nunique(axis=1) == 1
        agreed_values = preds.iloc[:, 0]  # any column since all equal when agree_mask
        missed_count = (agree_mask & (agreed_values != pivot["expected"])).sum()
        results.append(
            {
                "Models": ", ".join(combo),
                "GroupSize": k,
                "Disagreement (%)": dis_count / total * 100,
                "Missed Error (%)": missed_count / total * 100,
            }
        )
    return pd.DataFrame(results)


# Combine and sort by Missed Error
df_all = pd.concat([compute_ensemble(n) for n in range(2, 6)], ignore_index=True)
df_sorted = df_all.sort_values("Missed Error (%)", ascending=True).reset_index(drop=True)

# Print improvement stats
stats = []
for k in range(2, 6):
    st = df_sorted[df_sorted["GroupSize"] == k][["Disagreement (%)", "Missed Error (%)"]].median()
    st["Models #"] = k
    stats.append(st)
print(pd.DataFrame(stats))

# Print best 2-model combinations
print(df_sorted[df_sorted["GroupSize"] == 2].head(10))
