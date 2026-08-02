# 旧版

過去世代のスナップショットと初期の原稿。**参照用であり、再実行の対象外**である。
現行のパイプラインはここを読まないし、書きもしない。

| 中身 | 時期 | 内容 |
|---|---|---|
| `論文に使うCSV/` | 2026-07-26 | 基礎集計CSV 10本。`05_論文成果物/公費含む/` の部分集合で、うち4本は更に古い世代 |
| `内容まとめ/` | 2026-07-07〜22 | 主要CSVのコピー＋GE解析（後発品シェア）のまとめ |
| `Anti-allergic eye drop market.docx` / `_modified.docx` | 2026-06-30〜 | 初期の英文原稿 |
| `allergy_paper_draft.md` / `_ver2.md` | 2026-06〜07 | 初期の論文ドラフト |
| `gemini_review_verification.md` | 2026-07 | レビュー指摘の検証メモ |

---

## なぜ退避したか

`内容まとめ/` と `論文に使うCSV/` は、当時の `processed/` から手作業でコピーしたスナップショットである。
その後の再解析で `processed/` 側が更新されたため、**同名でも中身が現行と食い違っている**。

これが実害を生んだ例がある。旧 `generate_paper_csvs.py` は
`内容まとめ/prefecture_per_capita_ranking_allergy.csv` と
`内容まとめ/national_shares_allergy.csv` を論文用フォルダへコピーしていたため、
公費含まない版として実行しても `fig3_prefecture_ranking.csv` だけ公費含むデータのままになった。
詳細は [../05_論文成果物/README.md](../05_論文成果物/README.md) §4 を参照。

現在の `generate_paper_csvs.py` は一次出力先（`processed_nokouhi/`）からのみ読む。
`build_allergy_age_sex.py` も `内容まとめ/` への二重書き出しをやめている。

## GE解析のまとめについて

`内容まとめ/ge_analysis_interpretation.md` と `ge_*.csv` は、後発品（GE）シェア解析の
解釈メモと集計結果である。同名の解釈メモは `allergy解析/ge_analysis_interpretation.md`
にもあり、そちらが現行版。集計結果の現行版は
`allergy解析/03_解析結果/後発品_剤形/` にある。
