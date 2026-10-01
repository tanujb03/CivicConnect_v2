"""Command-line entry point for real-data acquisition and preparation.

    python -m ai.training.src.data_sources.cli cards
    python -m ai.training.src.data_sources.cli card nyc311
    python -m ai.training.src.data_sources.cli download nyc311 --out /kaggle/working/real/nyc311 --accept-terms nyc311 --acknowledge-unverified-license --since 2024-01-01 --max-rows 50000
    python -m ai.training.src.data_sources.cli figshare-license
    python -m ai.training.src.data_sources.cli profile nyc311 --input raw.jsonl --out profile.json
    python -m ai.training.src.data_sources.cli prepare nyc311 --input raw.jsonl --out prepared/ --accept-terms nyc311 ...
    python -m ai.training.src.data_sources.cli pairs --records prepared/records.jsonl --out pairs/

Outputs must be outside the git repository (or under the gitignored ai/artifacts/real_data).
Downloads and preparation require --accept-terms <source_id> (and --acknowledge-unverified-license while
the card's licence is not verified at the primary source).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ai.training.src.data_sources import prepare as prep
from ai.training.src.data_sources.canonical import CaseRecord
from ai.training.src.data_sources.card_schema import check_terms, list_cards, load_card
from ai.training.src.data_sources.column_roles import TaskPolicy
from ai.training.src.data_sources.download.figshare import FigshareClient
from ai.training.src.data_sources.download.socrata import SocrataDownloader
from ai.training.src.data_sources.errors import DataSourceError
from ai.training.src.data_sources.image_profile import profile_image_dataset
from ai.training.src.data_sources.mapping import DepartmentMapping, MappingTable
from ai.training.src.data_sources.pairs import build_pairs_from_parent_links
from ai.training.src.data_sources.paths import ensure_safe_output
from ai.training.src.data_sources.profile import profile_bmc, profile_tabular
from ai.training.src.io_utils import read_jsonl

RDD_ARTICLE_ID = 21431547


def _gate(card, a) -> None:
    check_terms(card, accepted=a.accept_terms or [], ack_unverified=a.acknowledge_unverified_license)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def terms(p):
        p.add_argument("--accept-terms", action="append", default=[], metavar="SOURCE_ID")
        p.add_argument("--acknowledge-unverified-license", action="store_true")

    sub.add_parser("cards")
    c = sub.add_parser("card"); c.add_argument("source")
    d = sub.add_parser("download"); d.add_argument("source", choices=["nyc311", "chicago311"]); d.add_argument("--out", type=Path, required=True)
    d.add_argument("--since"); d.add_argument("--until"); d.add_argument("--where"); d.add_argument("--select")
    d.add_argument("--max-rows", type=int, default=50_000); d.add_argument("--page-size", type=int, default=5_000); terms(d)
    sub.add_parser("figshare-license")
    sub.add_parser("figshare-files")
    f2 = sub.add_parser("figshare-download"); f2.add_argument("--file-name", required=True); f2.add_argument("--out", type=Path, required=True)
    f2.add_argument("--allow-gb", type=float, default=2.0); terms(f2)
    pr = sub.add_parser("profile"); pr.add_argument("source", choices=["nyc311", "chicago311", "bmc_mumbai"]); pr.add_argument("--input", type=Path, required=True)
    pr.add_argument("--out", type=Path, required=True); pr.add_argument("--max-rows", type=int, default=200_000)
    pr.add_argument("--role-map", type=Path, help="JSON {column: role} chosen after reading the data dictionary (bmc_mumbai)")
    pi = sub.add_parser("profile-images"); pi.add_argument("root", type=Path); pi.add_argument("--out", type=Path, required=True)
    la = sub.add_parser("leakage-audit"); la.add_argument("--records", type=Path, required=True); la.add_argument("--source", default="bmc_mumbai")
    la.add_argument("--task"); la.add_argument("--out", type=Path)
    sub.add_parser("matrix")
    pp = sub.add_parser("prepare"); pp.add_argument("source", choices=["nyc311", "chicago311", "rdd2022", "rdd2020", "bmc_mumbai", "bharatpothole", "mumbai_nashik_road_surface", "idd"])
    pp.add_argument("--role-map", type=Path); pp.add_argument("--confirm-citizen-text", action="store_true", help="bmc_mumbai: you inspected the description column and it is citizen-written")
    pp.add_argument("--row-index-ids", action="store_true"); pp.add_argument("--resolution-unit", choices=["hours", "days"])
    pp.add_argument("--format", choices=["voc", "yolo", "coco", "folder"], help="annotation format of image datasets (never guessed)")
    pp.add_argument("--class-names-file", type=Path); pp.add_argument("--group-by", choices=["dir", "regex", "block", "none"], default="dir")
    pp.add_argument("--group-regex"); pp.add_argument("--block-size", type=int, default=100); pp.add_argument("--label-from", choices=["parent", "top", "all"], default="parent")
    pp.add_argument("--holdout-fraction", type=float, default=0.0); pp.add_argument("--holdout-seed", type=int, default=0)
    pp.add_argument("--input", type=Path, required=True); pp.add_argument("--out", type=Path, required=True)
    pp.add_argument("--max-rows", type=int); pp.add_argument("--sample-seed", type=int, default=0); pp.add_argument("--since"); pp.add_argument("--until")
    pp.add_argument("--holdout-after", help="YYYY-MM-DD: requests on/after this date form the holdout (311 sources)")
    pp.add_argument("--include-category-text", action="store_true", help="emit category text as text (label leakage; flagged source_category_text)")
    pp.add_argument("--exclude-legacy", action="store_true")
    pp.add_argument("--countries", nargs="*"); pp.add_argument("--holdout-countries", nargs="*")
    pp.add_argument("--check-images", action="store_true"); pp.add_argument("--include-unannotated", action="store_true")
    pp.add_argument("--max-images", type=int); terms(pp)
    pa = sub.add_parser("pairs"); pa.add_argument("--records", type=Path, required=True); pa.add_argument("--out", type=Path, required=True)
    pa.add_argument("--neg-per-pos", type=int, default=1); pa.add_argument("--radius-m", type=float, default=150.0)
    pa.add_argument("--window-days", type=float, default=30.0); pa.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)

    try:
        if a.cmd == "cards":
            for card in list_cards():
                print(f"{card.id:16s} {card.kind:11s} licence={card.license.status:15s} supports={[s.capability for s in card.supports]}")
            return 0
        if a.cmd == "card":
            card = load_card(a.source)
            print(card.terms_summary()); print(); print(card.model_dump_json(indent=2))
            return 0
        if a.cmd == "figshare-license":
            print(json.dumps(FigshareClient(RDD_ARTICLE_ID).show_license(), indent=2))
            print("\nCompare with ai/training/src/data_sources/cards/rdd2022.json and update the card (status=VERIFIED_PRIMARY).")
            return 0
        if a.cmd == "figshare-files":
            for x in FigshareClient(RDD_ARTICLE_ID).list_files():
                print(f"{x['name']:60s} {(x['size'] or 0) / 1e6:10.1f} MB  md5={x['md5']}")
            return 0
        if a.cmd == "figshare-download":
            card = load_card("rdd2022"); _gate(card, a)
            out = ensure_safe_output(a.out)
            cl = FigshareClient(RDD_ARTICLE_ID)
            file = next((x for x in cl.list_files() if x["name"] == a.file_name), None)
            if file is None:
                raise DataSourceError(f"file {a.file_name!r} not found; run figshare-files")
            print("downloaded:", cl.download(file, out, allow_gb=a.allow_gb))
            return 0
        if a.cmd == "download":
            card = load_card(a.source); _gate(card, a)
            out = ensure_safe_output(a.out)
            raw = SocrataDownloader(card, app_token=os.environ.get("SOCRATA_APP_TOKEN")).download(
                out, since=a.since, until=a.until, where=a.where, select=a.select, max_rows=a.max_rows, page_size=a.page_size)
            print("downloaded:", raw)
            return 0
        if a.cmd == "matrix":
            from ai.training.src.data_sources.task_matrix import render_markdown
            print(render_markdown())
            return 0
        if a.cmd == "profile-images":
            rep = profile_image_dataset(a.root)
            out = ensure_safe_output(a.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"{rep['n_images']} images; format candidates (NOT decisions): {rep['format_candidates']}; class files: {rep['class_name_files']}; videos: {rep['n_videos']}")
            for w in rep["warnings"]:
                print("WARNING:", w)
            return 0
        if a.cmd == "leakage-audit":
            policy = TaskPolicy.load(a.source)
            recs = [CaseRecord.model_validate(r) for r in read_jsonl(a.records)]
            from ai.training.src.data_sources.leakage import audit_task, views_clean
            tasks = [a.task] if a.task else [t for t, s in policy.tasks.items() if s.leakage_checks]
            rep = {"views_clean": views_clean(recs, policy), "tasks": {t: audit_task(recs, policy, t) for t in tasks}}
            if a.out:
                o = ensure_safe_output(a.out)
                o.parent.mkdir(parents=True, exist_ok=True)
                o.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            for t, r in rep["tasks"].items():
                print(f"{t}: {'PASS' if r['passed'] else 'BLOCKED'} {r['blocking']}")
            return 0 if all(r["passed"] for r in rep["tasks"].values()) and not rep["views_clean"]["violations"] else 3
        if a.cmd == "profile" and a.source == "bmc_mumbai":
            card = load_card(a.source)
            role_map = json.loads(a.role_map.read_text(encoding="utf-8")) if a.role_map else None
            rep = profile_bmc(a.input, TaskPolicy.load("bmc_mumbai"), role_map, MappingTable.load(card.mapping_id), DepartmentMapping.load("bmc_mumbai_departments"), max_rows=a.max_rows)
            out = ensure_safe_output(a.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"profiled {rep['rows_profiled']} rows; unclassified (default-denied): {rep['unclassified_columns_default_denied']}; PII ignored: {rep['pii_columns_never_read']}; "
                  f"sensitive ignored: {rep['sensitive_columns_never_read']}; missing roles: {rep['missing_roles_of_interest']}")
            print("runnable tasks:", [t for t, v in rep["tasks_runnable_given_columns"].items() if v["runnable"]])
            return 0
        if a.cmd == "profile":
            card = load_card(a.source)
            from ai.training.src.data_sources.adapters.chicago311 import Chicago311Adapter
            from ai.training.src.data_sources.adapters.nyc311 import NYC311Adapter
            ad = {"nyc311": NYC311Adapter, "chicago311": Chicago311Adapter}[a.source]
            mapping = MappingTable.load(card.mapping_id)
            rep = profile_tabular(a.input, ad.aliases, mapping.raw["match_fields"], mapping, max_rows=a.max_rows)
            out = ensure_safe_output(a.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            cov = rep["draft_mapping_coverage"]
            print(f"profiled {rep['rows_profiled']} rows; unresolved aliases: {rep['unresolved_aliases']}; free-text candidates: "
                  f"{[c['column'] for c in rep['candidate_free_text_columns']]}; draft mapping coverage: {cov['share']}")
            return 0
        if a.cmd == "prepare":
            card = load_card(a.source); _gate(card, a)
            out = ensure_safe_output(a.out)
            if card.adapter is None or a.source == "idd":
                raise DataSourceError(f"{a.source} has no adapter: it is documented as an optional/future source and is not part of V1")
            if a.source == "bmc_mumbai":
                role_map = json.loads(a.role_map.read_text(encoding="utf-8")) if a.role_map else None
                m = prep.prepare_bmc(card, a.input, out, role_map=role_map, max_rows=a.max_rows, sample_seed=a.sample_seed, since=a.since, until=a.until,
                                     holdout_after=a.holdout_after, confirm_citizen_text=a.confirm_citizen_text, row_index_ids=a.row_index_ids,
                                     resolution_unit=a.resolution_unit)
            elif card.adapter == "detection":
                if not a.format:
                    raise DataSourceError("--format {voc,yolo,coco,folder} is required: annotation formats are never guessed (run profile-images first)")
                m = prep.prepare_images(card, a.input, out, fmt=a.format, class_names_file=a.class_names_file, group_by=a.group_by, group_regex=a.group_regex,
                                        block_size=a.block_size, label_from=a.label_from, holdout_fraction=a.holdout_fraction, holdout_seed=a.holdout_seed,
                                        max_images=a.max_images)
            elif card.adapter == "rdd2022":
                m = prep.prepare_rdd(card, a.input, out, countries=set(a.countries) if a.countries else None,
                                     holdout_countries=set(a.holdout_countries) if a.holdout_countries else None,
                                     check_images=a.check_images, include_unannotated=a.include_unannotated, max_images=a.max_images)
            else:
                m = prep.prepare_tabular(card, a.input, out, max_rows=a.max_rows, sample_seed=a.sample_seed, since=a.since, until=a.until,
                                         holdout_after=a.holdout_after, include_category_text=a.include_category_text, exclude_legacy=a.exclude_legacy)
            print(f"prepared {m['records']} records -> {out}")
            cov = m.get("coverage") or m.get("box_mapping_coverage") or m.get("box_or_label_mapping_coverage")
            print("mapping coverage:", json.dumps(cov["share"]))
            return 0
        if a.cmd == "pairs":
            out = ensure_safe_output(a.out)
            recs = [CaseRecord.model_validate(r) for r in read_jsonl(a.records)]
            pairs, stats = build_pairs_from_parent_links(recs, neg_per_pos=a.neg_per_pos, radius_m=a.radius_m, window_days=a.window_days, seed=a.seed)
            out.mkdir(parents=True, exist_ok=True)
            with (out / "pairs.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
                for p in pairs:
                    fh.write(p.model_dump_json() + "\n")
            (out / "PAIRS_MANIFEST.json").write_text(json.dumps({"stats": stats, "radius_m": a.radius_m, "window_days": a.window_days, "seed": a.seed,
                                                                 "source_records": a.records.name, "n_pairs": len(pairs)}, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(stats, indent=2))
            if not stats["positives"]:
                print("NOTE: no duplicate pairs found -- the file may lack duplicate/parent columns (see `profile`).", file=sys.stderr)
            return 0
    except DataSourceError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
