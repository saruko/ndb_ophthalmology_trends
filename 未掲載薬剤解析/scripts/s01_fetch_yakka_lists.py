# -*- coding: utf-8 -*-
"""s01: 薬価基準収載品目リスト（年度別スナップショット）の取得

厚労省の「薬価基準収載品目リスト及び後発医薬品に関する情報について」は
薬価改定期ごとにページが分かれ、各ページは期末時点の最新版のみをリンクする。
ただし旧版ファイルはリンクが外れてもサーバ上に残存しているため、
ページ本文に現れる更新日付を手掛かりに直接URLを叩いて年度別版を復元する。

各年度について2時点を取得する:
  start = 年度開始(4/1)時点で適用中の版
  end   = 年度内で最も新しい版
年度中に収載された品目と年度中に削除された品目の双方を分母に含めるため、
後段(s02)で両者の和集合を「その年度に薬価基準にあった品目」とする。

ファイル番号: _01=内用薬 _02=注射薬 _03=外用薬 _04=歯科用薬剤
（2014〜2016年頃は _1.._4 / 拡張子 .xls の命名）

出力: data/yakka/<日付>/yakka_<日付>_<剤形>.xls(x) と manifest.json
"""
import os
import re
import json
import time
import urllib.request
import urllib.error

from paths import YAKKA_RAW

BASE = "https://www.mhlw.go.jp"
SEED = "/topics/2014/03/tp0305-01.html"
UA = {"User-Agent": "Mozilla/5.0 (academic research; NDB coverage study)"}

KINDS = {1: "naiyo", 2: "chusha", 3: "gaiyo", 4: "shika"}
FISCAL_YEARS = list(range(2014, 2025))
SLEEP = 0.4


def _get(url, timeout=120):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _get_text(url):
    raw = _get(url)
    for enc in ("cp932", "utf-8", "euc-jp"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _head(url, timeout=30):
    req = urllib.request.Request(url, headers=UA, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, int(r.headers.get("Content-Length") or 0)
    except urllib.error.HTTPError as e:
        return e.code, 0
    except Exception:
        return -1, 0


def crawl_pages():
    """期間ページの連鎖を辿り、(更新日付 -> 出現ディレクトリ集合) を集める。"""
    page, seen, dates = SEED, set(), {}
    pages = []
    while page and page not in seen:
        seen.add(page)
        html = _get_text(BASE + page)
        pages.append(page)
        page_dir = page.rsplit("/", 1)[0] + "/xls/"
        for href in re.findall(r'href="([^"]*?tp\d{8}-\d+_\d+\.xlsx?)"', html, re.I):
            d = re.search(r"tp(\d{8})-\d+_\d+\.xlsx?$", href, re.I).group(1)
            hdir = href.rsplit("/", 1)[0] + "/" if "/" in href else page_dir
            if not hdir.startswith("/"):
                hdir = page_dir
            dates.setdefault(d, set()).update({hdir, page_dir})
        nxt = [n for n in re.findall(r'href="(/topics/\d{4}/\d{2}/tp\d+-01\.html)"', html)
               if n not in seen]
        page = nxt[0] if nxt else None
        time.sleep(SLEEP)
    return pages, dates


def _candidate_dirs(date, known_dirs):
    cands = list(known_dirs) + ["/topics/%s/%s/xls/" % (date[:4], date[4:6])]
    out = []
    for c in cands:
        if c not in out:
            out.append(c)
    return out


def resolve_date(date, known_dirs):
    """その日付版の _01.._04 が実在するURLを解決する。無ければ None。"""
    for d in _candidate_dirs(date, known_dirs):
        for num_fmt, ext in [("%02d", "xlsx"), ("%02d", "xls"), ("%d", "xls"), ("%d", "xlsx")]:
            url = "%s%stp%s-01_%s.%s" % (BASE, d, date, num_fmt % 1, ext)
            code, size = _head(url)
            time.sleep(SLEEP)
            if code == 200 and size > 50000:
                files = {}
                for k in KINDS:
                    u = "%s%stp%s-01_%s.%s" % (BASE, d, date, num_fmt % k, ext)
                    c2, s2 = _head(u)
                    time.sleep(SLEEP)
                    if c2 == 200 and s2 > 10000:
                        files[k] = {"url": u, "bytes": s2}
                return {"date": date, "dir": d, "ext": ext, "files": files}
    return None


def _resolve_first(candidates, dates, cache):
    """候補日付を新しい順に試し、最初に解決できたものを返す。"""
    for d in candidates:
        if d in cache:
            if cache[d] is not None:
                return cache[d]
            continue
        r = resolve_date(d, dates.get(d, set()))
        cache[d] = r if (r and len(r["files"]) >= 3) else None
        if cache[d]:
            return cache[d]
    return None


def fetch(refresh=False):
    os.makedirs(YAKKA_RAW, exist_ok=True)
    manifest_path = os.path.join(YAKKA_RAW, "manifest.json")
    if os.path.exists(manifest_path) and not refresh:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        if manifest.get("version") == 2:
            print("[s01] manifest.json をキャッシュから使用（--refresh で再取得）")
            _download(manifest)
            return manifest

    print("[s01] 期間ページを巡回中...")
    pages, dates = crawl_pages()
    ds = sorted(dates)
    print("  期間ページ %d 件 / 更新日付 %d 件" % (len(pages), len(ds)))

    cache, years = {}, {}
    for fy in FISCAL_YEARS:
        start_c = list(reversed([d for d in ds if d <= "%d0401" % fy]))[:4]
        end_c = list(reversed([d for d in ds if d <= "%d0331" % (fy + 1)]))[:4]
        print("  FY%d start..." % fy, end="", flush=True)
        s = _resolve_first(start_c, dates, cache)
        print(" %s / end..." % (s["date"] if s else "×"), end="", flush=True)
        e = _resolve_first(end_c, dates, cache)
        print(" %s" % (e["date"] if e else "×"))
        years[str(fy)] = {"start": s, "end": e}

    snapshots = {}
    for v in years.values():
        for r in v.values():
            if r:
                snapshots[r["date"]] = r

    manifest = {"version": 2, "pages": pages, "years": years, "snapshots": snapshots}
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    _download(manifest)
    return manifest


def _download(manifest):
    print("[s01] ダウンロード...")
    n_new = 0
    for date, r in sorted(manifest["snapshots"].items()):
        outdir = os.path.join(YAKKA_RAW, date)
        os.makedirs(outdir, exist_ok=True)
        for k, info in sorted(r["files"].items(), key=lambda kv: int(kv[0])):
            kind = KINDS[int(k)]
            ext = info["url"].rsplit(".", 1)[-1]
            fp = os.path.join(outdir, "yakka_%s_%s.%s" % (date, kind, ext))
            if os.path.exists(fp) and os.path.getsize(fp) > 10000:
                continue
            try:
                b = _get(info["url"])
            except Exception as ex:
                print("   ERR %s %s" % (info["url"], ex))
                continue
            with open(fp, "wb") as f:
                f.write(b)
            n_new += 1
            print("   %s %-7s %.1fMB" % (date, kind, len(b) / 1e6))
            time.sleep(SLEEP)
    print("[s01] 完了: %s (新規 %d ファイル)" % (YAKKA_RAW, n_new))


if __name__ == "__main__":
    import sys
    fetch(refresh="--refresh" in sys.argv)
