"""LLM-written corpus pipeline: prompts, validation, resumable generation, group-safe splits, gold set (scripted fake provider; no network)."""
import json
import random

import pytest

from ai.inference.errors import ProviderUnavailable
from ai.inference.provider import StructuredResult
from ai.training.src.text_corpus import build as cb
from ai.training.src.text_corpus import generate as gen
from ai.training.src.text_corpus import spec
from ai.training.src.text_corpus import validate as v

HI = ["सड़क पर बड़ा गड्ढा है और गाड़ियाँ फिसल रही हैं", "हमारी गली में गड्ढा बहुत बड़ा हो गया है", "बारिश के बाद सड़क पर गहरा गड्ढा बन गया है"]


def test_every_label_language_style_cell_is_planned_with_stable_ids_and_a_clear_prompt():
    cells = spec.build_cells()
    assert len(cells) == 27 * 4 * 9 and len({c.cell_id for c in cells}) == len(cells)
    assert {c.language for c in cells} == {"en", "hi", "mr", "hi-Latn"} and {c.label_id for c in cells} >= {"roads/pothole", "other/unclassified"}
    c = next(c for c in cells if c.label_id == "roads/pothole" and c.language == "mr")
    system, user = spec.prompt_for(c)
    assert "JSON" in system and "Pothole" in user and "Marathi in Devanagari" in user and "exactly 12 items" in user and "खड्डा" in user
    assert "does not fit any civic category" in spec.prompt_for(next(c for c in cells if c.label_id == "other/unclassified"))[1]


def test_validation_catches_wrong_script_pii_length_and_duplicates():
    assert v.problems("There is a big pothole near the school gate", "en") == []
    assert "script" in v.problems("सड़क पर गड्ढा है", "en") and "script" in v.problems("big pothole near school", "hi") and "script" in v.problems("road par gadda hai", "mr")
    assert v.problems("road par bada gadda hai school ke paas", "hi-Latn") == []
    for bad in ("call me on 9876543210 about the pothole", "mail me at someone@example.com please", "see https://x.example/photo.jpg", "my aadhaar 1234 5678 9012 pothole"):
        assert "pii" in v.problems(bad, "en"), bad
    assert "length" in v.problems("hi", "en") and "length" in v.problems("x" * 600, "en")
    seen: set[str] = set()
    kept, rej = v.clean_items(["Big pothole!", "big  pothole", "BIG POTHOLE.", "Another pothole on MG road", 7], "en", seen)
    assert kept == ["Big pothole!", "Another pothole on MG road"] and rej["duplicate"] == 2 and rej["not_text"] == 1


class Fake:
    name = "fake"

    def __init__(self, fail_from: int | None = None):
        self.calls, self.fail_from = 0, fail_from

    def structured_completion(self, *, task, instructions, parts, schema_name, json_schema):
        self.calls += 1
        if self.fail_from is not None and self.calls >= self.fail_from:
            raise ProviderUnavailable("quota", status_code=429)
        text = parts[0].text
        lang = "hi" if "Hindi in Devanagari" in text else "mr" if "Marathi in Devanagari" in text else "en"
        rng = random.Random(self.calls)
        items = [{"text": (rng.choice(HI) + f" {self.calls}-{i}") if lang in ("hi", "mr") else f"big pothole number {self.calls}-{i} on the road near school"} for i in range(12)]
        return StructuredResult(data={"items": items}, model="fake-model")


def test_generation_is_resumable_limited_and_stops_on_quota_failures(tmp_path):
    cells = spec.build_cells(languages=["en", "hi"], styles=["sms_short", "angry"], k=12)[:20]
    prov = Fake()
    log: list[str] = []
    s1 = gen.generate_shards(cells, {"en": prov, "hi": prov}, tmp_path, limit=7, log=log.append)
    assert s1["written"] == 7 and len(list(tmp_path.glob("*.json"))) == 7 and prov.calls == 7
    s2 = gen.generate_shards(cells, {"en": prov, "hi": prov}, tmp_path, log=log.append)
    assert s2["skipped_existing"] == 7 and s2["written"] == 13 and prov.calls == 20                      # finished shards are never re-requested
    flaky = Fake(fail_from=3)
    s3 = gen.generate_shards(spec.build_cells(languages=["en"], styles=["typo_noisy"], k=12), {"en": flaky}, tmp_path / "q", max_consecutive_failures=3, log=log.append)
    assert s3["written"] == 2 and s3["failed"] == 3 and any("stopping after 3 consecutive failures" in m for m in log)
    shard = json.loads(next(iter(tmp_path.glob("*.json"))).read_text(encoding="utf-8"))
    assert shard["backend"] == "fake" and shard["model"] == "fake-model" and shard["cell"]["label_id" if False else "subcategory"] and len(shard["items"]) == 12


