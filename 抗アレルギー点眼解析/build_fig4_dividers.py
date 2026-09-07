# -*- coding: utf-8 -*-
"""Figure 4A・4B（figureまとめnew.pptx スライド4）に 2021→2022年度 の縦破線を入れる。

legend（原稿§8）で「縦破線は足切りが実質解消した2022年度以降との境界」と述べているが、
図には未挿入だった（原稿 付記2）。グラフのプロット領域の実寸は PowerPoint の描画結果に
依存するため、PowerPoint COM で Chart.PlotArea.Inside* を読み、カテゴリ軸 11 区分
（2014〜2024）のうち 2021 と 2022 の境目（8/11）に破線を置く。

再実行しても二重に入らない（既存の破線は先に消す）。Windows + PowerPoint が必要。
"""
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
MASTER = os.path.join(BASE, "05_論文成果物", "公費含めない_new", "figureまとめnew.pptx")
SLIDE = 4
N_CAT = 11          # 2014〜2024
BOUNDARY = 8        # 2021 と 2022 の間（0起点で 8 区分目の右端）
NAME = "Divider_2021_2022"

PS = r"""
$ErrorActionPreference = 'Stop'
$ppt = New-Object -ComObject PowerPoint.Application
$pres = $ppt.Presentations.Open('%(master)s', $false, $false, $false)
$slide = $pres.Slides.Item(%(slide)d)
for ($i = $slide.Shapes.Count; $i -ge 1; $i--) {
  if ($slide.Shapes.Item($i).Name -like '%(name)s*') { $slide.Shapes.Item($i).Delete() }
}
$out = @()
foreach ($sh in @($slide.Shapes)) {
  if (-not $sh.HasChart) { continue }
  $ch = $sh.Chart
  $pa = $ch.PlotArea
  $x = $sh.Left + $pa.InsideLeft + $pa.InsideWidth * %(frac)s
  $y1 = $sh.Top + $pa.InsideTop
  $y2 = $y1 + $pa.InsideHeight
  $ln = $slide.Shapes.AddLine($x, $y1, $x, $y2)
  $ln.Name = '%(name)s_' + $sh.Name
  $ln.Line.DashStyle = 4        # msoLineDash
  $ln.Line.Weight = 1.5
  $ln.Line.ForeColor.RGB = 0x595959
  $out += ('{0}: x={1:F1} y={2:F1}..{3:F1}' -f $sh.Name, $x, $y1, $y2)
}
$pres.Save(); $pres.Close(); $ppt.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null
$out
"""


def main():
    script = PS % {"master": MASTER, "slide": SLIDE, "name": NAME,
                   "frac": "%d/%d" % (BOUNDARY, N_CAT)}
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, text=True)
    sys.stdout.write(r.stdout or "")
    if r.returncode != 0:
        sys.stderr.write(r.stderr or "")
        raise SystemExit("PowerShell failed")


if __name__ == "__main__":
    main()
