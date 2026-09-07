# 06_論文投稿 — 抗VEGF 硝子体内注射 論文（投稿準備）

`抗アレルギー点眼解析/05_論文成果物/公費含めない_new/` と同じ構成。数値はすべて
`../公費含まない/03_解析結果/`（全年度「公費レセプトを含まない」集計）に基づく。

| ファイル／フォルダ | 内容 |
|---|---|
| `論文下書き_抗VEGF_構成転換_2014_2024.md` | 原稿 draft v1（構造化抄録・IMRAD・限界・結論・ステートメント・図表 legend・再現性・対訳表・付記）。docx 版の査読 5 ラウンドの指摘を反映済み |
| `build_submission_files_antivegf.py` | 投稿用図表の生成スクリプト（APC の t 分布 CI、BS 削減額のキット薬価基準はここで再計算） |
| `build_pptx_figures_antivegf.py` | `投稿用/Figure*_data.csv` から Excel ネイティブグラフ入り pptx（Figure1〜6・SupplFigureS2）と、県ごとのフリーフォーム図形で描いた編集可能な地図 pptx（SupplFigureS1）を生成 |
| `投稿用/` | Figure1〜6（PNG 300 dpi + pptx + `_data.csv/xlsx`）、Table1〜5、SupplTableS1〜S9、SupplFigureS1〜S3（S1・S2 は pptx あり）、README（対応表） |

再生成:

```bash
.venv\Scripts\python.exe 抗VEGF薬解析/06_論文投稿/build_submission_files_antivegf.py
```

```bash
.venv\Scripts\python.exe 抗VEGF薬解析/06_論文投稿/build_pptx_figures_antivegf.py
```

関連: 旧原稿 `../公費含まない/抗VEGF_公費なし.docx`、解析記録・査読記録
`../公費含まない/抗VEGF薬解析結果_公費含まない.md`、legend 詳細 `../公費含まない/04_図表/figure_legends.md`、
RECORD-PE チェックリスト `../公費含まない/RECORD-PE_チェックリスト.md`。
