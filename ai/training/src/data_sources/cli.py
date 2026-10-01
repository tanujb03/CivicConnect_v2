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
from ai.training.src.data_sources.download.figshare import FigshareClient
from ai.training.src.data_sources.download.socrata import SocrataDownloader
from ai.training.src.data_sources.errors import DataSourceError
from ai.training.src.data_sources.mapping import MappingTable
from ai.training.src.data_sources.pairs import build_pairs_from_parent_links
from ai.training.src.data_sources.paths import ensure_safe_output
from ai.training.src.data_sources.profile import profile_tabular
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
    pr = sub.add_parser("profile"); pr.add_argument("source", choices=["nyc311", "chicago311"]); pr.add_argument("--input", type=Path, required=True)
    pr.add_argument("--out", type=Path, required=True); pr.add_argument("--max-rows", type=int, default=200_000)
    pp = sub.add_parser("prepare"); pp.add_argument("source", choices=["nyc311", "chicago311", "rdd2022"])
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
            if a.source == "rdd2022":
                m = prep.prepare_rdd(card, a.input, out, countries=set(a.countries) if a.countries else None,
                                     holdout_countries=set(a.holdout_countries) if a.holdout_countries else None,
                                     check_images=a.check_images, include_unannotated=a.include_unannotated, max_images=a.max_images)
            else:
                m = prep.prepare_tabular(card, a.input, out, max_rows=a.max_rows, sample_seed=a.sample_seed, since=a.since, until=a.until,
                                         holdout_after=a.holdout_after, include_category_text=a.include_category_text, exclude_legacy=a.exclude_legacy)
            print(f"prepared {m['records']} records -> {out}")
            print("mapping coverage:", json.dumps(m.get("coverage", m.get("box_mapping_coverage"))["share"]))
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
