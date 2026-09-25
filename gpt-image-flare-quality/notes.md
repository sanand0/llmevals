# GPT Image 2.5 Flare quality experiment — working notes

Conversation: https://chatgpt.com/c/6ab5fcc8-08cc-83ec-adac-434bb87a40bb

Model: gpt-image-2.5-flare, 1024×1024. Qualities: low, medium, high, xhigh, max.

The experiment was run sequentially. I designed prompt 1, generated and inspected all five qualities, then chose prompt 2 in response to what prompt 1 revealed, and did the same before designing prompt 3.

## Probe 1 — macro watch

### Why this prompt

The first probe targeted the most plausible effect of the quality control: rendering budget / visual detail. It mixes:

- tiny but semantically constrained text (FLARE QUALITY TEST);
- repeated fine geometry (12 markers + minute ticks);
- an exact but visually awkward clock time (10:08:37);
- fine material textures (hairline steel scratches, wool fibres, machining, knurling);
- a physically demanding local effect (a droplet refracting tick marks).

### What happened

All five tiers produced a convincing watch and correctly rendered FLARE QUALITY TEST, even at low. The broad composition and materials were already strong at low.

Visible differences were much smaller than the token-budget differences would suggest:

- low already shows brushed metal, fine minute ticks, wool texture, crown ridges, and a plausible refracting droplet;
- medium/high/xhigh/max vary in microtexture and edge polish, but there is no clean monotonic obviously-better progression in the whole image;
- the exact time constraint is not reliably obeyed at any tier: the hands are plausible, but raising quality does not visibly turn this instruction-following failure into success;
- the phrase is readable at every tier;
- each quality call is a fresh stochastic generation, so camera angle, hand positions, marker layout and lighting change and add comparison noise.

### Decision after probe 1

This looked unlike a reason-harder knob. Since low already captured the semantics, probe 2 was chosen to stress exact text, counts, ordering and structured layout rather than texture.

## Probe 2 — dense transit poster

### Why this prompt

The transit poster asks for one exact title, exactly five ordered stations, an exact 4×3 timetable, four icon associations, an exact warning, a tiny exact footer, strict alignment, and no extra text.

If quality acted like deeper semantic reasoning, higher tiers should materially improve counts, ordering and exact strings. If it acted mainly like rendering budget, differences should concentrate on typography and layout polish.

### What happened

All five posters are impressively correct, including low:

- all five station names are present, correctly ordered and correctly spelled;
- all four timetable rows and every requested number are correct;
- the four requested icons are associated with the intended rows;
- the warning and tiny footer are correct;
- exactly five route nodes are present.

The differences are mainly aesthetic: spacing, weight, line treatment and overall polish vary. There is no evidence on this prompt that higher quality increases semantic instruction-following. Low already solves the full structured-information task.

### Decision after probe 2

Two probes had failed to show a meaningful semantic/reasoning advantage. Probe 3 therefore maximized multi-scale rendering difficulty, where a larger image-token budget should have the best chance to separate the tiers.

## Probe 3 — rainy coffee shop / barista

### Why this prompt

The scene combines fine biological texture, woven fabric, scratched steel, transparent glass, condensation, liquid, steam, reflections, microtext, hand anatomy, rain, and multiple depth planes.

### What happened

Again, low is already remarkably capable. It renders a coherent photorealistic scene with plausible hands, milk stream and latte art; visible apron weave; scratched metal; condensation; rain; reflected lights; steam; beans, spoon and receipt; and a rich multi-plane background.

Across medium through max, fine detail and local rendering differ, but there is still no reliable monotonic visual ladder where every higher tier is clearly better. Composition changes substantially between calls, which often dominates the subtle quality differences. The receipt text is tiny enough that its readability varies with composition as much as with the quality tier.

High/xhigh/max can look more polished in individual regions (fine texture, reflections, edge treatment), but max is not uniformly superior to high or xhigh in every local detail. This is consistent with quality controlling rendering budget rather than exposing a deterministic reasoning-effort ladder.

