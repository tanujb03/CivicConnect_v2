"""Native-speaker review checklist (docs/I18N_REVIEW.md): a label-stratified, seeded sample of the Hindi and Marathi gold lines.

    python -m ai.training.src.text_corpus.review_sample --gold ai/training/gold/gold_llm_authored_claude_v1.csv --out docs/I18N_REVIEW.md

Per language: ONE line from each of ``k`` different labels (k = 20 of the 27), a seeded random line within the label. Marathi first takes the labels the Hindi sample left out, so the
two samples together cover as many labels as possible. The labels each sample leaves out are listed in the document.
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

from ai.training.src.text_corpus.build import load_gold

SEEDS = {"hi": 7, "mr": 11}
NAMES = {"hi": "Hindi (hi)", "mr": "Marathi (mr)"}
REPO_ROOT = Path(__file__).resolve().parents[4]


def display_path(p: Path) -> str:
    """The path as written into the doc: relative to the repository root, so the committed text does not depend on where the repo (or a worktree) lives."""
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.name


def stratified_sample(rows: list[tuple[int, dict]], k: int, seed: int, prefer: tuple[str, ...] = ()) -> tuple[list[tuple[int, dict]], list[str]]:
    """rows = (row number, row). Returns (the sampled rows in row order, the labels left out). Labels in ``prefer`` are taken first, the rest in a seeded shuffle."""
    rng = random.Random(seed)
    by: dict[str, list[tuple[int, dict]]] = {}
    for i, r in rows:
        by.setdefault(r["label_id"], []).append((i, r))
    first = [lab for lab in sorted(by) if lab in prefer]
    rest = [lab for lab in sorted(by) if lab not in prefer]
    rng.shuffle(rest)
    chosen = (first + rest)[:k]
    picked = sorted((rng.choice(by[lab]) for lab in sorted(chosen)), key=lambda x: x[0])
    return picked, sorted(set(by) - set(chosen))


def build_doc(gold: Path, k: int = 20) -> str:
    rows, _ = load_gold(gold)
    numbered = list(enumerate(rows, 1))                              # row N = N-th accepted data row of the CSV
    out = ["# Native-speaker review of LLM-written Indic text", "",
           f"**Why:** the gold set `{display_path(gold)}` was written by an LLM (provenance `llm_authored_claude`, a different model family from the Gemini/Groq corpus generators).",
           "LLM-written Hindi and Marathi can sound translated, stiff or regionally off, and the same applies to the training corpus. Until a native speaker has signed off,",
           "no accuracy number computed on these rows may be called a real-world result, and the set is always reported as `gold[llm_authored_claude, n=...]`, never as human gold.", "",
           f"**Sample:** per language, {k} lines, one from each of {k} different labels (of 27), chosen with `random.Random(seed)` (seed {SEEDS['hi']} for Hindi, {SEEDS['mr']} for Marathi) from the 84 lines",
           "of that language. Marathi takes the labels missing from the Hindi sample first, so together the two samples cover as many labels as possible. Rows are numbered `row N` = N-th data row after the CSV header.",
           "Regenerate with `python -m ai.training.src.text_corpus.review_sample`. If a sample shows problems, review all 84 lines of that language.", "",
           "## How to review (one tick per line)", "",
           "1. **Natural?** Would a real citizen write or say this? Fix stiff, over-formal or word-for-word-translated phrasing.",
           "2. **Right register for its style tag** (`sms`, `angry`, `polite`, `plain`, `landmark`, `typo`, `mixed`): terse for SMS, no polite forms in `angry`, spelling slips only in `typo`.",
           "3. **Correct language:** Hindi vs Marathi grammar and vocabulary (not Hindi words in Marathi dress, or the reverse); correct script and spelling outside `typo` rows.",
           "4. **Label still fits:** the text clearly belongs to the stated `label_id` and to no other label.",
           "5. **Safe:** no real person, phone number, address or offensive wording.", "",
           "Mark `[x]` when the line is fine as written. If it needs a change, leave `[ ]` and write the corrected text after `fix:`. Record reviewer name and date at the end of each section.", ""]
    prefer: tuple[str, ...] = ()
    for lang in ("hi", "mr"):
        pool = [(i, r) for i, r in numbered if r["language"] == lang]
        picked, missing = stratified_sample(pool, k, SEEDS[lang], prefer)
        out += [f"## {NAMES[lang]}: {len(picked)} lines, {len(picked)} labels (of {len(pool)} lines)", "",
                f"Labels NOT covered by this sample ({len(missing)}): " + (", ".join(f"`{m}`" for m in missing) or "none"), ""]
        for i, r in picked:
            style = r["notes"].split("style=")[1] if "style=" in r.get("notes", "") else "?"
            out += [f"- [ ] row {i} · `{r['label_id']}` · {style}: {r['text']}  ", "  fix: "]
        out += ["", "Reviewer: ____________ · Date: ____________ · Lines needing a fix: ___ / " + str(len(picked)), ""]
        prefer = tuple(missing)
    out += ["## After review", "",
            "- Apply the fixes to the CSV. Keep provenance `llm_authored_claude` for untouched lines; a line a reviewer rewrites is then human-edited: move it to a separate file marked `human`, never into the LLM-authored one.",
            "- If more than 4 of 20 lines in a language needed a fix, review all 84 lines of that language before using them for evaluation.",
            "- After editing the CSV, re-validate it with the repo loader (`ai.training.src.text_corpus.build.load_gold`): it must still accept every row.", ""]
    return "\n".join(out)


BEGIN, END = "<!-- gold-review:begin (generated by ai.training.src.text_corpus.review_sample; edit the CSV or the sampler, not this block) -->", "<!-- gold-review:end -->"


def write_doc(gold: Path, out: Path) -> None:
    """Write the generated block between the markers of ``out``; anything else in the file (other lanes' review sections) is kept. An existing file without markers is refused, never overwritten."""
    block = f"{BEGIN}\n{build_doc(gold)}\n{END}\n"
    if not out.exists():
        out.write_text(block, encoding="utf-8")
        return
    text = out.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        raise SystemExit(f"{out} exists but has no gold-review markers; add `{BEGIN}` and `{END}` around the generated part (refusing to overwrite the file)")
    head, rest = text.split(BEGIN, 1)
    tail = rest.split(END, 1)[1].lstrip("\n")
    out.write_text(head + block + ("\n" + tail if tail else ""), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gold", type=Path, default=Path("ai/training/gold/gold_llm_authored_claude_v1.csv"))
    ap.add_argument("--out", type=Path, default=Path("docs/I18N_REVIEW.md"))
    a = ap.parse_args()
    write_doc(a.gold, a.out)
    print("wrote", a.out)
