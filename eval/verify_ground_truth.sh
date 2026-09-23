#!/usr/bin/env bash
#
# 正解（ground truth）の裏付けを取るためのスクリプト。
#
#   - clean ビルドに対して CleanSpecTest を実行し、表示・画面遷移・購入処理を確認する
#   - B01 を注入したビルドに対して BugInjectionTest を実行し、
#     カートアイコンは無反応になり、メニューからはカートへ遷移できることを確認する
#
# 使い方:
#   ANDROID_SERIAL=emulator-5554 eval/verify_ground_truth.sh          # clean と B01
#   ANDROID_SERIAL=emulator-5554 eval/verify_ground_truth.sh B01      # 指定ビルドのみ
#
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RESULT_DIR="eval/results/ground_truth"
mkdir -p "$RESULT_DIR"

declare -a BUILDS=(clean B01)
if [ "$#" -gt 0 ]; then
  BUILDS=("$@")
fi

test_filter_for() {
  case "$1" in
    clean) echo "com.example.journeylab.CleanSpecTest" ;;
    B01)   echo "com.example.journeylab.BugInjectionTest" ;;
    *)     echo "" ;;
  esac
}

overall=0
summary=""

for build in "${BUILDS[@]}"; do
  filter="$(test_filter_for "$build")"
  if [ -z "$filter" ]; then
    echo "未知のビルド名: $build" >&2
    overall=1
    continue
  fi

  bugs=""
  [ "$build" != "clean" ] && bugs="$build"

  echo "=== $build (journeylab.bugs='$bugs') : $filter"
  ./gradlew :app:connectedDebugAndroidTest \
    -Pjourneylab.bugs="$bugs" \
    -Pandroid.testInstrumentationRunnerArguments.class="$filter" \
    > "$RESULT_DIR/$build.log" 2>&1
  status=$?

  if [ "$status" -eq 0 ]; then
    summary="${summary}${build}\tOK\n"
  else
    summary="${summary}${build}\tFAILED (see $RESULT_DIR/$build.log)\n"
    overall=1
  fi
done

echo
echo "==== ground truth 検証結果 ===="
printf "%b" "$summary"
exit "$overall"
