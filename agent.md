# KKBox Charts - Agent 指南

## 项目概述

每日自动抓取 KKBox 音乐榜单（台湾/日本/新加坡/香港），搜索 B 站可播放资源，输出暗色主题 HTML 页面。

## 部署信息

- **GitHub 仓库**: https://github.com/2Lavine/kkbox-charts
- **GitHub Pages**: https://2lavine.github.io/kkbox-charts/
- **本地路径**: `~/.qoderworkcn/skills/kkbox-charts/`

## 每日工作流

### 1. 生成数据并下载音频

```bash
python3 ~/.qoderworkcn/skills/kkbox-charts/kkbox_charts.py --download
```

输出：
- `data/YYYY-MM-DD.json` - 当日数据
- `data/latest.json` - 最新数据软链接
- `data/manifest.json` - 数据清单
- `music/*.mp3` - 下载的音频文件

### 2. 提交并推送到 GitHub

```bash
cd ~/.qoderworkcn/skills/kkbox-charts
git add data/ music/
git commit -m "chore: YYYY-MM-DD 榜单数据 + 音频更新"
git push origin main
```

### 3. 验证

- 脚本输出应显示 `20/20 found on Bilibili`（或接近）
- GitHub Actions 会自动部署到 Pages
- 访问 https://2lavine.github.io/kkbox-charts/ 确认更新

## 自动任务

已配置 GitHub Actions 每日自动抓取（见 `.github/workflows/`）。

本地如需手动触发：
```bash
# 运行抓取脚本
python3 ~/.qoderworkcn/skills/kkbox-charts/kkbox_charts.py --download

# 推送更新
cd ~/.qoderworkcn/skills/kkbox-charts && git add data/ music/ && git commit -m "chore: $(date +%Y-%m-%d) 榜单数据 + 音频更新" && git push
```

## 配置

脚本顶部可调整：
- `REGIONS`: 地区字典，可选 tw/jp/hk/sg/my
- `CHART_TYPE`: "song"(单曲榜) 或 "newrelease"(新歌榜)
- `BILI_PER_SONG`: 每首歌取几个 B 站搜索结果（默认 3）

## 注意事项

- B 站 wbi 搜索偶尔返回空结果（限流），脚本已做容错
- 封面图来自 kfs.io CDN，离线打开 HTML 时图片不显示
- 每次请求间隔 0.3s 防限流
- 音频文件较大，使用 Git LFS 或定期清理旧文件
