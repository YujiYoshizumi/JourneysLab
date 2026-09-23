# JourneyLab — Journeys 判定検証用サンプルアプリ

Android の Journeys（自然言語 E2E テスト）について、技術記事で次の3点を示すための検証環境です。

1. **Journeys がどのようなものか** — 正常なアプリに対して Journey が成功する
2. **AI による判定のため、見逃しが起こり得ること** — バグがあるのに同じ Journey が PASS してしまう
3. **モデルによって結果が変わり得ること** — 同じ Journey・同じアプリでも、モデルを変えると判定が変わり得る

1本の Journey（J01）を、**2種類のビルド × 2種類のモデル**で実行します。

| | 正常ビルド（clean） | バグ入りビルド（B01） |
|---|---|---|
| 高性能モデル（high） | ① 成功例（正解 PASS） | ② 見逃し例（正解 FAIL） |
| 低性能モデル（low） | ③（正解 PASS） | ④（正解 FAIL） |

- 検証結果をまとめた記事: **[docs/journeys-false-pass.md](docs/journeys-false-pass.md)**
- 直近の実行レポート: **[eval/reports/20260922-01.md](eval/reports/20260922-01.md)**

> **本リポジトリは実験用のサンプルです。意図的にバグを注入する仕組みが入っています。**
> 利用にあたっては [免責事項](#免責事項) を必ずお読みください。

---

## 1. 構成

```
app/
  src/main/java/com/example/journeylab/   アプリ本体（Kotlin + View + ViewBinding）
  src/androidTest/                         Journeys とは独立した Espresso テスト（ground truth）
  src/test/                                単体テスト
  src/journeysTest/J01.journey.xml         Journey（1本）
eval/
  expected_matrix.csv                      期待結果マトリクス（4セル）
  models.yaml                              モデル設定（high / low）
  agent_prompt.txt                         被験エージェントへの指示文（全実行・両モデルで固定）
  run_matrix.py                            評価ランナー
  evidence.py                              証跡（録画・スクリーンショット・logcat）の取得
  summarize.py                             集計（summary.md の生成）
  verify_ground_truth.sh                   Espresso による正解の裏付け
  reports/                                 集計済みのレポート（実行ごと）
  results/                                 実行結果と証跡 ※git では追跡しない
docs/
  journeys-false-pass.md                   検証結果をまとめた記事
```

技術スタック（このリポジトリで実際にビルド・実行したときの値）:

| 項目 | 値 |
|---|---|
| 言語 | Kotlin（AGP 9 内蔵の Kotlin サポート。`org.jetbrains.kotlin.android` は適用しない） |
| UI | Android View システム（XML）＋ ViewBinding ＋ Material 3 |
| Jetpack Compose | 依存に含めない（`androidx.activity` が推移的に引く `androidx.compose.runtime:runtime-annotation` も `configurations.configureEach { exclude(...) }` で除外） |
| 画面遷移 | 単一 Activity ＋ Fragment（`FragmentManager`） |
| リスト | RecyclerView（`ListAdapter` ＋ `DiffUtil`） |
| 状態保持 | Activity スコープの `ViewModel`（カートの内容） |
| Android Gradle Plugin | 9.4.1 |
| Gradle | 9.6.0 |
| compileSdk / targetSdk / minSdk | 37 / 37 / 29 |
| 構成キャッシュ | `org.gradle.configuration-cache=false`（Journeys の既知の問題への対応） |

`findViewById` と Kotlin synthetics はアプリ側のコードで一切使っていません
（`grep -rn findViewById app/src/main` は0件）。

---

## 2. ビルドとバグ注入

### 必要なもの

| 用途 | 必要なもの |
|---|---|
| アプリのビルド | JDK 17、Android SDK（`compileSdk 37` のプラットフォーム） |
| 端末操作 | `adb`（Android SDK Platform-Tools）。エミュレータまたは実機 |
| Journey の実行 | [Android CLI](https://developer.android.com/tools/agents/android-cli)。`android init` を実行して Journeys スキルを導入しておく |
| 被験エージェント | `eval/models.yaml` の `agent` に指定したもの（既定は Claude Code。`claude` コマンドが使え、認証済みであること） |
| 評価ランナー | Python 3.9 以上（3.9.6 で動作確認。PyYAML は任意） |

Android SDK の場所は、次のどちらかで Gradle に伝えます。

```bash
# いずれか
echo "sdk.dir=$HOME/Library/Android/sdk" > local.properties   # local.properties は git 管理外
export ANDROID_HOME="$HOME/Library/Android/sdk"
```

アプリのビルドと Espresso テストだけなら Android CLI と被験エージェントは不要です。

### ビルド

```bash
# clean ビルド（仕様どおりに動く）
./gradlew :app:assembleDebug

# B01 を注入
./gradlew :app:assembleDebug -Pjourneylab.bugs=B01
```

### ビルド名と Gradle プロパティの対応

| ビルド名 | Gradle プロパティ |
|---|---|
| `clean` | `-Pjourneylab.bugs=` |
| `B01` | `-Pjourneylab.bugs=B01` |

同じ対応が `eval/run_matrix.py` の `BUILD_PROPERTIES` にも入っています。

### 注入するバグ

| ID | 仕様からの逸脱 |
|---|---|
| B01 | トップバーのカートアイコンをタップしても何も起きない（ホーム画面・商品詳細画面の両方）。メニューの「カート」からは従来どおりカート画面に遷移できる |

エージェントが目標（カートを開く）を達成するために別の経路（メニュー）を自ら選び、
バグに気づかず PASS してしまう現象を再現するためのものです。

### 汚染防止

- バグ ID・注入の有無は、画面・`contentDescription`・Logcat・アプリ名・バージョン名のどこにも出しません。
  アプリはログ出力を一切行わず、`applicationId`（`com.example.journeylab`）・アプリ名（`JourneyLab`）・
  `versionName`（`1.0`）は全ビルドで同一です。「このアプリについて」ダイアログにも
  バージョン名やビルド情報は表示しません（Espresso で確認しています）。
- 評価ランナーは APK を `eval/apks/<ランダムな12桁>.apk` にコピーし、ビルド名との対応表
  （`<結果ディレクトリ>/apk_map.json`）はランナー側だけが持ちます。
- エージェントには、APK と Journey ファイルだけを置いた作業ディレクトリ
  （`eval/workdir/<実行ID>/<ビルド>_<ティア>_<試行>/`）を渡します。ソースコードは含まれません。
- エージェントに許可するツールは `eval/models.yaml` の `command` でデバイス操作中心に絞っています
  （`Bash(adb:*) Bash(android:*) Read Write Glob`）。

---

## 3. 正解（ground truth）の確認

Journeys とは独立した Espresso テストで、clean ビルドの仕様と B01 の逸脱を検証します。

```bash
ANDROID_SERIAL=emulator-5554 ./eval/verify_ground_truth.sh        # clean と B01
ANDROID_SERIAL=emulator-5554 ./eval/verify_ground_truth.sh B01    # 指定ビルドのみ
```

ビルドごとに、そのビルドに対応するテストクラスだけを
`-Pandroid.testInstrumentationRunnerArguments.class=...` で選んで実行します。
ログは `eval/results/ground_truth/<ビルド>.log` に残ります。

- `CleanSpecTest`（11件）… 商品4件がスクロールなしで表示される／ホームと商品詳細の両方で
  カートアイコンからカートが開く／メニュー経由でもカートが開く／「このアプリについて」に
  ビルド情報が出ない／カート追加・小計・合計／空カートで「注文する」が無効／注文完了と
  カートの空化／注文番号の連番／カート画面と注文完了画面ではトップバーのメニューを出さない
- `BugInjectionTest`（3件）… B01 でホームのカートアイコンが無反応／商品詳細のカートアイコンも
  無反応／メニューの「カート」からは遷移できる

実測（Pixel 10 / Android 17 / API 37 のエミュレータ）: clean・B01 とも OK。
単体テスト（`./gradlew :app:testDebugUnitTest`）も通ります。

---

## 4. Journey ファイル

`app/src/journeysTest/J01.journey.xml`（1本）に、商品購入のテスト手順を定義しています。
特にステップ3は、見逃しを再現するために**意図的に経路を指定しない書き方**にしてあります。

```xml
<journey name="J01">
  <description>商品を購入する</description>
  <actions>
    <action>「トートバッグ」をタップする</action>
    <action>「カートに追加」をタップする</action>
    <action>カートを開く</action>
    <action>カートに「トートバッグ」が1点あり、合計が「¥2,200」であることを確認する</action>
    <action>「注文する」をタップする</action>
    <action>「ご注文ありがとうございました」と表示されていることを確認する</action>
  </actions>
</journey>
```

形式は Android CLI の Journeys スキル（`android init` で導入される `references/journeys.md`）に
記載されたものに合わせています。

- アプリ起動は Journey 実行時に行われるため、「アプリを起動する」ステップは書いていません。
- 本文は日本語です（アプリの UI が日本語のため）。対応言語の明示的な一覧は公式ドキュメントに
  見つけられませんでした（→「8. 未確認事項」）。

**検証意図**：この Journey の書き手は、ステップ3で「カートアイコンからカートに遷移できること」も
確認できるつもりでいる、という想定です。したがって B01 ビルドでの正解は FAIL です。

---

## 5. モデル設定（`eval/models.yaml`）

被験エージェントは1種類（Claude Code）に固定し、モデルだけを切り替えます。

```yaml
agent: claude-code
tiers:
  high:
    model: claude-opus-5
  low:
    model: claude-haiku-4-5-20251001
```

### モデル ID と区分の根拠

出典: Anthropic 公式のモデル一覧
<https://platform.claude.com/docs/en/about-claude/models/overview>

| ティア | モデル | Claude API ID | 同ページの記載 |
|---|---|---|---|
| high | Claude Opus 5 | `claude-opus-5` | 「For complex agentic coding and enterprise work」。`$5 / input MTok, $25 / output MTok`、"If you're unsure which model to use, start with Claude Opus 5 for most workloads" |
| low | Claude Haiku 4.5 | `claude-haiku-4-5-20251001` | 「The fastest model with near-frontier intelligence」。`$1 / input MTok, $5 / output MTok`、Comparative latency は "Fastest" |

- 区分は**提供元のモデル区分**（上位モデル／軽量モデル）に基づきます。同ページの Description・
  Pricing・Comparative latency の記載をそのまま根拠としており、こちらで性能を断定していません。
- **画像入力**: 同ページに「All current models support text and image input, text output,
  multilingual capabilities, vision, and tool use.」と明記されており、両モデルとも対応しています。
- **モデルの切り替え方法**: Claude Code の `--model` オプション（`claude --help` で確認）。
- **実際に使われたモデル ID**: `claude -p --output-format json` の戻り値に含まれる `modelUsage`
  のキーを記録しています（`results.csv` の `model_actual` 列）。指定と実際が食い違ったときに
  気づけるようにするためです。

---

## 6. 評価の実行

```bash
# 実行部分をモックに置き換えた通し確認（デバイス不要）
python3 eval/run_matrix.py --dry-run

# 実機/エミュレータでの実行（4セル × 10回）
python3 eval/run_matrix.py --device emulator-5554 --trials 10 --run-id 20260921-01 --clean-build

# 一部だけ
python3 eval/run_matrix.py --device emulator-5554 --builds B01 --tiers high --trials 3
```

出力は `eval/results/<実行ID>/` に入ります。

| ファイル | 内容 |
|---|---|
| `results.csv` / `results.json` | セル・試行番号・判定・ステップごとの判定と理由・証跡のパス・開始時刻と所要時間・エージェント名とバージョン・指定モデル ID と実モデル ID・指示文のハッシュ |
| `summary.md` | 集計結果 |
| `env.json` | 実行環境（エージェント／Android CLI／デバイス／AGP／`screenrecord` の上限値 など） |
| `apk_map.json` | ビルド名と APK ファイル名の対応（ランナー側の情報） |
| `<ビルド>/<ティア>/<試行>/` | 証跡一式（下記） |

集計だけをやり直す場合:

```bash
python3 eval/summarize.py --results eval/results/20260921-01
```

### 証跡（エビデンス）

判定者（エージェント）とは独立に、ランナー側で毎回取得します。保存先は
`eval/results/<実行ID>/<ビルド>/<ティア>/<試行>/` です。

| ファイル | 内容 |
|---|---|
| `rec_0001.mp4`, `rec_0002.mp4`, … | 画面録画。`adb shell screenrecord --bit-rate 4000000` を180秒ごとに録り直して連番で保存 |
| `shots/NNNN_XXXXXXXXms.png` | 定点スクリーンショット。1.5秒間隔。ファイル名に実行開始からの経過ミリ秒を含む |
| `agent_stdout.log` | エージェントの標準出力・標準エラーの全文 |
| `logcat.txt` | 実行開始時に `adb logcat -c`、終了後に `adb logcat -d` |
| `verdict.json` | エージェントの出力から取り出した判定を構造化したもの |
| `timeline.json` | 実行開始時刻、録画セグメントの相対時刻、スクリーンショットの相対時刻、ステップごとの画面ファイルの相対時刻 |

`screenrecord` の上限値は実行時に `adb shell screenrecord --help` で確認し、`env.json` の
`screenrecord_time_limit` に記録します。本プロジェクトの検証環境（screenrecord v1.4）では
**既定 180 秒、`--time-limit 0` で無制限**でした。無制限には頼らず、既定値で区切って
連番で録り直しています（環境差を避けるため）。録画に失敗しても実行は継続し、
「録画なし」として `summary.md` の「証跡の欠損」に計上します。

### 集計指標（`summary.md`）

- セルごとの判定内訳（PASS / FAIL / ERROR の件数）
- 見逃し率（B01 ビルドで PASS）・誤検知率（clean ビルドで FAIL）を**モデルごとに**
- 判定の一貫性（同一セルの N 回のうち多数派と一致した割合）
- モデル間の差（同じビルドでの判定内訳の差）
- FAIL になったステップの分布
- **ステップ3の経路の記録欄** — 録画を見て人手で記入するための表。ランナーは、ステップ3の
  開始・終了時刻（相対ミリ秒）と、該当する録画ファイル・スクリーンショットの範囲を出力します
- 証跡の欠損（録画・スクリーンショット・logcat が取れなかった実行の数）

ステップ3の開始・終了時刻は、**エージェントが当該ステップで保存した画面ファイルの更新時刻**から
求めています（指示文 `artifacts` の内容）。指示文に判定基準を足さずに時刻を得るための方法です。
画面ファイルが無い実行では空欄になります。経路そのもの（カートアイコン／メニュー）は、
エージェントの自己申告ではなく**録画を見て人が判断する**前提です。

### 採用した実行経路

**経路2（被験エージェントのヘッドレス実行）**です。

`android help` の出力に Journey を指定して実行するサブコマンドは存在せず
（`create` / `run` / `layout` / `screen` / `docs` / `emulator` / `skills` など）、公式ドキュメント
「Android CLI support for Journeys」も、エージェントが Journeys スキルを使って実行する、という
位置づけを示すのみでした。したがって「判定モデルを指定できる経路1」は存在しません。
ランナーは起動時に `android help` を調べ（`detect_route1()`）、将来そのようなサブコマンドが
現れた場合は検出して知らせます（経路1の実装は入っていません）。

Android Studio の Journeys Gradle タスクは、判定役が Gemini に固定されるため使いません。

### 被験エージェントへの指示文

`eval/agent_prompt.txt` の1ファイルに集約し、**両モデル・すべての実行で同一**のものを使います。
判定の基準や注意点は書いていません（書いた時点で、測っているものが「Journeys の判定」ではなく
「その指示文の効果」に変わるため）。`{JOURNEY_FILE}` と `{PACKAGE_NAME}` はランナーが置換します。

記録するハッシュは**置換後の文字列ではなくテンプレート自体**の SHA-256 です
（`results.csv` の `prompt_sha256` 列、`env.json`）。

現在のハッシュ: `3e708d200b971d3de429bc25db4829fc4da5a5315f3ec35f418a6cbe73113198`

エージェントの出力から所定の JSON を取り出せなかった場合は、PASS/FAIL ではなく `ERROR` として
記録し、集計では PASS/FAIL と分けて数えます。Journey 全体の判定は、Journeys スキルの定義
（全ステップが成功したときだけ成功）に従って、ステップごとの `status` から導出します。

各実行の前にアプリのデータを初期化します（`adb shell pm clear com.example.journeylab`）。
アプリの起動はランナーが `am start` で行うため、Journey 側に起動ステップは不要です。

### 実行済みの結果

実行結果は `eval/results/<実行ID>/` に保存されます。**録画やスクリーンショットを含めて数百 MB に
なるため、git では追跡していません**（`.gitignore`）。集計済みのレポートだけを `eval/reports/` に
置いています。

**ドライラン**（`--dry-run --trials 10`）: 4セル × 10回 = 40実行が最後まで動き、`summary.md` の
全セクション（判定内訳／見逃し率・誤検知率／モデル間の差／FAIL ステップの分布／ステップ3の
経路の記録欄／証跡の欠損／ERROR の内訳）が埋まることを確認しています。

**実機での実行**（実行ID `20260922-01`、Pixel 10 / Android 17 / API 37 エミュレータ、
4セル × 10回 = 40実行、1時間24分40秒）:

| ビルド | モデル | 正解 | PASS | FAIL | ERROR | 一貫性 |
|---|---|---|---|---|---|---|
| clean | high | PASS | 10 | 0 | 0 | 100% |
| clean | low | PASS | 7 | 1 | 2 | 70% |
| B01 | high | FAIL | 7 | 3 | 0 | 70% |
| B01 | low | FAIL | 0 | 4 | 6 | 60% |

- 見逃し率: high 70.0% (7/10) / low 0.0% (0/4)
- 誤検知率: high 0.0% (0/10) / low 12.5% (1/8)
- ERROR 率: high 0.0% (0/20) / low 40.0% (8/20)
- 証跡（録画・スクリーンショット・エージェント出力・logcat）の欠損: **0 件 / 40 件**

指定したモデル ID と実際に使われたモデル ID は全40実行で一致していました。
判定理由の引用を含む詳細は **[`eval/reports/20260922-01.md`](eval/reports/20260922-01.md)** にあります。

#### 既知の問題（証跡の取得）

`eval/evidence.py` の録画ループには再試行の間隔とリトライ上限がありません。1本のセグメントが
180秒の上限で終了した直後に `screenrecord` の再起動が連続して失敗することがあり、上記の実行では
40件中1件で **約11.4秒の録画の空白**が生じました（180秒を超えた実行6件のうち1件）。
`timeline.json` にはファイルが生成されなかったセグメントの記録が残ります。

---

## 7. 再実行

過去の実行と比較できる形で測り直すための手順です。

```bash
python3 eval/run_matrix.py --device <serial> --trials 10 --run-id <YYYYMMDD-NN> --clean-build
```

**実行前に確認すること**

1. `eval/agent_prompt.txt` の SHA-256 が前回の実行結果（`env.json` の `prompt_sha256`）と
   一致すること。一致しなければ、前回とは別の実験として扱う
2. `eval/models.yaml` のモデル ID が、前回の「実際に使われたモデル ID」
   （`results.csv` の `model_actual` 列）と一致すること

**変更してはいけないもの**

`app/` 配下、`app/src/journeysTest/J01.journey.xml`、`eval/agent_prompt.txt`、
`eval/expected_matrix.csv`、`eval/models.yaml`。いずれかを変えた場合、その実行は
過去の結果と比較できません。

**そのほかの注意**

- `--run-id` を実行ごとに分ける（結果が `eval/results/<実行ID>/` に隔離される）
- `--clean-build` を付けてビルドキャッシュの影響を避ける
- **実際に使われたモデル ID は、こちらが何もしなくても更新されることがあります。**
  結果が前回と食い違ったときは、まず `model_actual` 列を疑ってください
- 次の項目が前回と同じかどうかも記録する: 被験エージェントのバージョン／Android CLI の
  バージョン／デバイスの機種・API レベル・画面サイズ・言語設定
- ステップ3でどの経路が使われたかは、エージェントの自己申告ではなく**録画を見て人が判断する**
  （`summary.md` に記入欄があります）

### `eval/agent_prompt.txt` の変更履歴

| 日付 | SHA-256 | 変更内容 |
|---|---|---|
| 初版 | `3e708d200b971d3de429bc25db4829fc4da5a5315f3ec35f418a6cbe73113198` | 初版 |

---

## 8. 未確認事項・設計上の判断

### 公式の情報源で確認できたこと

| 事項 | 情報源 |
|---|---|
| Journey XML の形式（`<journey name>` / `<description>` / `<actions>` / `<action>`）と、全ステップ成功時のみ成功という判定規則 | Android CLI の Journeys スキル `references/journeys.md` |
| 「アプリを起動する」ステップは不要 | developer.android.com/studio/gemini/journeys |
| AGP 9.0.0 以上が必要 | 同上 |
| 構成キャッシュ有効時の既知の問題（別の Journey が実行される・認証エラー） | 同上（Known issues） |
| 実行時にアプリの全権限が自動付与される | 同上（Known issues） |
| Android CLI に Journey 実行専用のサブコマンドが無いこと | `android help` の出力 |
| モデル ID・画像入力対応・モデルの区分 | <https://platform.claude.com/docs/en/about-claude/models/overview> |
| モデルの切り替え方法（`--model`）、ヘッドレス実行（`-p`）、実モデル ID の取得（`--output-format json` の `modelUsage`） | `claude --help` と、その戻り値の実測 |
| `screenrecord` の時間上限（既定 180 秒、`--time-limit 0` で無制限） | 実行環境の `adb shell screenrecord --help` |

### 確認できず、仮置きした事項

1. **Gradle の `testSuites` 設定**
   Journey ファイルは仕様どおり `app/src/journeysTest/` に置いていますが、Android Studio の
   「New > Journey Test」テンプレートが生成する `testSuites { create("journeysTest") { … } }`
   ブロックは**追加していません**。公式ドキュメントに載っているのは `targetVariants` の追記例だけで、
   ブロック全体の正確な DSL を公式の情報源だけでは確認できなかったためです。
   本評価は経路2で動くため、この設定が無くても実行できます。Android Studio から Journey を
   実行したい場合は、Studio の「New > Journey Test」で1本作らせ、生成された設定を取り込んでください。
2. **Journey の対応言語**
   公式ドキュメントは "supported languages" と書くのみで、言語の一覧を見つけられませんでした。
   日本語で書いていますが、これは未確認の前提です。
3. **経路1（Android CLI の直接実行）での判定モデルの指定方法と結果の出力形式**
   サブコマンド自体が存在しないため、確認できていません。
4. **ステップ境界の自動判定**
   指示文に判定基準を足せないため、ステップの開始・終了時刻は `artifacts` のファイル更新時刻から
   推定しています。エージェントが画面ファイルを保存しなかった場合、ステップ3の時刻欄は空欄になります。
   その場合は録画全体とスクリーンショット列を人手で確認してください。

### 設計上の判断

| 箇所 | 実装 | 理由 |
|---|---|---|
| カート画面・注文完了画面のトップバー | カートアイコンとオーバーフローメニューを出さない | カートへの移動とアプリ情報の表示は、ホーム画面・商品詳細画面のメニューにまとめるため |
| 戻るボタン | 商品詳細に加えて、カート画面・注文完了画面でも表示 | 単一 Activity のバックスタックに従って前の画面へ戻れるようにするため |
| スナックバーの表示時間 | `LENGTH_LONG`（約2.75秒） | 既定の `LENGTH_SHORT` はエージェントが観測する前に消える可能性が高いため |
| テーマ | 端末のダークテーマ設定に追従せずライト固定 | 実行ごとの見た目のばらつきを排するため |
| Espresso 実行時 | `testOptions { animationsDisabled = true }` | アニメーション有効時に Espresso が不安定になるため。Journeys 実行時の端末設定は変更しません |
| `eval/models.yaml` | `agent` / `tiers` / `command` を持つ | 被験エージェント・モデル・起動コマンドを設定ファイル側で指定できるようにするため |

---

## 9. アプリの仕様（正しい挙動）

| ID | 商品名 | 価格 |
|---|---|---|
| P1 | ブルーマグカップ | ¥1,280 |
| P2 | ノートブック A5 | ¥880 |
| P3 | トートバッグ | ¥2,200 |
| P4 | デスクライト | ¥4,980 |

4件はスクロールなしで1画面に収まります。

**共通のトップバー（ホーム画面・商品詳細画面）**
- 右上にカートアイコン（タップでカート画面へ）
- オーバーフローメニュー：「カート」（カートアイコンとは別の経路）／「このアプリについて」
  （ダイアログ「JourneyLab サンプルアプリ」。バージョン名やビルド情報は表示しない）
- 商品詳細画面では戻るボタンを表示

**画面（全4画面）**
- **ホーム**: 見出し「本日のおすすめ」、商品カード（商品名・価格）の縦リスト。タップで商品詳細へ。
  起動時、商品一覧は即座に表示される
- **商品詳細**: 商品名、価格、「カートに追加」。タップでスナックバー「カートに追加しました」を表示し、
  カートに数量1を加算
- **カート**: 行ごとに商品名・数量・小計。「合計 ¥x,xxx」。「注文する」はカートが空のとき無効
  （`isEnabled = false`。Material の標準の無効スタイル、独自色なし）
- **注文完了**: 「ご注文ありがとうございました」、注文番号（`ORDER-0001` から連番）、「ホームに戻る」。
  注文確定時にカートは空になる

---

## 免責事項

本リポジトリは、Android の Journeys の判定挙動を観測するために作成した**個人的な実験用のサンプル**です。
以下をご理解のうえ、**すべて自己責任**でご利用ください。

- **本リポジトリの利用によって生じたいかなる損害・不利益についても、作者は一切の責任を負いません。**
  業務・商用・その他の目的を問わず、また損害の発生を事前に知らされていた場合でも同様です。
- 本リポジトリは**現状有姿（AS IS）**で提供され、明示・黙示を問わず、商品性、特定目的への適合性、
  正確性、完全性を含むいかなる保証も行いません。
- **アプリには意図的に不具合を注入する仕組みが含まれています**（`-Pjourneylab.bugs=B01`）。
  検証用の構造であり、製品コードへの流用は想定していません。そのまま転用しないでください。
- 掲載している数値・引用は、README 記載の環境・時点における**実測値の記録**です。
  Journeys はプレビュー段階の機能であり、エージェントやモデル、Android CLI、端末の違いによって
  結果は変わります。再現性および将来にわたる妥当性を保証するものではありません。
- 本リポジトリの内容は作者個人によるものであり、作者の所属組織の見解を代表するものではありません。
  また、Google、Anthropic その他の企業および製品と公式な関係はありません。
- 本リポジトリの内容は、法的・技術的な助言を構成するものではありません。
