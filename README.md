<div align="center">

![Jev Browser Skill](docs/assets/hero.png)

# jev-browser-skill

让 Codex 用 Jev 操作 Chrome，完成搜索、筛选、填写和播放等网页任务。

[![License: MIT](https://img.shields.io/badge/License-MIT-lime.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/Codex-Agent%20Skill-06b6d4.svg)](skills/jev-browser/SKILL.md)
[![Checks](https://github.com/wanghai673/jev-browser-skill/actions/workflows/checks.yml/badge.svg)](https://github.com/wanghai673/jev-browser-skill/actions/workflows/checks.yml)

</div>

## 快速开始

需要 macOS、Chrome、Python 3.12+ 和 uv；API 与浏览器连接由 Skill 引导配置。

在 Codex 中输入：

```text
安装 jev-browser 这个 skill，地址是 https://github.com/wanghai673/jev-browser-skill
```

安装后，直接描述你要完成的任务：

```text
使用 $jev-browser，打开 B 站，搜索 machine learning，展示搜索结果。
```

## 使用示例

```text
打开维基百科，搜索 Monte Carlo method，打开对应条目。
打开 GitHub，搜索 browser-use，进入对应项目。
在当前页面筛选目标内容，展示筛选结果。
```

Codex 准备任务，Jev 连续操作；返回结果后停止，只有你要求继续才再次调用。

---

基于 [Jev Ultrafast](https://github.com/browser-use/jev-ultrafast) 适配。采用 [MIT License](LICENSE)，来源说明见 [NOTICE](NOTICE)。
