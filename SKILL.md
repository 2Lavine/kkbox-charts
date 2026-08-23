---
name: kkbox-charts
description: 抓取每日音乐单曲榜(台灣/日本)并搜索B站可播放资源，输出暗色主题HTML。触发词：榜单、音乐排行、今日歌曲、charts、每日歌单。
version: 1.1.0
---

# 每日音乐榜单 + B站资源

抓取日榜数据，自动搜索每首歌的B站可播放资源，输出一个自包含 HTML 文件。

## Steps

1. 运行脚本生成今日数据（JSON）：

```bash
python3 ~/.qoderworkcn/skills/kkbox-charts/kkbox_charts.py
```

2. 数据输出到 `data/YYYY-MM-DD.json` + `data/latest.json`

3. 用本地服务器打开页面（fetch 需要 HTTP 协议）：

```bash
cd ~/.qoderworkcn/skills/kkbox-charts && npx serve -l 3456 .
```

然后浏览器打开 `http://localhost:3456`

4. 或者直接把 index.html + data/latest.json 复制到 outputs 展示给用户。

## 配置

脚本顶部可调整：
- `REGIONS`: 地区字典，可选 tw/jp/hk/sg/my
- `CHART_TYPE`: "song"(单曲榜) 或 "newrelease"(新歌榜)
- `BILI_PER_SONG`: 每首歌取几个B站搜索结果（默认3）

## Pitfalls

- B站 wbi 搜索偶尔返回空结果（限流），脚本已做 try/except 容错
- 封面图来自 kfs.io CDN，离线打开 HTML 时图片不显示
- 每次请求间隔 0.3s 防限流

## Verification

- 脚本输出 `20/20 found on Bilibili`（或接近）表示正常
- 打开 HTML 确认：排名数字、蓝色B站标签可跳转
