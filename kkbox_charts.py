#!/usr/bin/env python3
"""每日音乐榜单数据抓取 + B站音频下载
用法:
  python3 kkbox_charts.py              # 只生成 JSON 数据
  python3 kkbox_charts.py --download   # 生成数据 + 下载B站音频到 music/
"""

import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

REGIONS = {
    "tw": "台灣",
    "jp": "日本",
    "sg": "新加坡",
    "hk": "香港",
}

# 榜单类型 → 中文名 / 排序权重（各地区有哪些榜就抓哪些）
TYPE_ZH = {"song": "單曲榜", "newrelease": "新歌榜", "album": "專輯榜"}
TYPE_ORDER = {"song": 0, "newrelease": 1, "album": 2}

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "data"
MUSIC_DIR = BASE_DIR / "music"
BILI_PER_SONG = 3
GENRES_FILE = BASE_DIR / "genres.json"
# 缓存里没有的歌手，按 KKBOX 分类回退一个大类曲风
CATEGORY_FALLBACK = {"華語": "華語流行", "Mandarin": "華語流行", "邦楽": "日系流行", "本地": "粵語流行"}


def load_genres() -> dict:
    """读取持久的 歌手→曲风 缓存（genres.json）。"""
    if GENRES_FILE.exists():
        try:
            return json.loads(GENRES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def fetch_chart(terr: str) -> dict:
    url = f"https://kma.kkbox.com/charts/?terr={terr}&lang=tc"
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8")
            m = re.search(r"var dailyChart\s*=\s*(\{.*?\});\s*\n", html, re.DOTALL)
            if not m:
                raise ValueError(f"[{terr}] dailyChart not found")
            return json.loads(m.group(1))
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise last_err


def extract_all_charts(chart_data: dict) -> list[dict]:
    """抽取该地区的全部榜单（單曲榜/新歌榜等），每个榜单带标题与歌曲列表。"""
    charts = []
    for key, val in chart_data.items():
        ctype = val.get("type")
        if ctype not in TYPE_ZH:
            continue
        cat = val.get("category", {}).get("name", "")
        title = f"{TYPE_ZH[ctype]}·{cat}" if cat else TYPE_ZH[ctype]
        songs = [{
            "rank": item["rankings"]["this_period"],
            "last_rank": item["rankings"].get("last_period"),
            "song_name": item.get("song_name", ""),
            "artist": item.get("artist_name", ""),
            "album": item.get("album_name", ""),
            "cover": item.get("cover_image", {}).get("normal", ""),
            "release_date": item.get("release_date"),
            "song_url": item.get("song_url", ""),
            "artist_url": item.get("artist_url", ""),
            "album_url": item.get("album_url", ""),
        } for item in val.get("data", [])]
        charts.append({"key": key, "type": ctype, "title": title, "category": cat, "songs": songs})
    charts.sort(key=lambda c: (TYPE_ORDER.get(c["type"], 9), c["key"]))
    return charts


def search_bilibili(query: str) -> list[dict]:
    url = (
        "https://api.bilibili.com/x/web-interface/wbi/search/type"
        f"?search_type=video&keyword={urllib.parse.quote(query)}"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://search.bilibili.com",
        "Origin": "https://search.bilibili.com",
    }
    # B站搜索高频请求会被临时限流（返回空结果），故空结果时退避重试
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            items = data.get("data", {}).get("result", [])[:BILI_PER_SONG]
            if items:
                return [{
                    "bvid": it.get("bvid", ""),
                    "title": re.sub(r"<[^>]+>", "", it.get("title", "")),
                    "play": it.get("play", 0),
                    "duration": it.get("duration", ""),
                    "author": it.get("author", ""),
                } for it in items]
        except Exception:
            pass
        time.sleep(2.9 * (attempt + 1))
    return []


def sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符"""
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    name = re.sub(r'\s*[-–—]\s*.*$', '', name)  # 去副标题
    return name.strip()[:80]


def download_audio(bvid: str, output_path: Path) -> bool:
    """从B站下载音频并转为 mp3"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com",
    }
    try:
        # 1. 获取 cid
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        req = urllib.request.Request(url, headers=headers)
        data = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
        if data["code"] != 0:
            return False
        cid = data["data"]["cid"]

        # 2. 获取音频流
        url2 = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&fnval=16"
        req2 = urllib.request.Request(url2, headers=headers)
        data2 = json.loads(urllib.request.urlopen(req2, timeout=10).read().decode())
        if data2["code"] != 0:
            return False
        audios = data2.get("data", {}).get("dash", {}).get("audio", [])
        if not audios:
            return False
        best = max(audios, key=lambda a: a["bandwidth"])

        # 3. 下载音频流
        tmp_path = output_path.with_suffix(".m4s")
        req3 = urllib.request.Request(best["baseUrl"], headers=headers)
        with urllib.request.urlopen(req3, timeout=60) as resp:
            tmp_path.write_bytes(resp.read())

        # 4. ffmpeg 转 mp3
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(tmp_path), "-vn",
             "-codec:a", "libmp3lame", "-q:a", "2", str(output_path)],
            capture_output=True, timeout=30,
        )
        tmp_path.unlink(missing_ok=True)
        return result.returncode == 0 and output_path.exists()
    except Exception as e:
        print(f"    download error: {e}")
        return False


