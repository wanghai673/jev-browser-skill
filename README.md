<div align="center">

![Jev Browser Skill](docs/assets/hero.png)

# ⚡ Jev Browser Skill

### 让 Codex 操作浏览器，更快，也更省。

**低延迟决策 · 低成本 API · 复用你的 Chrome**

搜索、筛选、填写、打开网页。说出目标，把连续操作交给 Jev。

[![License: MIT](https://img.shields.io/badge/License-MIT-lime.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/Codex-Agent%20Skill-06b6d4.svg)](skills/jev-browser/SKILL.md)
[![Checks](https://github.com/wanghai673/jev-browser-skill/actions/workflows/checks.yml/badge.svg)](https://github.com/wanghai673/jev-browser-skill/actions/workflows/checks.yml)

[快速开始](#快速开始) · [为什么快又省](#为什么快又省) · [查看 Skill](skills/jev-browser/SKILL.md)

</div>

## 把高频网页操作，交给低成本的 Jev

Codex 理解你的目标、准备任务，Jev 负责接下来的点击与选择。把高频决策放进轻量的执行循环，减少主模型逐步操作带来的等待和调用开销。

| ⚡ 低延迟 | 💰 低输入价格 | 🎁 输出免费 |
| :---: | :---: | :---: |
| **70–500 ms** | **$0.042 / 百万 token** | **$0** |
| 官方报告的模型请求延迟 | Jev 输入 token 单价 | Jev 输出 token 费用 |

按每次请求计费 **1 万输入 token** 估算，**100 次 Jev 决策约 $0.042**。

<sub>数据来源：[TypeSafe 官方](https://typesafe.ai/blog/introducing-system-one-models-and-jev)，核对于 2026-09-22。上述为模型延迟和 Jev API 费用；完整任务还包括网页加载、重试及 Codex 自身的耗时与费用。</sub>

## 为什么快又省

Jev 直接从候选项中做选择，无需逐字生成操作说明。本 Skill 进一步缩短了浏览器执行链：

| 设计 | 带来的变化 |
| --- | --- |
| **一次请求，同时选动作和目标** | “做什么”和“点哪里”在同一次 Jev 请求里决定，减少网络往返。 |
| **提前备好文字，选中就填** | Codex 预先提供搜索词等内容，输入阶段直接填入，省去额外的文字生成调用。 |
| **直接读取页面文字和控件** | 默认从 DOM 获取页面信息，省去逐步截图与图像理解的开销。 |
| **一次交代，连续执行** | Jev 自行完成点击、滚动和切页；Codex 在结果返回后回复，减少模型之间的反复交接。 |

## 接入简单，用起来顺手

- **沿用你的 Chrome 和登录态**：连接已有浏览器，在熟悉的网站继续操作。
- **配置由 Skill 引导**：内置 `doctor`，实际检查 Jev API 和 Chrome 调试连接，缺什么就提示什么。
- **结果返回就停止**：不追加一轮检查或操作；需要继续时，再说一句。

## 快速开始

把这句话发给 Codex：

```text
安装 jev-browser 这个 skill，地址是 https://github.com/wanghai673/jev-browser-skill
```

装好就可以说：

```text
打开 B 站，搜索 machine learning，展示搜索结果。
```

支持 macOS + Chrome，需要 Python 3.12+ 和 uv。首次配置由 Skill 引导完成。

---

基于 [Jev Ultrafast](https://github.com/browser-use/jev-ultrafast) · [MIT License](LICENSE) · [来源说明](NOTICE)
