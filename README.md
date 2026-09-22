<div align="center">

![Jev Browser：快速、低成本，让 Codex 高效操作浏览器](docs/assets/hero.png)

# ⚡ Jev Browser Skill

### 让 Codex 操作浏览器，更快，也更省。

**低延迟决策 · 低成本 API · 复用你的 Chrome**

搜索、筛选、填写、打开网页。说出目标，把连续操作交给 Jev。

[![License: MIT](https://img.shields.io/badge/License-MIT-lime.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/Codex-Agent%20Skill-06b6d4.svg)](skills/jev-browser/SKILL.md)
[![Checks](https://github.com/wanghai673/jev-browser-skill/actions/workflows/checks.yml/badge.svg)](https://github.com/wanghai673/jev-browser-skill/actions/workflows/checks.yml)

[快速开始](#快速开始) · [为什么快又省](#为什么快又省) · [查看 Skill](skills/jev-browser/SKILL.md)

</div>

## 低延迟、低成本，让网页操作快起来

Codex 直接操作浏览器时，由所选主模型逐步决策；接入 Jev 后，Codex 负责理解目标、准备任务，把连续点击与选择交给 Jev。

**⚡ Jev 官方报告的模型请求延迟为 70–500 ms。** 本项目把动作和目标放在一次请求中选择，并让 Jev 连续执行，减少每一步的模型等待与交接。

### 与 Codex 可选模型的 API 单价对比

| 决策模型 | 输入 / 百万 token | 输出 / 百万 token | 输入单价相对 Jev |
| --- | ---: | ---: | ---: |
| **Jev** | **$0.042** | **免费** | **1×** |
| [GPT-5.6 Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra) | $2.00 | $12.00 | 47.6× |
| [GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol) | $4.00 | $20.00 | 95.2× |
| [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) | $10.00 | $50.00 | 238.1× |

同样计费 **10 万输入 token**，Jev 为 **$0.0042**；上表三款模型分别为 **$0.20 / $0.40 / $1.00**，另计输出费用。高频网页决策交给 Jev，Codex 保留对任务的理解与结果回复。

<sub>核对于 2026-09-22；Jev 数据来自 [TypeSafe 官方](https://typesafe.ai/blog/introducing-system-one-models-and-jev)，OpenAI 价格见表中模型链接。比较采用标准、未缓存、短上下文 API 单价，不代表 Codex 订阅扣费或完整任务的成本倍数。模型 token 用量可能不同，任务总开销还包括 Codex、网页加载与重试；本项目尚未发布与 Codex 直接操作浏览器的同任务耗时对照。</sub>

## 为什么快又省

Jev 直接从候选项中做选择，无需逐字生成操作说明。本 Skill 进一步缩短了浏览器执行链：

| 设计 | 带来的变化 |
| --- | --- |
| **一次请求，同时选动作和目标** | “做什么”和“点哪里”在同一次 Jev 请求里决定，减少网络往返。 |
| **提前备好文字，选中就填** | Codex 预先提供搜索词等内容，输入阶段直接填入，省去额外的文字生成调用。 |
| **直接读取页面文字和控件** | 默认从 DOM 获取页面信息，省去逐步截图与图像理解的开销。 |
| **一次交代，连续执行** | Jev 自行完成点击、滚动和切页；Codex 在结果返回后回复，减少模型之间的反复交接。 |

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
