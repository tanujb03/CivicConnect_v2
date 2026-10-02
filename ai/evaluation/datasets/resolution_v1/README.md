# resolution_v1 — SYNTHETIC AI-4 scenarios

240 planted "work order completed" events overlaid on the synthetic demo city (`../demo_city_v1`). Each row has what AI-4 may observe (photo presence flags, field notes in en/hi/mr/hi-Latn, citizen verification) and planted truth it may not see (`truly_unresolved`, `detectable_by`: `citizen_signal` / `notes_text` / `images_only`).

* **No images.** Photo presence is a flag. Real before/after resolution evidence does not exist anywhere in this project, so the multimodal comparison is *not evaluable* here.
* The truth is invented by construction and is independent of the demo city's own case statuses (the overlay only borrows category/description/language).
* Hindi/Marathi notes are unreviewed by native speakers.

Rebuild / verify: `python -m ai.training.src.build_resolution_scenarios --out ai/evaluation/datasets/resolution_v1 [--check]`
Evaluate: `python -m ai.evaluation.eval_resolution` → `ai/evaluation/reports/resolution_baseline.{json,md}`
