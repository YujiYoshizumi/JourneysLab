#!/usr/bin/env python3
"""Journeys の判定を測る評価ランナー。

1本の Journey（J01）を、2種類のビルド（clean / B01）× 2種類のモデル（high / low）で
N 回ずつ実行し、判定と証跡を集める。

実行経路
--------
経路1: Android CLI に Journey を直接実行し、かつ判定モデルを指定できるサブコマンドが
       あればそれを使う。起動時に `android help` を調べて判定する。
経路2: 被験エージェントをヘッドレスで起動し、公式の Journeys スキルに実行させる。
       起動コマンドとモデル指定は eval/models.yaml から組み立てる。

使い方
------
    # 実行部分をモックにした通し確認（デバイス不要）
    python3 eval/run_matrix.py --dry-run

    # 実機/エミュレータでの実行
    python3 eval/run_matrix.py --device emulator-5554 --trials 10 --run-id 20260921-01
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime
import hashlib
import json
import os
import pathlib
import random
import re
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import evidence  # noqa: E402
import summarize  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval"
APP_ID = "com.example.journeylab"
LAUNCH_COMPONENT = f"{APP_ID}/.MainActivity"
JOURNEY_DIR = ROOT / "app" / "src" / "journeysTest"

# ビルド名 → Gradle プロパティ（README のビルド名対応表と同じ内容）
BUILD_PROPERTIES = {
    "clean": ["-Pjourneylab.bugs="],
    "B01": ["-Pjourneylab.bugs=B01"],
}


# --------------------------------------------------------------------------- #
# 最小限の YAML 読み取り
# --------------------------------------------------------------------------- #
def load_models_yaml(path: pathlib.Path) -> dict:
    """models.yaml を読む。

    PyYAML があればそれを使い、無ければ本ファイル用の限定的な書式
    （`key: 値`、`key: [JSON 配列]`、1段ネストのマッピング）だけを読む。
    """
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError:
        pass

    result: dict = {}
    current_parent: str | None = None
    current_child: str | None = None
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].rstrip() if " #" in raw else raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        key, _, value = line.strip().partition(":")
        key, value = key.strip(), value.strip()

        if indent == 0:
            current_parent, current_child = None, None
            if value == "":
                result[key] = {}
                current_parent = key
            else:
                result[key] = json.loads(value) if value.startswith("[") else value.strip('"\'')
        elif indent == 2 and current_parent:
            if value == "":
                result[current_parent][key] = {}
                current_child = key
            else:
                result[current_parent][key] = value.strip('"\'')
        elif indent >= 4 and current_parent and current_child:
            result[current_parent][current_child][key] = value.strip('"\'')
    return result


# --------------------------------------------------------------------------- #
# データ構造
# --------------------------------------------------------------------------- #
@dataclasses.dataclass
class Cell:
    case_id: str
    build: str
    model_tier: str
    expected: str


@dataclasses.dataclass
class RunResult:
    case_id: str
    build: str
    model_tier: str
    trial: int
    expected: str
    verdict: str  # PASS / FAIL / ERROR
    agent: str
    agent_version: str
    model_requested: str
    model_actual: str
    prompt_sha256: str
    started_at: str
    duration_sec: float
    evidence_dir: str
    recording_files: str
    screenshot_count: int
    logcat_captured: bool
    recording_captured: bool
    failed_step_index: int
    failed_step_action: str
    steps: list
    error: str = ""

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def evidence_missing(self) -> bool:
        return not (self.recording_captured and self.screenshot_count > 0 and self.logcat_captured)


# --------------------------------------------------------------------------- #
# 外部コマンド
# --------------------------------------------------------------------------- #
def run(cmd: list, cwd: pathlib.Path | None = None, timeout: int | None = None):
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout
    )


def adb(device: str | None, args: list, timeout: int = 120):
    return run(evidence.adb_args(device) + args, timeout=timeout)


def first_line(cmd: list) -> str:
    try:
        proc = run(cmd, timeout=120)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "unknown"
    text = (proc.stdout or proc.stderr or "").strip().splitlines()
    return text[0].strip() if text else "unknown"


# --------------------------------------------------------------------------- #
# 実行経路の判定
# --------------------------------------------------------------------------- #
JOURNEY_SUBCOMMAND = re.compile(r"^\s{2}(journey|journeys)\b", re.MULTILINE)


def detect_route1() -> str | None:
    """Android CLI に Journey を直接実行するサブコマンドがあるか調べる。"""
    try:
        proc = run(["android", "help"], timeout=300)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    match = JOURNEY_SUBCOMMAND.search(proc.stdout)
    return match.group(1) if match else None


# --------------------------------------------------------------------------- #
# ビルド
# --------------------------------------------------------------------------- #
def build_apk(build: str, apk_dir: pathlib.Path, dry_run: bool, clean_build: bool) -> pathlib.Path:
    """ビルド構成ごとに APK を作り、バグ ID を含まないランダムな名前で保存する。"""
    apk_dir.mkdir(parents=True, exist_ok=True)
    target = apk_dir / f"{uuid.uuid4().hex[:12]}.apk"

    if dry_run:
        target.write_bytes(b"dry-run placeholder")
        return target

    tasks = (["clean"] if clean_build else []) + [":app:assembleDebug"]
    proc = run([str(ROOT / "gradlew"), *tasks, *BUILD_PROPERTIES[build]], cwd=ROOT, timeout=3600)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout[-4000:] + proc.stderr[-4000:])
        raise RuntimeError(f"ビルドに失敗しました: {build}")

    built = ROOT / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
    shutil.copy2(built, target)
    return target


# --------------------------------------------------------------------------- #
# 判定の取り出し
# --------------------------------------------------------------------------- #
VERDICT_BLOCK = re.compile(r"<<<VERDICT>>>(.*?)<<<END>>>", re.DOTALL)
JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def load_journey_actions(path: pathlib.Path) -> list[str]:
    """Journey XML から、定義された順序で手順の文言を読む。"""
    root = ET.parse(path).getroot()
    actions = ["".join(action.itertext()).strip() for action in root.findall("./actions/action")]
    if root.tag != "journey" or not actions or any(not action for action in actions):
        raise ValueError(f"Journey に有効な手順が定義されていません: {path}")
    return actions


def extract_verdict(text: str) -> dict | None:
    """エージェントの出力から所定の JSON を取り出す。"""
    if not text:
        return None
    match = VERDICT_BLOCK.search(text)
    candidate = match.group(1) if match else None
    if candidate is None:
        fallback = JSON_BLOCK.search(text)
        candidate = fallback.group(0) if fallback else None
    if candidate is None:
        return None
    inner = JSON_BLOCK.search(candidate)
    if inner is None:
        return None
    try:
        payload = json.loads(inner.group(0))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def normalize_steps(payload: dict, workdir: pathlib.Path, t0_epoch: float) -> list:
    """steps を正規化し、artifacts のファイル更新時刻から相対時刻を推定する。"""
    raw = payload.get("results")
    if not isinstance(raw, list):
        return []

    steps = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            return []
        artifacts = item.get("artifacts") or []
        if not isinstance(artifacts, list):
            artifacts = [str(artifacts)]

        times = []
        resolved = []
        for artifact in artifacts:
            path = pathlib.Path(str(artifact))
            if not path.is_absolute():
                path = workdir / path
            if path.exists():
                resolved.append(str(path))
                times.append(int((path.stat().st_mtime - t0_epoch) * 1000))
            else:
                resolved.append(str(artifact))

        steps.append(
            {
                "index": index,
                "action": str(item.get("action", "")),
                "status": str(item.get("status", "")).upper(),
                "reasoning": str(item.get("reasoning", "")),
                "artifacts": resolved,
                "artifact_times_ms": sorted(times),
            }
        )
    return steps


def derive_verdict(steps: list, expected_actions: list[str]) -> tuple[str, str]:
    """Journey 定義と報告を照合し、全体の判定と入力不備の理由を返す。"""
    if not expected_actions:
        return "ERROR", "Journey に手順が定義されていません"
    if not steps:
        return "ERROR", "有効なステップの判定結果を取り出せませんでした"
    if len(steps) > len(expected_actions):
        return "ERROR", f"報告された手順数が Journey 定義を超えています（{len(steps)}/{len(expected_actions)}）"

    for index, (step, expected_action) in enumerate(zip(steps, expected_actions), start=1):
        if step.get("index") != index:
            return "ERROR", f"ステップ{index}の番号が連続していません"
        action = " ".join(str(step.get("action", "")).split())
        if action != " ".join(expected_action.split()):
            return "ERROR", f"ステップ{index}の文言または順序が Journey 定義と一致しません"
        if step.get("status") not in {"PASSED", "FAILED"}:
            return "ERROR", f"ステップ{index}の status が PASSED / FAILED ではありません"

    # 失敗した手順までの報告でも、Journey 全体の失敗は確定できる。
    if any(step["status"] == "FAILED" for step in steps):
        return "FAIL", ""
    if len(steps) < len(expected_actions):
        return "ERROR", f"成功と報告された手順が不足しています（{len(steps)}/{len(expected_actions)}）"
    return "PASS", ""


def first_failed_step(steps: list):
    for step in steps:
        if step["status"] == "FAILED":
            return step["index"], step["action"]
    return 0, ""


# --------------------------------------------------------------------------- #
# エージェント実行（経路2）
# --------------------------------------------------------------------------- #
class Route2Runner:
    def __init__(self, models_config: dict, timeout: int):
        self.agent = str(models_config.get("agent", "unknown"))
        self.command_template = models_config.get("command")
        if not isinstance(self.command_template, list):
            raise SystemExit("eval/models.yaml に command（配列）がありません")
        self.tiers = models_config.get("tiers") or {}
        self.timeout = timeout
        self.version = first_line(["claude", "--version"]) if self.agent == "claude-code" else "unknown"

    def model_for(self, tier: str) -> str:
        try:
            return str(self.tiers[tier]["model"])
        except (KeyError, TypeError):
            raise SystemExit(f"eval/models.yaml に tiers.{tier}.model がありません")

    def execute(self, workdir: pathlib.Path, prompt: str, tier: str):
        """(stdout, stderr, envelope, error) を返す。"""
        model = self.model_for(tier)
        cmd = [part.replace("{prompt}", prompt).replace("{model}", model) for part in self.command_template]
        try:
            proc = subprocess.run(
                cmd, cwd=str(workdir), capture_output=True, text=True, timeout=self.timeout
            )
        except FileNotFoundError:
            return "", "", None, f"エージェントのコマンドが見つかりません: {cmd[0]}"
        except subprocess.TimeoutExpired:
            return "", "", None, f"エージェントの実行がタイムアウトしました（{self.timeout}s）"

        envelope = None
        try:
            envelope = json.loads(proc.stdout)
        except json.JSONDecodeError:
            envelope = None

        error = ""
        if proc.returncode != 0:
            error = f"エージェントが異常終了しました (exit={proc.returncode}): {proc.stderr[-400:]}"
        return proc.stdout, proc.stderr, envelope, error


class MockRunner:
    """--dry-run 用。エージェントを呼ばずに、それらしい結果を作る。"""

    agent = "mock"
    version = "mock-0"

    def __init__(self, models_config: dict, seed: int = 20260922):
        self.tiers = models_config.get("tiers") or {}
        self.random = random.Random(seed)

    def model_for(self, tier: str) -> str:
        try:
            return str(self.tiers[tier]["model"])
        except (KeyError, TypeError):
            return f"mock-{tier}"

    def execute_mock(self, cell: Cell, journey_path: pathlib.Path, workdir: pathlib.Path) -> dict:
        actions = load_journey_actions(journey_path)
        roll = self.random.random()
        # 低性能ティアのほうが ERROR と見逃しを多く出す、という作り物の傾向を入れておく
        error_rate = 0.05 if cell.model_tier == "low" else 0.02
        miss_rate = 0.55 if cell.model_tier == "low" else 0.35
        if roll < error_rate:
            return {"__error__": "所定の JSON を取り出せませんでした（モック）"}

        verdict = cell.expected
        if cell.expected == "FAIL" and roll < miss_rate:
            verdict = "PASS"
        elif cell.expected == "PASS" and roll > 0.93:
            verdict = "FAIL"

        # FAIL のときは「カートを開く」（ステップ3）で落ちたことにする。
        # Journey は最初の失敗で評価が終わるため、それ以降のステップは報告されない。
        failed_at = 2 if verdict == "FAIL" else None
        results = []
        for index, action in enumerate(actions):
            if failed_at is not None and index > failed_at:
                break
            status = "FAILED" if index == failed_at else "PASSED"
            shot = workdir / f"agent_step{index + 1}.png"
            shot.write_bytes(b"mock")
            results.append(
                {
                    "action": action,
                    "status": status,
                    "reasoning": "モック実行",
                    "artifacts": [shot.name],
                }
            )
        return {"journey": cell.case_id, "results": results}


# --------------------------------------------------------------------------- #
# 1 回の実行
# --------------------------------------------------------------------------- #
def make_workdir(base: pathlib.Path, cell: Cell, trial: int, apk: pathlib.Path) -> pathlib.Path:
    """ソースコードを含まない作業ディレクトリ（APK と journey ファイルのみ）。"""
    workdir = base / f"{cell.build}_{cell.model_tier}_{trial}"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    shutil.copy2(apk, workdir / apk.name)
    journey = JOURNEY_DIR / f"{cell.case_id}.journey.xml"
    shutil.copy2(journey, workdir / journey.name)
    return workdir


def display_path(path: pathlib.Path) -> str:
    """結果に記録するパス。リポジトリ内なら相対、外なら絶対で表す。"""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def error_result(
    cell: Cell,
    trial: int,
    runner,
    prompt_sha: str,
    started_at: datetime.datetime,
    evidence_dir: pathlib.Path,
    message: str,
) -> RunResult:
    """試行を開始できなかった場合に、ERROR として記録するための結果を作る。"""
    return RunResult(
        case_id=cell.case_id,
        build=cell.build,
        model_tier=cell.model_tier,
        trial=trial,
        expected=cell.expected,
        verdict="ERROR",
        agent=runner.agent,
        agent_version=runner.version,
        model_requested=runner.model_for(cell.model_tier),
        model_actual="",
        prompt_sha256=prompt_sha,
        started_at=started_at.isoformat(timespec="seconds"),
        duration_sec=0.0,
        evidence_dir=display_path(evidence_dir),
        recording_files="",
        screenshot_count=0,
        logcat_captured=False,
        recording_captured=False,
        failed_step_index=0,
        failed_step_action="",
        steps=[],
        error=message,
    )


def execute_cell_once(
    cell: Cell,
    trial: int,
    apk: pathlib.Path,
    runner,
    prompt_template: str,
    prompt_sha: str,
    device: str | None,
    workdir_base: pathlib.Path,
    results_dir: pathlib.Path,
    dry_run: bool,
) -> RunResult:
    journey_name = f"{cell.case_id}.journey.xml"
    workdir = make_workdir(workdir_base, cell, trial, apk)
    journey_path = workdir / journey_name
    evidence_dir = results_dir / cell.build / cell.model_tier / f"{trial:02d}"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.datetime.now()
    t0 = time.time()

    try:
        expected_actions = load_journey_actions(journey_path)
    except (ValueError, ET.ParseError, OSError) as exc:
        # Journey が読めない場合、この試行だけを ERROR として記録し、残りの実行は続ける。
        return error_result(
            cell, trial, runner, prompt_sha, started_at, evidence_dir,
            f"Journey を読み込めませんでした: {exc}",
        )

    recorder = None
    shotter = None
    logcat_ok = False

    if dry_run:
        # 証跡の入れ物だけ作って、取得できたことにする
        (evidence_dir / "rec_0001.mp4").write_bytes(b"dry-run")
        (evidence_dir / "shots").mkdir(exist_ok=True)
        (evidence_dir / "shots" / "0001_00000000ms.png").write_bytes(b"dry-run")
        (evidence_dir / "logcat.txt").write_text("dry-run\n", encoding="utf-8")
        logcat_ok = True
        payload = runner.execute_mock(cell, journey_path, workdir)
        error = payload.pop("__error__", "")
        stdout = json.dumps(payload, ensure_ascii=False)
        envelope = {"result": f"<<<VERDICT>>>{stdout}<<<END>>>",
                    "modelUsage": {runner.model_for(cell.model_tier): {}}}
        stderr = ""
        recording_files = ["rec_0001.mp4"]
        shots = [{"file": "shots/0001_00000000ms.png", "elapsed_ms": 0}]
        recording_captured = True
        capture_errors: list = []
    else:
        # --- 端末の準備 ------------------------------------------------- #
        adb(device, ["install", "-r", "-t", str(apk)], timeout=600)
        adb(device, ["shell", "pm", "clear", APP_ID])
        evidence.clear_logcat(device)
        adb(device, ["shell", "am", "start", "-n", LAUNCH_COMPONENT])
        time.sleep(3)

        # --- 証跡の取得開始 --------------------------------------------- #
        recorder = evidence.ScreenRecorder(device, evidence_dir, t0)
        recorder.start()
        shotter = evidence.Screenshotter(device, evidence_dir / "shots", t0)
        shotter.start()

        prompt = (
            prompt_template
            .replace("{JOURNEY_FILE}", journey_name)
            .replace("{PACKAGE_NAME}", APP_ID)
        )
        stdout, stderr, envelope, error = runner.execute(workdir, prompt, cell.model_tier)

        # --- 証跡の取得終了 --------------------------------------------- #
        shotter.stop()
        recorder.stop()
        logcat_ok = evidence.dump_logcat(device, evidence_dir / "logcat.txt")
        recording_files = [s["file"] for s in recorder.segments if s.get("file")]
        shots = shotter.shots
        recording_captured = recorder.captured
        capture_errors = recorder.errors + shotter.errors

    duration = time.time() - t0

    (evidence_dir / "agent_stdout.log").write_text(
        (stdout or "") + ("\n--- stderr ---\n" + stderr if stderr else ""),
        encoding="utf-8", errors="replace",
    )

    # --- 判定の取り出し ------------------------------------------------- #
    agent_text = ""
    model_actual = ""
    if isinstance(envelope, dict):
        agent_text = str(envelope.get("result", ""))
        usage = envelope.get("modelUsage")
        if isinstance(usage, dict) and usage:
            model_actual = ",".join(sorted(usage.keys()))
    if not agent_text:
        agent_text = stdout or ""

    payload = extract_verdict(agent_text)
    steps = normalize_steps(payload, workdir, t0) if payload else []
    verdict, verdict_error = derive_verdict(steps, expected_actions)
    if verdict == "ERROR" and not error:
        error = verdict_error

    failed_index, failed_action = first_failed_step(steps)

    (evidence_dir / "verdict.json").write_text(
        json.dumps({"payload": payload, "steps": steps}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (evidence_dir / "timeline.json").write_text(
        json.dumps(
            {
                "started_at": started_at.isoformat(timespec="seconds"),
                "duration_sec": round(duration, 2),
                "recordings": recorder.segments if recorder else
                    [{"index": 1, "file": "rec_0001.mp4", "start_ms": 0, "end_ms": int(duration * 1000)}],
                "screenshots": shots,
                "steps": [
                    {"index": step["index"], "status": step["status"],
                     "artifact_times_ms": step["artifact_times_ms"]}
                    for step in steps
                ],
                "capture_errors": capture_errors,
            },
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )

    return RunResult(
        case_id=cell.case_id,
        build=cell.build,
        model_tier=cell.model_tier,
        trial=trial,
        expected=cell.expected,
        verdict=verdict,
        agent=runner.agent,
        agent_version=runner.version,
        model_requested=runner.model_for(cell.model_tier),
        model_actual=model_actual,
        prompt_sha256=prompt_sha,
        started_at=started_at.isoformat(timespec="seconds"),
        duration_sec=round(duration, 2),
        evidence_dir=display_path(evidence_dir),
        recording_files=";".join(recording_files),
        screenshot_count=len(shots),
        logcat_captured=logcat_ok,
        recording_captured=recording_captured,
        failed_step_index=failed_index,
        failed_step_action=failed_action,
        steps=steps,
        error=error,
    )


# --------------------------------------------------------------------------- #
# 入出力
# --------------------------------------------------------------------------- #
def load_matrix(path: pathlib.Path) -> list:
    with path.open(encoding="utf-8", newline="") as f:
        return [
            Cell(row["case_id"], row["build"], row["model_tier"], row["expected"])
            for row in csv.DictReader(f)
        ]


RESULT_FIELDS = [
    "case_id", "build", "model_tier", "trial", "expected", "verdict",
    "agent", "agent_version", "model_requested", "model_actual", "prompt_sha256",
    "started_at", "duration_sec", "evidence_dir", "recording_files",
    "screenshot_count", "logcat_captured", "recording_captured",
    "failed_step_index", "failed_step_action", "total_steps", "evidence_missing", "error",
]


def result_row(result: RunResult) -> dict:
    row = {key: getattr(result, key) for key in RESULT_FIELDS if hasattr(result, key)}
    row["total_steps"] = result.total_steps
    row["evidence_missing"] = result.evidence_missing
    return row


def write_results(results: list, results_dir: pathlib.Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    with (results_dir / "results.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result_row(result))

    (results_dir / "results.json").write_text(
        json.dumps([dataclasses.asdict(result) for result in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def collect_environment(device: str | None, runner, dry_run: bool) -> dict:
    if dry_run:
        return {"dry_run": True}
    return {
        "agent": runner.agent,
        "agent_version": runner.version,
        "android_cli_version": first_line(["android", "--version"]),
        "device_serial": device or "(既定のデバイス)",
        "device_model": adb(device, ["shell", "getprop", "ro.product.model"]).stdout.strip(),
        "device_sdk": adb(device, ["shell", "getprop", "ro.build.version.sdk"]).stdout.strip(),
        "device_release": adb(device, ["shell", "getprop", "ro.build.version.release"]).stdout.strip(),
        "device_size": adb(device, ["shell", "wm", "size"]).stdout.strip(),
        "device_locale": adb(device, ["shell", "getprop", "persist.sys.locale"]).stdout.strip(),
        "screenrecord_time_limit": evidence.probe_screenrecord_limit(device),
        "agp_version": read_agp_version(),
        "app_source_commit": git_commit(),
    }


def read_agp_version() -> str:
    toml = (ROOT / "gradle" / "libs.versions.toml").read_text(encoding="utf-8")
    match = re.search(r'androidGradlePlugin\s*=\s*"([^"]+)"', toml)
    return match.group(1) if match else "unknown"


def git_commit() -> str:
    """このプロジェクト自身のコミットハッシュ。別リポジトリの中に置かれている場合は誤解を避けて明示する。"""
    toplevel = run(["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"], timeout=30)
    if toplevel.returncode != 0:
        return "(git 管理外)"
    if pathlib.Path(toplevel.stdout.strip()).resolve() != ROOT:
        return f"(git 管理外: 親リポジトリ {toplevel.stdout.strip()})"
    proc = run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], timeout=30)
    return proc.stdout.strip() if proc.returncode == 0 else "(git 管理外)"


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--matrix", default=str(EVAL / "expected_matrix.csv"))
    parser.add_argument("--models", default=str(EVAL / "models.yaml"))
    parser.add_argument("--results", default=str(EVAL / "results"))
    parser.add_argument("--run-id", default=None, help="結果の保存先を results/<実行ID>/ に分ける")
    parser.add_argument("--trials", type=int, default=10, help="1セルあたりの実行回数")
    parser.add_argument("--device", default=os.environ.get("ANDROID_SERIAL"))
    parser.add_argument("--timeout", type=int, default=1800, help="1回の Journey 実行のタイムアウト秒")
    parser.add_argument("--builds", default=None, help="対象ビルドをカンマ区切りで限定")
    parser.add_argument("--tiers", default=None, help="対象モデルティアをカンマ区切りで限定")
    parser.add_argument("--route", choices=["auto", "1", "2"], default="auto")
    parser.add_argument("--clean-build", action="store_true",
                        help="APK 作成時に clean タスクを先に流す（再実行時の推奨）")
    parser.add_argument("--dry-run", action="store_true",
                        help="Journey 実行をモックに置き換えて通しで動かす")
    args = parser.parse_args()

    run_id = args.run_id or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    results_dir = pathlib.Path(args.results) / run_id

    cells = load_matrix(pathlib.Path(args.matrix))
    if args.builds:
        wanted = {value.strip() for value in args.builds.split(",")}
        cells = [cell for cell in cells if cell.build in wanted]
    if args.tiers:
        wanted = {value.strip() for value in args.tiers.split(",")}
        cells = [cell for cell in cells if cell.model_tier in wanted]
    if not cells:
        raise SystemExit("対象のセルがありません")

    missing = [c.case_id for c in cells if not (JOURNEY_DIR / f"{c.case_id}.journey.xml").exists()]
    if missing:
        raise SystemExit(f"journey ファイルが見つかりません: {sorted(set(missing))}")

    # --- 実行経路の決定 ---------------------------------------------------
    route1 = None if args.route == "2" else detect_route1()
    if args.route == "1" and route1 is None:
        raise SystemExit(
            "Android CLI に Journey を直接実行するサブコマンドが見つかりませんでした。"
            " 経路1は使えません（--route 2 を指定してください）。"
        )
    if route1:
        print(f"[route] 経路1 のサブコマンドを検出しました（android {route1}）")
        raise SystemExit(
            "このランナーはまだ経路1に対応していません。"
            " モデルを指定できるかを含めて確認のうえ実装してください（README の「未確認事項」参照）。"
        )
    print("[route] 経路2 を使用します（エージェントのヘッドレス実行）")

    # --- 指示文とモデル設定 -----------------------------------------------
    prompt_path = EVAL / "agent_prompt.txt"
    prompt_template = prompt_path.read_text(encoding="utf-8")
    # 置換後ではなく、テンプレート自体のハッシュを記録する。
    prompt_sha = hashlib.sha256(prompt_template.encode("utf-8")).hexdigest()
    print(f"[prompt] {prompt_path.name} sha256={prompt_sha}")

    models_config = load_models_yaml(pathlib.Path(args.models))
    runner = MockRunner(models_config) if args.dry_run else Route2Runner(models_config, args.timeout)
    for tier in sorted({cell.model_tier for cell in cells}):
        print(f"[model] {tier} -> {runner.model_for(tier)}")

    # --- ビルド -----------------------------------------------------------
    builds = sorted({cell.build for cell in cells})
    unknown = [build for build in builds if build not in BUILD_PROPERTIES]
    if unknown:
        raise SystemExit(f"ビルド名と Gradle プロパティの対応がありません: {unknown}")

    apk_by_build = {}
    for build in builds:
        print(f"[build] {build} -> {' '.join(BUILD_PROPERTIES[build])}")
        apk_by_build[build] = build_apk(build, EVAL / "apks", args.dry_run, args.clean_build)

    results_dir.mkdir(parents=True, exist_ok=True)
    # APK 名とバグ ID の対応表はランナー側だけが持つ
    (results_dir / "apk_map.json").write_text(
        json.dumps({b: p.name for b, p in apk_by_build.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    env = collect_environment(args.device, runner, args.dry_run)
    env["run_id"] = run_id
    env["prompt_sha256"] = prompt_sha
    env["trials"] = args.trials
    env["journey"] = "J01"
    (results_dir / "env.json").write_text(
        json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # --- 実行 -------------------------------------------------------------
    workdir_base = EVAL / "workdir" / run_id
    if workdir_base.exists():
        shutil.rmtree(workdir_base)
    workdir_base.mkdir(parents=True)

    results = []
    total = len(cells) * args.trials
    done = 0
    started_at = datetime.datetime.now()

    for cell in cells:
        for trial in range(1, args.trials + 1):
            done += 1
            print(f"[{done}/{total}] {cell.build} / {cell.model_tier} / trial {trial}", flush=True)
            results.append(
                execute_cell_once(
                    cell=cell, trial=trial, apk=apk_by_build[cell.build], runner=runner,
                    prompt_template=prompt_template, prompt_sha=prompt_sha,
                    device=args.device, workdir_base=workdir_base,
                    results_dir=results_dir, dry_run=args.dry_run,
                )
            )
            write_results(results, results_dir)

    # --- 集計 -------------------------------------------------------------
    write_results(results, results_dir)
    rows = [result_row(result) for result in results]
    details = [dataclasses.asdict(result) for result in results]
    (results_dir / "summary.md").write_text(
        summarize.summarize(rows, details, env), encoding="utf-8"
    )

    print(f"\n完了（{datetime.datetime.now() - started_at}）: {results_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
