# CLAUDE.md

## Commands

すべて**リポジトリ直下**から実行する。本体解析のスクリプトは `data/raw` などを
カレントディレクトリ相対で参照する。

### 1. 依存ライブラリのインストール
```bash
pip install -r requirements.txt
```

### 2. 本体解析パイプラインの実行
```bash
# 10件未満の秘匿データを「0」で補完して解析（デフォルト）
python 本体解析/run_pipeline.py --imputation zero

# 10件未満の秘匿データを「5」で補完して解析
python 本体解析/run_pipeline.py --imputation five

# 10件未満の秘匿データを「1〜9の乱数」で補完して解析
python 本体解析/run_pipeline.py --imputation random
```

### 3. 共変量（実データ）の再構築
e-Stat（政府統計の総合窓口）から人口推計・医師統計・医療施設調査をダウンロードし、
`data/covariates/prefecture_covariates.csv` を再生成します。
```bash
python 本体解析/build_real_covariates.py
```

### 4. テーマ別解析
各テーマフォルダの README.md を参照（`抗アレルギー点眼解析/`, `翼状片解析/`, `眼腫瘍解析/`,
`緑内障点眼解析/`, `緑内障手術解析/`, `抗VEGF薬解析/`, `薬事工業生産動態統計/`,
`秘匿バイアス解析/`, `未掲載薬剤解析/`）。

## フォルダ構成の約束

- テーマごとにトップフォルダを1つ。内部は `01_抽出データ / 02_中間データ / 03_解析結果 / 04_図表 / 05_論文成果物` + `src/`。
- 本体解析のみ出力を `data/processed/` に置く（`.gitignore` の `data/` 除外で流出防止するため）。
- 旧版は `99_アーカイブ/` へ。削除しない。
- テーマ横断の資料・参考文献は `00_共通/`、外部統計の生データは `data/external/`。
- 各テーマの説明は README.md 1本にまとめる（claude.md は作らない）。

---

## Behavioral Guidelines (derived from Andrej Karpathy's observations)

Behavioral guidelines to reduce common LLM coding mistakes.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding
**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First
**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.
- Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes
**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

### 4. Goal-Driven Execution
**Define success criteria. Loop until verified.**

Transform vague tasks into verifiable goals:
- Vague: "Add validation." -> Verifiable: "Write tests for invalid inputs, then make them pass."
- Vague: "Fix the bug." -> Verifiable: "Write a test that reproduces the bug, then make it pass."
- Vague: "Refactor X." -> Verifiable: "Ensure tests pass before and after."

For any non-trivial task:
1. State your plan as a list of verifiable steps before executing:
   - [Step] -> verify: [check]
   - [Step] -> verify: [check]
2. Weak success criteria require constant clarification. Strong success criteria allow for independent looping.
