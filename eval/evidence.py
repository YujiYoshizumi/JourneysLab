#!/usr/bin/env python3
"""実行ごとの証跡（エビデンス）取得。

判定者（被験エージェント）とは独立に、ランナー側で次を取得する。

1. 画面録画（`adb shell screenrecord`。時間上限に達する場合は連番で録り直す）
2. 定点スクリーンショット（`adb exec-out screencap -p` を一定間隔で）
3. エージェントの標準出力・標準エラー（呼び出し側が保存する）
4. デバイス側のログ（`adb logcat -c` → `adb logcat -d`）

すべての証跡に、実行開始時刻を基準とした相対ミリ秒を付ける。
"""

from __future__ import annotations

import pathlib
import subprocess
import threading
import time

# `adb shell screenrecord --help` で確認した既定の上限（秒）。
# 本プロジェクトの検証環境（screenrecord v1.4）では既定 180 秒、`--time-limit 0` で無制限。
# 環境差を避けるため、無制限には頼らず既定値で区切って録り直す。
DEFAULT_SEGMENT_SECONDS = 180
DEFAULT_BIT_RATE = 4_000_000
REMOTE_PREFIX = "/sdcard/journeylab_rec_"


def adb_args(device: str | None) -> list[str]:
    return ["adb"] + (["-s", device] if device else [])


def probe_screenrecord_limit(device: str | None) -> str:
    """`adb shell screenrecord --help` の `--time-limit` 行をそのまま返す（記録用）。"""
    try:
        proc = subprocess.run(
            adb_args(device) + ["shell", "screenrecord", "--help"],
            capture_output=True, text=True, timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "unknown"
    text = (proc.stdout or "") + (proc.stderr or "")
    lines = [line.strip() for line in text.splitlines()]
    for index, line in enumerate(lines):
        if line.startswith("--time-limit"):
            return " ".join(lines[index:index + 3]).strip()
    return "unknown"


class ScreenRecorder:
    """画面録画を連番のセグメントで切れ目なく記録する。"""

    def __init__(
        self,
        device: str | None,
        out_dir: pathlib.Path,
        t0: float,
        segment_seconds: int = DEFAULT_SEGMENT_SECONDS,
        bit_rate: int = DEFAULT_BIT_RATE,
    ):
        self.device = device
        self.out_dir = out_dir
        self.t0 = t0
        self.segment_seconds = segment_seconds
        self.bit_rate = bit_rate
        self.segments: list[dict] = []
        self.errors: list[str] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _ms(self) -> int:
        return int((time.time() - self.t0) * 1000)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        index = 0
        while not self._stop.is_set():
            index += 1
            remote = f"{REMOTE_PREFIX}{index:04d}.mp4"
            started_ms = self._ms()
            try:
                proc = subprocess.Popen(
                    adb_args(self.device)
                    + ["shell", "screenrecord", "--bit-rate", str(self.bit_rate),
                       "--time-limit", str(self.segment_seconds), remote],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            except FileNotFoundError as exc:
                self.errors.append(f"screenrecord を起動できません: {exc}")
                return
            proc.wait()
            self.segments.append(
                {
                    "index": index,
                    "remote": remote,
                    "start_ms": started_ms,
                    "end_ms": self._ms(),
                    "file": None,
                }
            )

    def stop(self) -> None:
        """録画を止め、セグメントを取得する。失敗しても例外は投げない。"""
        self._stop.set()
        # 端末側の screenrecord に SIGINT を送ると mp4 が正しく閉じられる。
        subprocess.run(
            adb_args(self.device) + ["shell", "pkill", "-INT", "screenrecord"],
            capture_output=True, text=True,
        )
        if self._thread is not None:
            self._thread.join(timeout=60)
        time.sleep(1.5)  # ファイルの書き終わりを待つ

        for segment in self.segments:
            local = self.out_dir / f"rec_{segment['index']:04d}.mp4"
            pull = subprocess.run(
                adb_args(self.device) + ["pull", segment["remote"], str(local)],
                capture_output=True, text=True,
            )
            subprocess.run(
                adb_args(self.device) + ["shell", "rm", "-f", segment["remote"]],
                capture_output=True, text=True,
            )
            if pull.returncode == 0 and local.exists() and local.stat().st_size > 0:
                segment["file"] = local.name
                segment["size_bytes"] = local.stat().st_size
            else:
                self.errors.append(f"録画の取得に失敗: {segment['remote']} {pull.stderr.strip()[:200]}")
            segment.pop("remote", None)

    @property
    def captured(self) -> bool:
        return any(segment.get("file") for segment in self.segments)


class Screenshotter:
    """定点スクリーンショットを一定間隔で保存する。"""

    def __init__(self, device: str | None, out_dir: pathlib.Path, t0: float, interval_sec: float = 1.5):
        self.device = device
        self.out_dir = out_dir
        self.t0 = t0
        self.interval_sec = interval_sec
        self.shots: list[dict] = []
        self.errors: list[str] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        index = 0
        while not self._stop.is_set():
            index += 1
            elapsed_ms = int((time.time() - self.t0) * 1000)
            name = f"{index:04d}_{elapsed_ms:08d}ms.png"
            try:
                proc = subprocess.run(
                    adb_args(self.device) + ["exec-out", "screencap", "-p"],
                    capture_output=True, timeout=60,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                self.errors.append(f"screencap に失敗: {exc}")
                return
            if proc.returncode == 0 and proc.stdout:
                (self.out_dir / name).write_bytes(proc.stdout)
                self.shots.append({"file": f"shots/{name}", "elapsed_ms": elapsed_ms})
            else:
                self.errors.append(f"screencap に失敗: {proc.stderr[:200]!r}")
            self._stop.wait(self.interval_sec)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=30)

    @property
    def captured(self) -> bool:
        return bool(self.shots)


def clear_logcat(device: str | None) -> None:
    subprocess.run(adb_args(device) + ["logcat", "-c"], capture_output=True, text=True)


def dump_logcat(device: str | None, path: pathlib.Path) -> bool:
    proc = subprocess.run(
        adb_args(device) + ["logcat", "-d"], capture_output=True, text=True, timeout=120
    )
    if proc.returncode != 0:
        return False
    path.write_text(proc.stdout, encoding="utf-8", errors="replace")
    return True