## Overall findings

1. **Quality is not behaving like LLM thinking effort.** None of the semantic constraints in the first three probes became reliably solved merely by increasing quality; probe 4 instead reveals a rendering-detail difference.
2. **Low is surprisingly capable.** It got the dense transit poster fully correct and produced strong photorealistic detail.
3. **Extra quality mostly buys rendering headroom.** The places to look are microtexture, edge treatment, material detail, reflections, tiny graphical elements and overall polish.
4. **The gain is not cleanly monotonic in one-shot comparisons.** Each call is stochastic and there is no seed control here, so composition differences can swamp the rendering-quality effect.
5. **Do not compare tiers as if they were progressive refinements of one base image.** They are independent generations from the same prompt.
6. **For thumbnail-sized output, low or medium may often be enough.** High/xhigh/max are easiest to justify when users will inspect large images or fine material/textural detail.
7. **A more rigorous benchmark would need repeats.** Several generations per prompt × quality, followed by blinded ratings, would separate quality effects from generation variance.

Contact sheets: contact-sheets/watch.webp, contact-sheets/transit.webp, contact-sheets/barista.webp, contact-sheets/portrait.webp, and the native-resolution contact-sheets/portrait-detail.webp.

## Research before probe 4 — where should higher quality actually separate?

Research sources:

- OpenAI image generation guide: https://developers.openai.com/api/docs/guides/image-generation
- OpenAI GPT Image 2.5 prompting guide: https://developers.openai.com/api/docs/guides/image-prompting
- Wilow quality-level watch test: https://trywilow.com/blog/gpt-image-2-5-quality-settings
- Runware Flare quality-level guide: https://runware.ai/docs/models/openai-gpt-image-2-5-flare/guides/quality-levels
- Genflick 142-call capability benchmark: https://genflick.com/blog/gpt-image-2-5-capability-benchmark
- OpenAI Images 2.5 announcement / editing improvements: https://openai.com/index/introducing-chatgpt-images-2-5/

The first three 1024×1024 probes were not operating in the regime where published quality-tier comparisons show the clearest differences.

The strongest external evidence points to resolved surface detail at large output sizes, not semantic complexity:

- OpenAI describes quality as rendering quality, separate from image dimensions, and says higher settings are worth testing when a lower tier fails a quality requirement; a higher setting is not guaranteed to improve every prompt.
- Wilow's controlled watch test used roughly 8-megapixel outputs and found low/medium soft on fine brushed-metal structure while high/xhigh/max were crisper. When the same watch was small inside a larger ad, low and max looked effectively the same. They reported little visible gain beyond high.
- Runware's Flare quality guide uses a close beauty portrait as its low-vs-max demonstration and points to pores, freckles and individual flyaway hairs. It notes that skin is unusually revealing of smoothing.
- Genflick's 142-call benchmark found that medium already handled bounded text, spatial ordering, and multi-reference composition. This argues against extreme text or large object counts as the best way to expose rendering-quality differences.
- OpenAI emphasizes reference preservation and precise editing as major Image 2.5 improvements, but those are model capabilities. Nothing in the official docs says the quality parameter is primarily an editing-only control. A text-to-image test is therefore still valid.

### Probe 4 hypothesis

To maximize the chance of seeing a visible tier difference without moving into editing, use nearly the maximum allowed pixel count and make the whole frame a texture-sensitive subject. 2880×2880 is exactly 8,294,400 pixels, the documented maximum total pixel count.

This probe uses a tightly framed natural face because pores, vellus hair, eyelashes, iris fibres and flyaway hair expose smoothing immediately, while a knitted wool collar and brushed titanium hoop provide two non-skin texture references in the same scene.