def test_build_splits_by_request_group_keeps_templates_out_of_test_and_writes_a_manifest(tmp_path):
    cells = spec.build_cells(languages=["en", "hi"], styles=["sms_short", "angry", "typo_noisy", "landmark", "voice_transcript", "elderly_simple"], k=12)[:324]
    prov = Fake()
    gen.generate_shards(cells, {"en": prov, "hi": prov}, tmp_path / "shards")
    tpl = tmp_path / "tpl"
    tpl.mkdir()
    (tpl / "train.jsonl").write_text("".join(json.dumps({"id": f"t{i}", "text": f"template text {i}", "language": "en", "category": "roads", "subcategory": "pothole", "family_id": f"pothole:en:{i % 5}"}) + "\n" for i in range(40)), encoding="utf-8")
    m = cb.build(tmp_path / "shards", tmp_path / "corpus", templates=tpl, templates_per_label_lang=10, seed=3)
    rows = {sp: [json.loads(ln) for ln in (tmp_path / "corpus" / f"{sp}.jsonl").read_text(encoding="utf-8").splitlines()] for sp in ("train", "val", "test")}
    assert sum(len(r) for r in rows.values()) == m["generation"]["items_kept"] + 10 and all(rows[s] for s in rows)
    train_labels = {r["label_id"] for r in rows["train"]}
    assert {r["label_id"] for sp in ("val", "test") for r in rows[sp]} <= train_labels            # every evaluated label is also trained
    side = {}
    for sp, rs in rows.items():
        for r in rs:
            assert side.setdefault(r["group"], sp) == sp, "a generation request straddles two splits"
    assert not any(r["source"] == "template" for r in rows["test"]) and all(r["synthetic"] and r["label_origin"] in ("llm_generated", "synthetic_template") for r in rows["train"])
    assert m["gold"] is None and set(m["files"]) == {"train.jsonl", "val.jsonl", "test.jsonl"} and "NOT real citizen" in m["notice"]
    assert cb.build(tmp_path / "shards", tmp_path / "corpus2", templates=tpl, templates_per_label_lang=10, seed=3)["files"] == m["files"]      # deterministic


def test_gold_template_roundtrip_and_validation(tmp_path):
    p = tmp_path / "gold.csv"
    cb.gold_template(p)
    text = p.read_text(encoding="utf-8")
    assert "roads/pothole  =  Pothole" in text and "other/unclassified" in text and text.count("example - delete") == 2
    rows, bad = cb.load_gold(p)
    assert rows == [] and bad["example_or_empty"] == 2
    with p.open("a", encoding="utf-8") as f:
        f.write('"khadda hai road par school ke paas",roads/pothole,hi-Latn,\n"light band hai",street_lighting/light_not_working,hi-Latn,\n"x",no/such,en,\n"y",roads/pothole,fr,\n"khadda hai road par school ke paas",roads/pothole,hi-Latn,\n')
    rows, bad = cb.load_gold(p)
    assert [r["label_id"] for r in rows] == ["roads/pothole", "street_lighting/light_not_working"] and bad == {"example_or_empty": 2, "unknown_label": 1, "unknown_language": 1, "duplicate": 1}
    shards = tmp_path / "s"
    gen.generate_shards(spec.build_cells(languages=["en"], styles=["sms_short"], k=12)[:30], {"en": Fake()}, shards)
    m = cb.build(shards, tmp_path / "c", gold=p)
    first = json.loads((tmp_path / "c" / "gold.jsonl").read_text().splitlines()[0])
    assert m["gold"]["rows"] == 2 and (tmp_path / "c" / "gold.jsonl").exists()
    assert (first["provenance"], first["label_origin"], first["synthetic"]) == ("unspecified", "unspecified", True)             # no provenance given: never defaulted to human
    assert m["gold"]["by_provenance"] == {"unspecified": 2} and m["gold"]["human_rows"] == 0


