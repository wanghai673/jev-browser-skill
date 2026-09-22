<div align="center">

![Jev Browser：快速、低成本，让 Codex 高效操作浏览器](docs/assets/hero.png)

# ⚡ Jev Browser Skill

### 让 Codex 操作浏览器，更快，也更省。

**低延迟决策 · 低成本 API · 复用你的 Chrome**

搜索、筛选、填写、打开网页。说出目标，把连续操作交给 Jev。

[![License: MIT](https://img.shields.io/badge/License-MIT-lime.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/Codex-Agent%20Skill-06b6d4.svg)](skills/jev-browser/SKILL.md)
[![Checks](https://github.com/wanghai673/jev-browser-skill/actions/workflows/checks.yml/badge.svg)](https://github.com/wanghai673/jev-browser-skill/actions/workflows/checks.yml)

[观看演示](#演示) · [快速开始](#快速开始) · [为什么快又省](#为什么快又省) · [查看 Skill](skills/jev-browser/SKILL.md)

</div>

## 演示

**7.1 秒，完成一次航班搜索。** 从苏黎世到伦敦，一句话启动 Google Flights 搜索，自动填写并展示航班结果。

<a href="https://github.com/browser-use/jev-ultrafast/blob/1231850a0bf1a0c0341fe408ef1668dbbfdfac46/docs/demo.mp4"><img src="https://raw.githubusercontent.com/browser-use/jev-ultrafast/1231850a0bf1a0c0341fe408ef1668dbbfdfac46/docs/demo.gif" alt="Jev Ultrafast 在 Google Flights 搜索苏黎世到伦敦航班的实时演示" width="100%" /></a>

[▶ 观看完整视频](https://github.com/browser-use/jev-ultrafast/blob/1231850a0bf1a0c0341fe408ef1668dbbfdfac46/docs/demo.mp4) · [上游演示与计时说明](https://github.com/browser-use/jev-ultrafast/blob/1231850a0bf1a0c0341fe408ef1668dbbfdfac46/docs/performance.md)

<sub>演示来自 Browser Use 的 Jev Ultrafast，按 1× 速度播放。7.1 秒包含模型决策、文本生成与页面加载，不含初始页面准备。</sub>

## 为什么快又省

| 设计 | 带来的变化 |
| :--- | :--- |
| ✍️ **提前备好文字，选中就填** | Codex 预先提供搜索词等内容，输入阶段直接填入，省去额外的文字生成调用。 |
| 📄 **直接读取页面文字和控件** | 默认从 DOM 获取页面信息，省去逐步截图与图像理解的开销。 |
| 🔄 **一次交代，连续执行** | Jev 自行完成点击、滚动和切页；Codex 在结果返回后回复，减少模型之间的反复交接。 |
| ⚡ **延迟低，成本省** | 模型请求延迟 **70–500 ms**；输入 **$0.042 / 百万 token**，**输出免费**。 |

<sub>延迟与价格来自 [TypeSafe 官方](https://typesafe.ai/blog/introducing-system-one-models-and-jev)，核对于 2026-09-22。以上为模型请求指标；完整任务还包括 Codex、网页加载和重试的开销。</sub>

## 快速开始

把这句话发给 Codex：

```text
安装 jev-browser 这个 skill，地址是 https://github.com/wanghai673/jev-browser-skill
```

装好就可以说：

```text
打开 B 站，搜索 machine learning，展示搜索结果。
```

也可以在完成配置后，通过 Python 入口直接调用：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/jev-browser/scripts/jev.py" run \
  --url 'https://www.bilibili.com' \
  --goal 'Search Bilibili for machine learning and show the search results.' \
  --inputs '[{"value":"machine learning","purpose":"Bilibili search query"}]' \
  --show
```

支持 macOS + Chrome，需要 Python 3.12+ 和 uv。首次配置由 Skill 引导完成。

## 致谢

- [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast)：上游浏览器 Agent 运行时。本项目在其基础上适配 Codex Skill，加入预置输入、连续执行、配置自检与结果记录等能力。
- [TypeSafe / Jev](https://docs.typesafe.ai/)：提供低延迟的结构化决策 API，负责选择浏览器动作与操作目标。
- [Browser Harness](https://github.com/browser-use/browser-harness)：提供 Chrome 连接与浏览器操作的基础设施。

代码采用 [MIT License](LICENSE)，保留上游版权声明。项目来源与适配说明见 [NOTICE](NOTICE)。

欢迎 Star、提交 Issue，或分享你用 Jev 完成的浏览器任务。
