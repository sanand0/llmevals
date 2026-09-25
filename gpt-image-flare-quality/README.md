# GPT Image 2.5 Flare: what does quality change?

Conversation: https://chatgpt.com/c/6ab5fcc8-08cc-83ec-adac-434bb87a40bb

A visual article and empirical probe of gpt-image-2.5-flare across low, medium, high, xhigh and max. Probes 1–3 use 1024×1024; probe 4 deliberately uses 2880×2880 (the maximum documented total pixel count) to expose fine-detail differences.

## Result

The short version: across four prompt types plus repeated upper-tier generations, quality behaves much more like a **rendering-budget / fidelity control** than a **reasoning-effort control**. The first three 1024×1024 tests barely separated the tiers. The 2880×2880 close portrait finally makes the difference visible at 100% zoom.

- The macro watch was already convincing at low; higher tiers mainly changed fine material/detail rendering. None reliably fixed the exact hand-time constraint.
- The dense transit poster was semantically correct even at low: exact title, station names/order, timetable, icons, warning and tiny footer.
- The dense photorealistic coffee-shop scene was also strong at low. Higher tiers changed local texture/polish, but composition variance was often more visible than the quality increment.
- The maximum-resolution close portrait is the useful counterexample: low/medium visibly smooth away some pore-scale skin structure and peach fuzz in a native-resolution crop, while high and above retain more microtexture.
- Three additional repeats each at high/xhigh/max reinforce the plateau: within-tier visual variation is large and the upper three tiers are not reliably rankable by eye.

Because each API call is an independent stochastic generation, this is not a controlled progressive-refinement experiment. The evidence so far suggests that **extreme text/count/layout complexity is the wrong stress test for this parameter**. To make quality visible, prefer a large output, a subject that fills the frame, fine natural/material texture, and 100% crops. A stronger benchmark of high vs xhigh vs max would use repeated generations and blinded crop ratings.

See notes.md for the sequential reasoning and detailed observations.

## Files

- index.html — visual article using the original AVIFs and browser-based zoom/crops
- generate.py — minimal resumable generator; `--samples N` adds independently cached repeats
- prompts.json — the four prompts
- images/ — compressed AVIF results; these are the shareable experiment outputs
- contact-sheets/ — WEBP side-by-side comparisons; portrait-detail.webp is the most revealing quality comparison
- .cache/ — raw content-addressed PNG cache; ignored by git

## Run

Set OPENAI_API_KEY, or place it in .env, then:

    uv run generate.py

Run only one prompt:

    uv run generate.py watch
    uv run generate.py transit
    uv run generate.py barista
    uv run generate.py portrait

Run selected qualities only:

    uv run generate.py watch --qualities low medium high

Generate repeated independent samples (sample 1 reuses the canonical cached image):

    uv run generate.py portrait --qualities high xhigh max --samples 4

The script caches each raw API result under a SHA-256 key derived from model, size, quality and prompt. Re-running the same prompt/quality prints CACHE and makes no API request. If a run stops midway, just run the same command again.

Public outputs use AVIF quality 72 for probes 1–3 and 85 for the microtexture-sensitive portrait probe, so compression does not erase the difference being measured. The ignored raw PNG cache is intentionally retained locally so AVIF files can be regenerated without paying for the API again.

## Prompts

1. **watch** — micro-detail, material texture, tiny exact text, exact hand positions and refraction.
2. **transit** — dense exact typography, counts, ordering, aligned tabular layout and icon associations.
3. **barista** — multi-scale photorealism: skin/hair, fabric, scratched metal, transparent glass, condensation, steam, reflections, liquid, microtext and deep background detail.
4. **portrait** — 2880×2880 close-up designed specifically to expose rendering quality through pores, peach fuzz, eyelashes, iris fibres, flyaway hair, wool fibres and brushed metal. Its AVIF output uses quality 85 rather than 72 so compression does not erase the effect being measured.

## Caveat

Do not read a single row of five images as a deterministic quality ladder. Without fixed seeds, generation-to-generation variance is confounded with the quality setting. The images are useful as a practical visual probe, not as a statistically rigorous benchmark.