The key comparison is not only the whole image. The useful view is a native-resolution crop at 100% zoom, especially low/medium versus high/xhigh/max. Published evidence suggests that if there is a visible quality ladder, this is where it should appear. It may still plateau at high rather than continue through max.

### Probe 4 result

This is the first probe where the quality setting is visibly easier to see, but only when inspecting the native-resolution crop rather than the downscaled whole image.

- At whole-image viewing size, all five portraits are strong and the tier differences remain easy to miss.
- In the 100% face crop, low and medium look smoother: pore-scale structure, peach fuzz and other high-frequency skin detail are less resolved.
- High, xhigh and max retain more natural microtexture and fine hair detail. This matches the external watch/portrait benchmarks much better than the earlier 1024×1024 tests did.
- The improvement is most convincing as a low/medium → high transition. There is still no robust visual ordering among high, xhigh and max; stochastic differences in face, lighting and local focus remain at least as large as the incremental tier difference.
- The wool and hair also benefit from the extra resolved detail, but skin is the easiest region for a human viewer to notice.

So the practical recipe for making quality visible is: **large output + subject filling the frame + fine natural/material texture + inspect at 100% zoom**. Adding huge amounts of text or many precisely counted objects primarily stresses semantic/layout capability, which Flare already handles well at low/medium and which does not consume the extra quality budget in the same visibly useful way.

Editing/reference-image workflows are worth testing separately because Image 2.5 was explicitly improved there, but the quality control itself is not editing-specific. Probe 4 demonstrates a text-to-image case where it matters.

### Current interpretation after four probes

Quality appears to have three practical regimes on these examples:

1. **low/medium:** sufficient for semantics, layouts, thumbnails, and surprisingly strong general rendering;
2. **high:** the meaningful step when full-resolution fine texture matters;
3. **xhigh/max:** expensive headroom for demanding edge cases, but not a reliably visible improvement over high in a single uncontrolled generation.

To establish whether xhigh/max have a repeatable advantage over high, the next useful experiment would not be an even crazier single prompt. It would be several repeats of a high-resolution texture-sensitive prompt followed by blind 100%-crop comparisons.

## Probe 5 — repeated high / xhigh / max samples

The next question after probe 4 was whether the apparent plateau past high was real or simply an unlucky single comparison.

I generated three additional independent samples at each of high, xhigh, and max, for four samples per tier (12 upper-tier portraits total). The generator now supports --samples N; sample 1 retains the canonical cache key/output, while samples 2+ receive independent cache keys and -2, -3, ... filenames. This preserves all earlier cached work.

I inspected a fixed relative face crop in a shuffled, initially unlabeled 12-image grid. The samples were not reliably rankable by tier. Skin microtexture, freckles, pore visibility, eyebrow/eyelash detail, and local sharpness vary substantially within each tier. There are excellent high samples and less impressive max samples, and vice versa.

This strengthens, rather than weakens, the earlier conclusion:

- the clear practical separation in this experiment is low/medium versus high on a large, texture-sensitive image;
- xhigh and max do not form an obvious monotonic visual ladder above high;
- stochastic generation variance is large enough that a single high-vs-max pair is poor evidence;
- a rigorous claim that max beats high would require a larger randomized blinded rating experiment, not cherry-picked crops.

## Article

index.html tells the experiment as a visual article. Its zoomed views use CSS overflow/positioning on the original AVIF files; it does not create new image crops. This deliberately keeps the evidence traceable to the actual generations.

The narrative is:

1. quality behaves like rendering effort, not deeper prompt reasoning;
2. the difference becomes visible on large, texture-sensitive subjects inspected at native resolution;
3. the meaningful jump in these tests is primarily low/medium → high;
4. text-heavy, layout-heavy, and cluttered 1024×1024 tests did not benefit visibly enough to justify the top tiers;
5. repeated high/xhigh/max portraits show large within-tier variance and no obvious upper-tier ordering;
6. editing/reference-image fidelity is a separate future benchmark because it introduces input-fidelity and preservation effects.

