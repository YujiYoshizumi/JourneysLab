#!/usr/bin/env python3
"""results.csv / results.json から summary.md を生成する。

run_matrix.py から呼ばれるほか、単体でも実行できる。

    python3 eval/summarize.py --results eval/results/20260921-01
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import pathlib
import statistics

TIERS = ["high", "low"]
BUILDS = ["clean", "B01"]

# ステップ3（カートを開く）が、経路の観察対象。
ROUTE_STEP_INDEX = 3


def _rate(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "-"
    return f"{numerator / denominator * 100:.1f}% ({numerator}/{denominator})"


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def _as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def summarize(rows: list, details: list | None = None, env: dict | None = None) -> str:
    details = details or []
    detail_by_key = {
        (d["build"], d["model_tier"], int(d["trial"])): d for d in details
    }

    cells: dict = collections.defaultdict(list)
    for row in rows:
        cells[(row["build"], row["model_tier"])].append(row)

    lines: list = []
    lines.append("# Journeys 判定の評価結果")
    lines.append("")

    # --- 実行環境 --------------------------------------------------------
    if env:
        lines.append("## 実行環境")
        lines.append("")
        lines.append("| 項目 | 値 |")
        lines.append("|---|---|")
        for key in [
            "run_id", "journey", "trials", "agent", "agent_version",
            "android_cli_version", "device_serial", "device_model", "device_sdk",
            "device_release", "device_size", "device_locale",
            "screenrecord_time_limit", "agp_version", "app_source_commit",
            "prompt_sha256", "dry_run",
        ]:
            if key in env:
                lines.append(f"| {key} | `{env[key]}` |")
        lines.append("")
        requested = sorted({r.get("model_requested", "") for r in rows if r.get("model_requested")})
        actual = sorted({r.get("model_actual", "") for r in rows if r.get("model_actual")})
        lines.append(f"- 指定したモデル ID: {', '.join(f'`{m}`' for m in requested) or '-'}")
        lines.append(f"- 実際に使われたモデル ID: {', '.join(f'`{m}`' for m in actual) or '（取得できず）'}")
        lines.append("")

    # --- セルごとの判定内訳 ----------------------------------------------
    lines.append("## セルごとの判定内訳")
    lines.append("")
    lines.append("| ビルド | モデル | 正解 | PASS | FAIL | ERROR | 一貫性 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    consistency_values = []
    for build in BUILDS:
        for tier in TIERS:
            cell_rows = cells.get((build, tier))
            if not cell_rows:
                continue
            counts = collections.Counter(row["verdict"] for row in cell_rows)
            expected = cell_rows[0]["expected"]
            majority = counts.most_common(1)[0][1]
            consistency = majority / len(cell_rows)
            consistency_values.append(consistency)
            judged = [row for row in cell_rows if row["verdict"] in ("PASS", "FAIL")]
            wrong = [row for row in judged if row["verdict"] != expected]
            if not judged:
                label = "判定なし"
            elif not wrong:
                label = "正解どおり"
            elif expected == "FAIL":
                label = f"見逃し {len(wrong)}/{len(judged)}"
            else:
                label = f"誤検知 {len(wrong)}/{len(judged)}"
            lines.append(
                f"| {build} | {tier} | {expected} | {counts.get('PASS', 0)} | "
                f"{counts.get('FAIL', 0)} | {counts.get('ERROR', 0)} | "
                f"{consistency * 100:.0f}% | {label} |"
            )
    lines.append("")

    # --- 見逃し率・誤検知率 ----------------------------------------------
    lines.append("## 見逃し率・誤検知率（モデルごと）")
    lines.append("")
    lines.append("| モデル | 見逃し率（B01 で PASS） | 誤検知率（clean で FAIL） | ERROR 率 |")
    lines.append("|---|---|---|---|")
    for tier in TIERS:
        tier_rows = [row for row in rows if row["model_tier"] == tier]
        if not tier_rows:
            continue
        judged = [row for row in tier_rows if row["verdict"] in ("PASS", "FAIL")]
        bug = [row for row in judged if row["build"] == "B01"]
        clean = [row for row in judged if row["build"] == "clean"]
        misses = [row for row in bug if row["verdict"] == "PASS"]
        false_fails = [row for row in clean if row["verdict"] == "FAIL"]
        errors = [row for row in tier_rows if row["verdict"] == "ERROR"]
        lines.append(
            f"| {tier} | {_rate(len(misses), len(bug))} | "
            f"{_rate(len(false_fails), len(clean))} | {_rate(len(errors), len(tier_rows))} |"
        )
    lines.append("")
    if consistency_values:
        lines.append(f"- 判定の一貫性（セルごとの多数派一致率の平均）: {statistics.mean(consistency_values) * 100:.1f}%")
        lines.append("")

    # --- モデル間の差 ----------------------------------------------------
    lines.append("## モデル間の差（同じビルドでの判定内訳）")
    lines.append("")
    lines.append("| ビルド | high: PASS/FAIL/ERROR | low: PASS/FAIL/ERROR | PASS 率の差（high - low） |")
    lines.append("|---|---|---|---|")
    for build in BUILDS:
        parts = {}
        for tier in TIERS:
            cell_rows = cells.get((build, tier), [])
            counts = collections.Counter(row["verdict"] for row in cell_rows)
            parts[tier] = (counts, len(cell_rows))
        if not parts["high"][1] and not parts["low"][1]:
            continue
        texts = {}
        pass_rates = {}
        for tier in TIERS:
            counts, total = parts[tier]
            texts[tier] = (
                f"{counts.get('PASS', 0)}/{counts.get('FAIL', 0)}/{counts.get('ERROR', 0)}"
                if total else "-"
            )
            pass_rates[tier] = (counts.get("PASS", 0) / total) if total else None
        if pass_rates["high"] is not None and pass_rates["low"] is not None:
            diff = f"{(pass_rates['high'] - pass_rates['low']) * 100:+.1f} pt"
        else:
            diff = "-"
        lines.append(f"| {build} | {texts['high']} | {texts['low']} | {diff} |")
    lines.append("")

    # --- FAIL になったステップの分布 --------------------------------------
    lines.append("## FAIL になったステップの分布")
    lines.append("")
    fail_rows = [row for row in rows if row["verdict"] == "FAIL"]
    if not fail_rows:
        lines.append("FAIL と判定された実行はありません。")
        lines.append("")
    else:
        distribution: dict = collections.defaultdict(lambda: collections.Counter())
        actions: dict = {}
        for row in fail_rows:
            index = _as_int(row.get("failed_step_index"))
            distribution[(row["build"], row["model_tier"])][index] += 1
            if index and row.get("failed_step_action"):
                actions.setdefault(index, row["failed_step_action"])
        lines.append("| ビルド | モデル | FAIL したステップ番号（件数） |")
        lines.append("|---|---|---|")
        for (build, tier), counter in sorted(distribution.items()):
            text = " / ".join(
                f"ステップ{index if index else '不明'}: {count}件"
                for index, count in sorted(counter.items())
            )
            lines.append(f"| {build} | {tier} | {text} |")
        lines.append("")
        if actions:
            lines.append("FAIL したステップの文言:")
            lines.append("")
            for index in sorted(actions):
                lines.append(f"- ステップ{index}: {actions[index]}")
            lines.append("")

    # --- ステップ3の経路の記録欄 ------------------------------------------
    lines.append(f"## ステップ{ROUTE_STEP_INDEX}の経路の記録欄（録画を見て人手で記入する）")
    lines.append("")
    lines.append(
        f"ステップ{ROUTE_STEP_INDEX}「カートを開く」で、カートアイコンとメニューの"
        "どちらが使われたかは、エージェントの自己申告ではなく録画で判断する。"
        "下表の「経路」列に、`カートアイコン` / `メニュー` / `その他` / `到達できず` を記入する。"
    )
    lines.append("")
    lines.append(
        "開始・終了時刻は、エージェントが当該ステップで保存した画面ファイルの更新時刻から"
        "求めた相対ミリ秒（実行開始が 0）。画面ファイルが無い実行は空欄になる。"
    )
    lines.append("")
    lines.append(
        "| ビルド | モデル | 試行 | 判定 | ステップ3 開始(ms) | ステップ3 終了(ms) | 録画 | 該当スクリーンショット | 経路（記入欄） |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for row in rows:
        key = (row["build"], row["model_tier"], _as_int(row["trial"]))
        detail = detail_by_key.get(key)
        start_ms = end_ms = ""
        shots_text = "-"
        if detail:
            steps = detail.get("steps") or []
            target = next((s for s in steps if _as_int(s.get("index")) == ROUTE_STEP_INDEX), None)
            previous = next((s for s in steps if _as_int(s.get("index")) == ROUTE_STEP_INDEX - 1), None)
            times = (target or {}).get("artifact_times_ms") or []
            previous_times = (previous or {}).get("artifact_times_ms") or []
            if times:
                start_ms = str(previous_times[-1] if previous_times else times[0])
                end_ms = str(times[-1])
            if start_ms and end_ms:
                shots_text = f"shots/ の {start_ms}〜{end_ms} ms"
        recordings = row.get("recording_files") or "-"
        lines.append(
            f"| {row['build']} | {row['model_tier']} | {row['trial']} | {row['verdict']} | "
            f"{start_ms or '-'} | {end_ms or '-'} | {recordings} | {shots_text} |  |"
        )
    lines.append("")
    lines.append("各実行の証跡は `results.csv` の `evidence_dir` 列のディレクトリにある。")
    lines.append("")

    # --- 証跡の欠損 ------------------------------------------------------
    lines.append("## 証跡の欠損")
    lines.append("")
    missing = [row for row in rows if _as_bool(row.get("evidence_missing"))]
    no_recording = [row for row in rows if not _as_bool(row.get("recording_captured"))]
    no_shots = [row for row in rows if _as_int(row.get("screenshot_count")) == 0]
    no_logcat = [row for row in rows if not _as_bool(row.get("logcat_captured"))]
    lines.append(f"- 録画が取れなかった実行: {len(no_recording)} 件")
    lines.append(f"- 定点スクリーンショットが取れなかった実行: {len(no_shots)} 件")
    lines.append(f"- logcat が取れなかった実行: {len(no_logcat)} 件")
    lines.append(f"- いずれかが欠損した実行: {len(missing)} 件 / 全 {len(rows)} 件")
    lines.append("")
    if missing:
        lines.append("| ビルド | モデル | 試行 | 録画 | スクリーンショット | logcat |")
        lines.append("|---|---|---|---|---|---|")
        for row in missing:
            lines.append(
                f"| {row['build']} | {row['model_tier']} | {row['trial']} | "
                f"{'あり' if _as_bool(row.get('recording_captured')) else 'なし'} | "
                f"{_as_int(row.get('screenshot_count'))} 枚 | "
                f"{'あり' if _as_bool(row.get('logcat_captured')) else 'なし'} |"
            )
        lines.append("")

    # --- ERROR の内訳 ----------------------------------------------------
    error_rows = [row for row in rows if row["verdict"] == "ERROR"]
    if error_rows:
        lines.append("## ERROR の内訳")
        lines.append("")
        lines.append("| ビルド | モデル | 試行 | 内容 |")
        lines.append("|---|---|---|---|")
        for row in error_rows:
            lines.append(
                f"| {row['build']} | {row['model_tier']} | {row['trial']} | {row.get('error', '')} |"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="eval/results", help="結果ディレクトリ（実行 ID まで）")
    args = parser.parse_args()

    results_dir = pathlib.Path(args.results)
    with (results_dir / "results.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    details = []
    details_path = results_dir / "results.json"
    if details_path.exists():
        details = json.loads(details_path.read_text(encoding="utf-8"))

    env = {}
    env_path = results_dir / "env.json"
    if env_path.exists():
        env = json.loads(env_path.read_text(encoding="utf-8"))

    out = results_dir / "summary.md"
    out.write_text(summarize(rows, details, env), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
