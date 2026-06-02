<div align="center">

# 🏷️ retitle

### 你的 AI 会话是一笔宝贵财富。烂标题把它埋了，retitle 帮你重新挖出来。

每一次和 Claude Code、Codex、Cursor 的会话，都是你辛苦攒下的上下文——你追过的 bug、
做过的决策、上线的代码。这是一笔**宝贵的财富**。可三个工具都只用你的**第一条消息**
给会话命名，然后永远冻在那儿。一小时后工作早已转向，侧边栏却还写着*「检查分支是否同步」*。
乘以几百个会话，你最值钱的历史就变成了一座**搜不动的坟场**。

这么好的财富，不该被一个过时的标题浪费掉。

**`retitle` 在后台静静运行，一旦会话空闲下来，就把标题改成这次工作*真正*变成的样子
——三个工具通吃。** 然后用 `retitle search` 把这笔历史财富挖出来：一次性在 Claude Code、
Codex、Cursor 里找回任何过去的会话。

[![CI](https://github.com/study8677/retitle/actions/workflows/ci.yml/badge.svg)](https://github.com/study8677/retitle/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/study8677/retitle?label=release&color=blue)](https://github.com/study8677/retitle/releases)
[![GitHub stars](https://img.shields.io/github/stars/study8677/retitle?style=flat&color=yellow)](https://github.com/study8677/retitle/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](pyproject.toml)
[![Supported tools](https://img.shields.io/badge/tools-8-9c27b0.svg)](#支持的工具)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-orange.svg)](CONTRIBUTING.md)

[English](README.md) · **简体中文** · [使用配方](docs/COOKBOOK.md)

</div>

<p align="center">
  <img src="https://raw.githubusercontent.com/study8677/retitle/main/assets/demo.svg" alt="retitle 把停在第一句话的 Claude Code / Codex / Cursor 会话标题改成最新内容" width="820">
</p>

<p align="center"><b>30 秒零安装试用</b> —— 只读预览，不写入任何东西：</p>

```bash
uvx --from git+https://github.com/study8677/retitle.git retitle list
```

---

## 痛点：一座搜不动的金矿

每个 AI 编程工具都只在开场时根据第一条提示词命名一次，然后就把标题冻在那儿：

| 工具 | 侧边栏还显示 | 这个会话其实早就在做 |
|------|-------------|----------------------|
| **Cursor** | `加一个加载动画` | *把数据库迁移到 Postgres* |
| **Codex** | `修个 README 里的错别字` | *排查不稳定的 CI 流水线* |
| **Claude Code** | `检查分支是否同步` | *实现审计日志功能* |

标题在十分钟内就成了谎言。于是一周后，你*明明记得*之前用 AI 解过这个一模一样的 bug，却怎么也翻不到那次对话——财富明明在，却被埋住了。`retitle` 让标题始终如实，这座金矿才能一直可被搜索。

<sub>（示例均为虚构——`retitle` 只在本地读取你的会话，绝不会把它们发布到任何地方。）</sub>

## 长这样

```console
$ retitle list

Claude Code
     16m  检查分支是否同步             → 实现审计日志写入
     34m  —                          → 修复仪表盘加载白屏
      2m  重构部署脚本                 · 使用中

Codex
    1.2h  搭建新服务                   → 设计会话自动改名流程
    2.1h  审查 API 改动                · 距上次改名无新内容

Cursor
     29m  加一个加载动画               → 修复登录页样式问题
    2.4h  最初的同步问题               → 定位重复报错的根因

下一轮将重命名 7 个会话（空闲 ≥ 5m，namer=heuristic）。
运行 `retitle once` 立即应用，或 `retitle install` 让它持续运行。
```

---

## 🔍 还能：找回任何历史会话

准确的标题只是一半价值，另一半是能**找回**它。`retitle search` 一次性在
Claude Code、Codex、Cursor 里搜：

```console
$ retitle search "stripe webhook"

🔍 "stripe webhook" — 2 matches

  Cursor        3h    Wire up the Stripe webhook handler    payments-api
  Claude Code   2d    Debug the Stripe webhook signature    billing-svc

$ retitle search postgres --content      # 连消息正文一起搜，带匹配片段
```

---

## 快速开始

`retitle` 是纯 Python、**零依赖**。把它作为独立 CLI 安装：

```bash
# 用 pipx（推荐）
pipx install git+https://github.com/study8677/retitle.git

# 或用 uv
uv tool install git+https://github.com/study8677/retitle.git

# 或从源码
git clone https://github.com/study8677/retitle.git && cd retitle
pip install -e .
```

然后：

```bash
retitle status         # 在这台机器上检测到了什么？
retitle list           # 预览：当前标题 → 建议标题（不写入任何东西）
retitle once           # 立即跑一轮重命名
retitle install        # 装成后台服务，永久运行（launchd / systemd）
```

就这样。装好后它每分钟醒来一次，找出已空闲 5 分钟的会话，把其中「自上次以来内容有变化」的重新命名。

---

## 工作原理

```
        ┌──────────── 每隔 poll_seconds（默认 60s） ────────────┐
        │                                                       │
   discover ──► 对每个空闲 ≥ 5m 且有新内容的会话 ──► namer ──► 写回标题
   （按工具）        │                                   │           │
   Claude Code      │ 仍在使用 → 跳过                    │           ├─ Claude Code：追加一行 `ai-title`
   Codex            │ 自上次改名无变化 → 跳过            │           ├─ Codex：      UPDATE threads SET title
   Cursor           │ 被人工改过名 → 跳过（直到          │           └─ Cursor：     更新 composerHeaders + composerData
                    │     对话出现新内容）              │
```

每个会话的判定规则刻意保守：

1. **还在用?** 空闲时间未达到阈值 → 不动它。
2. **没新东西?** 内容哈希与上次写入的标题一致 → 跳过（重复运行不花一分钱）。
3. **手动改过名?** 我们绝不覆盖人工编辑——直到你发了新消息、它再次空闲为止。
4. 否则：生成一个新标题并写入。

这让整个工具**幂等**且**可以放心地长期运行**。

**标题是怎么来的。** 默认 retitle 会调用你已经登录的 `claude`（或 `codex`）命令行
——`claude --model haiku -p "…"`——所以标题是对话的真实 LLM 总结，且无需 API key。
没装 CLI？就退回离线启发式。

**按需重命名历史会话。** 为了不一次性对所有会话都调用 CLI，单次扫描最多改
`batch_size` 个（默认 25），最近的优先；剩下的由后台在后续轮次里慢慢改完。

```bash
retitle once                # 立即改最近的一批
retitle once --limit 50     # 改最近的 50 个
retitle once --all          # 改所有符合条件的历史（idle 0、不限时间；较慢）
retitle once --all --dry-run   # 预览整个积压，不写入
```

---

## 支持的工具

| 工具 | 读取 | 写入 | 状态 |
|------|------|------|------|
| **Claude Code** | `~/.claude/projects/**/<id>.jsonl` | 追加一行 `ai-title`（纯追加——最安全的写法） | ✅ 稳定 |
| **Codex** | `~/.codex/state_*.sqlite` + rollout 文件 | `UPDATE threads SET title` | ✅ 稳定 |
| **Cursor** | `state.vscdb`（`composerHeaders` + `composerData`） | 同时更新两处标题字段 | ⚠️ 实验性 |
| **Antigravity** *(Google)* | IDE: `state.vscdb`（`antigravityUnifiedStateSync.trajectorySummaries`）— Companion: `~/.gemini/antigravity/agyhub_summaries_proto.pb` | 重写对应 `CascadeTrajectorySummary` 的 `summary` 字段（Companion 走原子 rename 重写文件） | ⚠️ 实验性 — [看说明](#antigravity-说明) |
| **Continue** *(continue.dev)* | `~/.continue/sessions/<id>.json` | 改写 `title` + 原子 rename | ⚠️ 实验性 |
| **Zed** *(zed.dev Assistant)* | `~/Library/Application Support/Zed/conversations/<uuid>.json` 等 | 改写 `summary` / `title` + 原子 rename | ⚠️ 实验性 — schema 随 Zed 版本变 |
| **Windsurf** *(Codeium)* | `state.vscdb`(Cursor 分支布局) | 复用 Cursor 的写入路径,只换路径 | ⚠️ 实验性 |
| **Aider** | `.aider.chat.history.md`(每个项目一份) | 写到 `.aider.chat.history.md.title` 旁路文件(Aider 本身只读) | ⚠️ 实验性 — 只读 |

> **关于「应用开着时写入」。** Codex、Cursor 和 Antigravity 都把数据存在正在使用的 SQLite
> 数据库里。`retitle` 写入很谨慎（读取走只读连接、写入设了 `busy_timeout`），而且只碰
> *空闲*会话。但宿主 App 会把对话缓存在内存里，所以你在磁盘上改的标题，可能在你重新打开
> 那个对话时被运行中的 App 覆盖。想让结果最可靠，就在 App 关闭时让 `retitle` 跑。Claude
> Code 的纯追加格式没有这个顾虑。

### Antigravity 说明

Antigravity 有两个形态——**IDE 版**(基于 VS Code 的客户端,带 Gemini 侧边栏)和
**Companion App**(独立桌面端,Windows-only)。`retitle` 两种都支持:

| 形态 | 标题存储位置 | 格式 |
|---|---|---|
| IDE | `state.vscdb` → `ItemTable['antigravityUnifiedStateSync.trajectorySummaries']` | base64(envelope(base64(`CascadeTrajectorySummary`)))——和 Cursor 一样套两层 base64 |
| Companion App | `~/.gemini/antigravity/agyhub_summaries_proto.pb` | 裸 protobuf,`repeated TopEntry { uuid; CascadeTrajectorySummary }` |

两种形态共享同一个 `CascadeTrajectorySummary` schema(从 Antigravity 2.0 的
`FileDescriptorProto` 反编译来),只是外层封装不同。IDE 走 SQL `UPDATE`,Companion
走「写临时文件 + 原子 rename」。两种形态的对话正文(`~/.gemini/antigravity/conversations/<uuid>.pb`)
都是**加密**的,但 Antigravity 的 agent 都会把自己写的明文工作文档放在
`~/.gemini/antigravity/brain/<uuid>/` 下(`task.md`、`implementation_plan.md`、
`walkthrough.md`,以及对应的 `*.metadata.json` 摘要)——这些就是 `retitle` 喂给 namer
用来重新起标题的素材。

- ✅ Antigravity 的对话会出现在 `retitle list` / `retitle search` / `retitle stats` 里
- ✅ **自动改名**对所有产生过 brain artifact 的对话都生效(也就是那些长一点、有计划文档的
  会话——标题最容易跑偏的就是这一类)。短对话还没生成 artifact 的会被「实质内容」闸门跳过,
  这是合理的——没素材也起不了名字。
- ✅ `retitle once --tool antigravity` 手动改名任何时候都能用。

如果以后 Antigravity 出了官方扩展 API 直接暴露对话正文,我们再把那一层接上做全覆盖。
跟进:[#1](https://github.com/study8677/retitle/issues/1).

---

## 命名后端（namer）—— 无需 API key

默认的 **`auto`** **完全不需要 API key**：retitle 直接复用你**已经登录**的 `claude`
或 `codex` 命令行来生成高质量标题；两个都没装时，退回完全离线的启发式。你一个字
的 key 都不用填。

| `namer` | 作用 | 要 API key 吗？ |
|---------|------|----------------|
| `auto` | 用你已登录的 `claude` / `codex` CLI，否则 `heuristic` | **不要** · 默认 |
| `heuristic` | 把你最近一条消息清洗成标题；即时、离线 | 不要 |
| `claude` | 始终用 `claude` CLI（默认快速的 Haiku 模型） | 不要——复用登录 |
| `codex` | 始终用 `codex` CLI（`gpt-5-codex`） | 不要——复用登录 |
| `anthropic` | 直连 Anthropic API | 需要 `ANTHROPIC_API_KEY` |
| `openai` | 直连 OpenAI API | 需要 `OPENAI_API_KEY` |

开箱即用、零配置、不用粘贴任何 key，你就能得到 LLM 质量的标题（花的是你已有的
额度）。想要零成本/完全离线？设 `namer = "heuristic"`。

```bash
retitle status        # 会显示 auto 实际解析到了谁，例如 "namer=auto → claude"
```

---

## 可选:GUI app(菜单栏 + 仪表盘)

仓库里带了**两个**可选的 GUI 前端——都只是 Python CLI 的一层 viewer,真正
做改名的还是你之前 `retitle install` 装好的那个 daemon。

| 平台 | 目录 | 工具栈 | 状态 |
|---|---|---|---|
| **macOS 原生** | [`macos-app/`](macos-app/) | Swift + SwiftUI,只需 Command Line Tools | ✅ 已测试 |
| **Windows / 跨平台** | [`windows-app/`](windows-app/) | Python + PySide6 (Qt6),Windows / macOS / Linux 都能跑 | ⚠ 未测试 — 详见对应 README |

两个 app 的功能集是**对等的**:

- **托盘 / 菜单栏图标** — 显示运行 / 暂停状态,展示最近几次改名(旧标题 → 新标题)
- **仪表盘窗口** — 顶部 stat 卡片(已追踪 / 会话数 / 待处理 / 累计改名);带品牌色的
  工具过滤(Claude / Codex / Cursor / Antigravity);跨标题 + 路径搜索;每行的
  "立即改名" 按钮(跳过空闲闸门);改名前后 diff 显示
- **可视化设置面板** — 滑块、下拉、勾选框,读写你的 `config.toml`,不用手编 TOML
- **人类化进度** — 没有任何原始 stderr;所有信息都翻译成 toast 或系统通知
- **首次启动权限引导**(macOS)— 一键跳到系统设置 → 完全磁盘访问,授权一次后
  系统就不会每次扫描都弹权限框
- **懒扫描** — 只在仪表盘打开 / 你手动点 Refresh 时才扫描会话,平时只 poll 轻量的
  status,避免反复触发权限对话框
- **国际化** — 英文 + 简体中文,跟随系统语言自动切换

### macOS 构建

```bash
cd macos-app
./build-app.sh
open Retitle.app
```

把 `Retitle.app` 拖到 `~/Applications`,登录项加上,重启后自动启动菜单栏图标。
这是 `LSUIElement` app——只在菜单栏出现,不上 Dock。

### Windows 构建

```powershell
cd windows-app
python -m venv .venv ; .venv\Scripts\activate
pip install -e .
retitle-gui
```

开机自启:把 `retitle-gui` 的快捷方式扔到
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`。

### 架构

两个 app 都通过 `subprocess` / `Process` 调 Python CLI,数据走 JSON。CLI 提供
`retitle status --json` / `list --json` / `stats --json` / `search --json` /
`once --session <id>` 等命令——GUI 调它们,展示结果。**没有新增任何状态、存储
或额外 daemon**,Python daemon 仍然是唯一的真理来源。

---

## 配置

`retitle config` 会创建并打印 `~/.config/retitle/config.toml`：

```toml
idle_seconds = 300          # 空闲 5 分钟后改名
poll_seconds = 60           # 每分钟扫一次
batch_size = 25             # 每次扫描最多改 N 个（0 = 不限）
tools = ["claude-code", "codex", "cursor"]
namer = "heuristic"         # heuristic | claude | codex | anthropic | openai
max_age_days = 7            # 忽略超过一周未活动的会话
min_user_messages = 1       # 至少要有这么多条真实消息
dry_run = false

[anthropic]
model = "claude-haiku-4-5"

[openai]
model = "gpt-4o-mini"
```

任何字段都能在单次运行时覆盖：`retitle run --idle 600 --namer anthropic --tool cursor`。

## 命令

| 命令 | 说明 |
|------|------|
| `retitle list` | 预览所有发现的会话及其建议标题（不写入任何东西） |
| `retitle search <关键词>` | 跨所有工具按标题搜索会话（加 `--content` 连正文一起搜） |
| `retitle stats` | 快速概览：各工具会话数、多少未命名 / 已空闲 |
| `retitle once` | 立即改最近一批（`--limit N`、`--all`、`--dry-run`） |
| `retitle run` | 在前台持续运行（可加 `--once`、`--dry-run`） |
| `retitle install` | 安装并启动后台服务（macOS 用 launchd，Linux 用 systemd） |
| `retitle uninstall` | 停止并移除后台服务 |
| `retitle status` | 显示配置、检测到的工具、守护进程状态 |
| `retitle config` | 创建 / 打印配置文件 |

> `retitle list`、`retitle search`、`retitle stats` 都支持 `--json`，方便脚本集成。

---

## 隐私与安全

- **不用填 key；命名走你自己已登录的工具。** 默认的 `auto` 会让你已登录的 `claude`/`codex`
  CLI 来写标题，所以一小段对话摘录会发给对应服务商（花的是你已有的额度——无需 API key）。
  想要任何数据都不离开本机？设 `namer = "heuristic"`，就是 100% 离线。
- **它只改标题。** `retitle` 读取对话、写入一个标题字段 / 追加一行，
  从不编辑、删除或重排你的对话内容。
- **可逆且幂等。** 标题改坏了也只是个标题——发条消息它就会重新评估。
  内容没变时重复运行什么都不做。

## 常见问题

**会和工具自带的自动命名打架吗?**
不会。工具只命名一次就停了；`retitle` 只在会话空闲后才动手，两者不会同时写。

**会覆盖我自己设的标题吗?**
不会——除非你给那个会话发了新消息。在对话真正往前走之前，人工标题都会被尊重。

**需要填 API key 吗?**
不需要。默认会复用你已登录的 `claude` / `codex` CLI（不用粘贴任何 key），花的是你
已有的额度；想零成本就设 `namer = "heuristic"`（完全离线）。

**一直开着安全吗?**
安全——这就是它的设计目标。见[工作原理](#工作原理)。唯一的注意点是「Cursor 开着时改它的数据库」（见上文）。

## 参与贡献

好奇它的内部原理——包括逆向出的三个工具的会话存储格式？见 **[ARCHITECTURE.md](ARCHITECTURE.md)**。

新增一个工具的支持只需一个文件——在 `src/retitle/adapters/` 里实现四个方法
（`available`、`discover`、`read_transcript`、`set_title`）。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

```bash
git clone https://github.com/study8677/retitle.git && cd retitle
pip install -e ".[dev]"
pytest
```

## 点个 Star

你的 AI 会话是一笔值得守护的财富。如果 retitle 帮你把它捡了回来，点个 ⭐ 能帮更多人发现它，
也会激励我适配更多工具（Aider、Continue、Zed……）。欢迎提 issue 和 PR。

## 致谢

- **[@xiongaox](https://github.com/xiongaox)** 提出了 [#1](https://github.com/study8677/retitle/issues/1)
  要求支持 Antigravity——正是这个 issue 推着我把整套 Antigravity 适配器做了出来:从反编译
  protobuf schema,到发现 `brain/` 明文素材,再到他后来把 Companion App 的 `.pb` 上传到
  issue,直接解锁了 Companion 那条路径——全都源自这个起点。谢谢 🙏。

## 许可证

[MIT](LICENSE) © JingWen Fan