def test_gold_template_asks_for_a_provenance_column_and_example_rows_do_not_load(tmp_path):
    p = tmp_path / "gold.csv"
    cb.gold_template(p)
    text = p.read_text(encoding="utf-8")
    assert cb.GOLD_HEADER == ["text", "label_id", "language", "notes", "provenance"] and "text,label_id,language,notes,provenance" in text and "write `human` for lines YOU wrote" in text
    assert cb.load_gold(p)[0] == []


def test_gold_provenance_is_read_per_row_written_to_gold_jsonl_and_counted_in_the_manifest(tmp_path):
    p = tmp_path / "gold.csv"
    p.write_text("text,label_id,language,notes,provenance\n"
                 "mere ghar ke saamne bada gadda hai,roads/pothole,hi-Latn,,human\n"                                             # explicit human
                 "road par gadda hai school ke paas,roads/pothole,hi-Latn,llm_authored_claude; style=plain,llm_authored_claude\n"     # explicit column
                 "gadda hai chowk par bahut bada,roads/pothole,hi-Latn,llm_authored_claude; style=sms,\n"                              # notes marker only
                 "pothole near the market is huge,roads/pothole,en,,\n"                                                              # nothing: unspecified
                 "big pothole by the temple wall,roads/pothole,en,written by the team,\n"                                            # 'team' in notes is not a marker
                 "huge pothole by the bus depot,roads/pothole,en,llm_authored_claude,human\n"                                        # contradiction: not human
                 "pothole next to the school gate,roads/pothole,en,,teacher\n", encoding="utf-8")                                    # unknown value: not human
    rows, bad = cb.load_gold(p)
    assert not bad and [(r["provenance"], r["provenance_source"]) for r in rows] == [
        ("human", "column"), ("llm_authored_claude", "column"), ("llm_authored_claude", "notes"), ("unspecified", "none"), ("unspecified", "none"),
        ("unspecified", "conflict"), ("unspecified", "column_unrecognized")]
    shards = tmp_path / "s"
    gen.generate_shards(spec.build_cells(languages=["en"], styles=["sms_short"], k=12)[:30], {"en": Fake()}, shards)
    m = cb.build(shards, tmp_path / "c", gold=p)
    out = [json.loads(x) for x in (tmp_path / "c" / "gold.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(r["provenance"], r["label_origin"], r["synthetic"]) for r in out] == [
        ("human", "team_authored", False), ("llm_authored_claude", "llm_authored_claude", True), ("llm_authored_claude", "llm_authored_claude", True),
        ("unspecified", "unspecified", True), ("unspecified", "unspecified", True), ("unspecified", "unspecified", True), ("unspecified", "unspecified", True)]
    assert sum(r["label_origin"] == "team_authored" for r in out) == 1                                                            # only the one explicit human row
    g = m["gold"]
    assert g["by_provenance"] == {"human": 1, "llm_authored_claude": 2, "unspecified": 4} and g["human_rows"] == 1
    assert g["by_provenance_language"] == {"human": {"hi-Latn": 1}, "llm_authored_claude": {"hi-Latn": 2}, "unspecified": {"en": 4}} and "never reported as human" in g["note"]
    assert json.loads((tmp_path / "c" / "manifest.json").read_text(encoding="utf-8"))["gold"]["by_provenance"] == g["by_provenance"] and "only rows marked human" in m["notice"]


def test_the_four_column_gold_csv_from_before_provenance_existed_still_loads(tmp_path):
    p = tmp_path / "old.csv"
    p.write_text("text,label_id,language,notes\nroad par gadda hai,roads/pothole,hi-Latn,\nlight band hai,street_lighting/light_not_working,hi-Latn,llm_authored_claude; style=sms\n", encoding="utf-8")
    rows, bad = cb.load_gold(p)
    assert not bad and [r["provenance"] for r in rows] == ["unspecified", "llm_authored_claude"]


def test_the_committed_llm_gold_set_is_marked_llm_authored_everywhere_and_never_human():
    from pathlib import Path
    rows, bad = cb.load_gold(Path(__file__).parents[1] / "gold" / "gold_llm_authored_claude_v1.csv")
    assert not bad and len(rows) == 336
    assert {(r["provenance"], r["provenance_source"]) for r in rows} == {("llm_authored_claude", "column")}
    assert {r["language"] for r in rows} == {"en", "hi", "mr", "hi-Latn"} and len({r["label_id"] for r in rows}) == 27


def test_review_sample_is_one_line_per_label_seeded_and_marathi_takes_the_labels_hindi_left_out():
    from pathlib import Path

    from ai.training.src.text_corpus import review_sample as rs
    gold = Path(__file__).parents[1] / "gold" / "gold_llm_authored_claude_v1.csv"
    rows = list(enumerate(cb.load_gold(gold)[0], 1))
    hi = [(i, r) for i, r in rows if r["language"] == "hi"]
    s1, miss1 = rs.stratified_sample(hi, 20, 7)
    assert len(s1) == 20 and len({r["label_id"] for _, r in s1}) == 20 and len(miss1) == 7 and all(r["language"] == "hi" for _, r in s1)
    assert (s1, miss1) == rs.stratified_sample(hi, 20, 7)                                         # fixed seed: reproducible
    assert rs.stratified_sample(hi, 20, 8)[0] != s1                                               # another seed: another sample
    mr = [(i, r) for i, r in rows if r["language"] == "mr"]
    s2, miss2 = rs.stratified_sample(mr, 20, 11, tuple(miss1))
    assert {r["label_id"] for _, r in s2} >= set(miss1) and len(s2) == 20 and not (set(miss1) & set(miss2))              # Marathi covers every label Hindi missed
    assert len({r["label_id"] for _, r in s1} | {r["label_id"] for _, r in s2}) == 27
    doc = rs.build_doc(gold)
    assert doc == rs.build_doc(gold) and doc.count("Labels NOT covered by this sample (7)") == 2 and doc.count("- [ ] row ") == 40 and "never as human gold" in doc


def test_review_doc_is_regenerated_only_inside_its_markers_and_never_overwrites_other_content(tmp_path):
    from pathlib import Path

    from ai.training.src.text_corpus import review_sample as rs
    gold = Path(__file__).parents[1] / "gold" / "gold_llm_authored_claude_v1.csv"
    doc = tmp_path / "I18N_REVIEW.md"
    rs.write_doc(gold, doc)                                                                       # new file: only the generated block
    first = doc.read_text(encoding="utf-8")
    assert first.startswith(rs.BEGIN) and first.rstrip().endswith(rs.END) and "## Hindi (hi)" in first
    other = "## Backend notification templates (Hindi and Marathi): NOT REVIEWED\n\n- [ ] some other lane's strings\n"
    doc.write_text(first.rstrip("\n") + "\n\n" + other, encoding="utf-8")
    stale = doc.read_text(encoding="utf-8").replace("row ", "row STALE ", 3)
    doc.write_text(stale, encoding="utf-8")
    rs.write_doc(gold, doc)                                                                       # regenerate: the block is refreshed, the other section is untouched
    now = doc.read_text(encoding="utf-8")
    assert "STALE" not in now and now.count(rs.BEGIN) == 1 and now.count(rs.END) == 1 and now.endswith(other) and now.index(rs.END) < now.index("## Backend notification templates")
    rs.write_doc(gold, doc)
    assert doc.read_text(encoding="utf-8") == now                                                  # idempotent
    foreign = tmp_path / "other.md"
    foreign.write_text("# someone else's doc\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        rs.write_doc(gold, foreign)
    assert foreign.read_text(encoding="utf-8") == "# someone else's doc\n"


def test_the_committed_review_doc_is_current_with_the_gold_csv_and_keeps_the_other_generated_section(tmp_path):
    from pathlib import Path

    from ai.training.src.text_corpus import review_sample as rs
    root = Path(__file__).parents[3]
    committed = (root / "docs" / "I18N_REVIEW.md").read_text(encoding="utf-8")
    copy = tmp_path / "I18N_REVIEW.md"
    copy.write_text(committed, encoding="utf-8")
    rs.write_doc(root / "ai" / "training" / "gold" / "gold_llm_authored_claude_v1.csv", copy)
    assert copy.read_text(encoding="utf-8") == committed, "docs/I18N_REVIEW.md gold-review block is stale: run python -m ai.training.src.text_corpus.review_sample"
    assert "## Backend notification templates" in committed and "<!-- BEGIN GENERATED: notification templates" in committed


def test_gold_csv_saved_by_excel_or_notepad_with_bom_and_crlf_is_read(tmp_path):
    p = tmp_path / "gold.csv"
    p.write_bytes("﻿text,label_id,language,note\r\nरस्त्यावर खड्डा आहे,roads/pothole,mr,\r\n".encode("utf-8"))
    rows, bad = cb.load_gold(p)
    assert [r["label_id"] for r in rows] == ["roads/pothole"] and rows[0]["language"] == "mr" and not bad