def main():
    do_download = "--download" in sys.argv
    OUTPUT_DIR.mkdir(exist_ok=True)
    if do_download:
        MUSIC_DIR.mkdir(exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    output = {"date": date_str, "regions": {}}
    genres_db = load_genres()

    for terr, name in REGIONS.items():
        print(f"Fetching {name} ({terr})...")
        try:
            chart = fetch_chart(terr)
            charts = extract_all_charts(chart)
            for c in charts:
                songs = c["songs"]
                # 附加曲风标签与简介（缓存查不到则按分类回退）
                fallback = CATEGORY_FALLBACK.get(c.get("category"), c.get("category"))
                for s in songs:
                    g = genres_db.get(s["artist"])
                    if g:
                        s["genres"] = g.get("genres", [])
                        s["profile"] = g.get("profile", "")
                    else:
                        s["genres"] = [fallback] if fallback else []
                        s["profile"] = ""
                print(f"  [{c['title']}] {len(songs)} songs, searching Bilibili...")
                for s in songs:
                    query = re.sub(r"\s*[-–—].*$", "", s["song_name"])
                    query = f"{query} {s['artist'].split('(')[0].strip()}"
                    s["bili"] = search_bilibili(query)
                    time.sleep(0.6)

                    # 文件名带榜单 key 前缀，避免不同地区/榜单同排名冲突
                    fname = (f"{c['key']}-{s['rank']:02d} "
                             f"{sanitize_filename(s['song_name'])} - "
                             f"{sanitize_filename(s['artist'])}.mp3")
                    out_path = MUSIC_DIR / fname
                    if out_path.exists():
                        s["audio"] = f"music/{fname}"
                        print(f"    ✓ {fname} (exists)")
                    elif do_download and s["bili"]:
                        ok = download_audio(s["bili"][0]["bvid"], out_path)
                        if ok:
                            s["audio"] = f"music/{fname}"
                            print(f"    ✓ {fname}")
                        else:
                            print(f"    ✗ {fname}")
                        time.sleep(0.5)

                found = sum(1 for s in songs if s["bili"])
                print(f"    → {found}/{len(songs)} found on Bilibili")
                time.sleep(2)
            output["regions"][terr] = {"name": name, "charts": charts}
        except Exception as e:
            print(f"  ✗ {e}")

    # 写入数据
    out_path = OUTPUT_DIR / f"{date_str}.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_path = OUTPUT_DIR / "latest.json"
    latest_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    # 生成 manifest.json 供目录页使用
    dates = sorted(
        [p.stem for p in OUTPUT_DIR.glob("2*.json")],
        reverse=True
    )
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(dates, ensure_ascii=False), encoding="utf-8")

    print(f"\nData: {out_path}")
    if do_download:
        mp3s = list(MUSIC_DIR.glob("*.mp3"))
        print(f"Music: {MUSIC_DIR} ({len(mp3s)} files)")


if __name__ == "__main__":
    main()
