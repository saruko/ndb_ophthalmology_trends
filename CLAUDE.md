# CLAUDE.md

## Commands

### 1. 依存ライブラリのインストール
```bash
pip install -r requirements.txt
```

### 2. パイプラインの実行
```bash
# 10件未満の秘匿データを「0」で補完して解析（デフォルト）
python run_pipeline.py --imputation zero

# 10件未満の秘匿データを「5」で補完して解析
python run_pipeline.py --imputation five

# 10件未満の秘匿データを「1〜9の乱数」で補完して解析
python run_pipeline.py --imputation random
```

### 3. 共変量（実データ）の再構築
e-Stat（政府統計の総合窓口）から人口推計・医師統計・医療施設調査をダウンロードし、
`data/covariates/prefecture_covariates.csv` を再生成します。
```bash
python build_real_covariates.py
```

### 4. 模擬データの完全生成（検証・テスト用）
※注意: `data/raw/` 配下にある実データが上書きされます。
```bash
python generate_mock_data.py
```

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
