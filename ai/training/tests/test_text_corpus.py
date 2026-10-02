"""LLM-written corpus pipeline: prompts, validation, resumable generation, group-safe splits, gold set (scripted fake provider; no network)."""
import json
import random

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
    assert m["gold"]["rows"] == 2 and (tmp_path / "c" / "gold.jsonl").exists() and json.loads((tmp_path / "c" / "gold.jsonl").read_text().splitlines()[0])["label_origin"] == "team_authored"
