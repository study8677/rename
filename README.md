<div align="center">

# rename

#### 让你的 AI 会话标题，始终对得上现在的内容。

**简体中文** · [English](README.en.md) · [使用配方](docs/COOKBOOK.md)

</div>

<p align="center">
  <img src="https://raw.githubusercontent.com/study8677/rename/main/assets/demo.svg" alt="rename 把停在第一句话的 Claude Code / Codex / Cursor 会话标题改成最新内容" width="820">
</p>

<p align="center">
  <a href="macos-app/">
    <img src="https://raw.githubusercontent.com/study8677/rename/main/assets/dashboard.svg" alt="原生菜单栏 / 托盘应用，一处看清 Claude Code、Codex、Cursor、Antigravity 的所有会话" width="820">
  </a>
</p>

<br>

Claude Code、Codex、Cursor 都只用你的**第一条消息**给会话命名，然后永远冻在那儿。
一小时后工作早就转向，侧边栏却还写着「检查分支是否同步」。乘以几百个会话,你
最值钱的历史就变成了搜不动的坟场。

`rename` 在后台运行。会话一空闲下来,它就把标题改成这次工作真正变成的样子;
然后用 `rename search` 跨工具找回任何历史会话。

<br>

## 安装

```bash
brew install study8677/rename/rename
pipx install git+https://github.com/study8677/rename.git
uv tool install git+https://github.com/study8677/rename.git
```

无需 API key,零运行时依赖。支持 macOS、Linux 和 Windows。

<br>

## 使用

```bash
rename status         # 检测到了什么
rename list           # 预览新标题(不写入)
rename once           # 跑一轮然后退出
rename install        # 永久后台运行
```

后台每分钟醒一次,找空闲 ≥ 5 分钟、内容自上次改名后有变化的会话改名。
没变化的不会重写,重复运行无副作用。

<br>

---

<br>

## 痛点

| 工具 | 侧边栏还显示 | 这个会话其实早就在做 |
|------|-------------|----------------------|
| Cursor | `加一个加载动画` | 把数据库迁移到 Postgres |
| Codex | `修个 README 里的错别字` | 排查不稳定的 CI 流水线 |
| Claude Code | `检查分支是否同步` | 实现审计日志功能 |

标题在十分钟内就成了谎言。一周后你明明记得之前用 AI 解过这个 bug,却翻不到那次对话——
对话还在,只是被错误的标签盖住了。

<br>

## 长这样

```console
$ rename list

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

下一轮将重命名 7 个会话(空闲 ≥ 5m, namer=heuristic)。
运行 `rename once` 立即应用,或 `rename install` 让它持续运行。
```

<br>

## 搜索

准确的标题只是一半,另一半是找回。`rename search` 一次跨所有工具搜:

```console
$ rename search "stripe webhook"

  Cursor        3h    Wire up the Stripe webhook handler    payments-api
  Claude Code   2d    Debug the Stripe webhook signature    billing-svc

$ rename search postgres --content   # 连消息正文一起搜,带匹配片段
```

<br>

---

<br>

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

**标题是怎么来的。** 默认 rename 会调用你已经登录的 `claude`（或 `codex`）命令行
——`claude --model haiku -p "…"`——所以标题是对话的真实 LLM 总结，且无需 API key。
没装 CLI？就退回离线启发式。

**装上就用，不会偷偷改你的历史。** 第一次跑的时候 rename 会记一个"基线时间戳"，
之后后台只会改"基线之后才活跃"的会话——你装 rename 之前的旧聊天不会被自动碰，
除非你明确同意。

**按需重命名历史会话。** 想把积压的旧会话也跑一遍？dashboard 上有
**"改名历史会话"** 按钮（带确认对话框 + dry-run），命令行对应是：

```bash
rename once                          # 只改最近的一批（默认行为）
rename once --historical --dry-run   # 预览所有"装 rename 之前"的会话
rename once --historical             # 真把整个历史跑一遍（不受 max-age / batch 限制）
rename once --session <id>           # 强行只改某一个会话
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
> 数据库里。`rename` 写入很谨慎（读取走只读连接、写入设了 `busy_timeout`），而且只碰
> *空闲*会话。但宿主 App 会把对话缓存在内存里，所以你在磁盘上改的标题，可能在你重新打开
> 那个对话时被运行中的 App 覆盖。想让结果最可靠，就在 App 关闭时让 `rename` 跑。Claude
> Code 的纯追加格式没有这个顾虑。

### Antigravity 说明

Antigravity 有两个形态——**IDE 版**(基于 VS Code 的客户端,带 Gemini 侧边栏)和
**Companion App**(独立桌面端,Windows-only)。`rename` 两种都支持:

| 形态 | 标题存储位置 | 格式 |
|---|---|---|
| IDE | `state.vscdb` → `ItemTable['antigravityUnifiedStateSync.trajectorySummaries']` | base64(envelope(base64(`CascadeTrajectorySummary`)))——和 Cursor 一样套两层 base64 |
| Companion App | `~/.gemini/antigravity/agyhub_summaries_proto.pb` | 裸 protobuf,`repeated TopEntry { uuid; CascadeTrajectorySummary }` |

两种形态共享同一个 `CascadeTrajectorySummary` schema(从 Antigravity 2.0 的
`FileDescriptorProto` 反编译来),只是外层封装不同。IDE 走 SQL `UPDATE`,Companion
走「写临时文件 + 原子 rename」。两种形态的对话正文(`~/.gemini/antigravity/conversations/<uuid>.pb`)
都是**加密**的,但 Antigravity 的 agent 都会把自己写的明文工作文档放在
`~/.gemini/antigravity/brain/<uuid>/` 下(`task.md`、`implementation_plan.md`、
`walkthrough.md`,以及对应的 `*.metadata.json` 摘要)——这些就是 `rename` 喂给 namer
用来重新起标题的素材。

- ✅ Antigravity 的对话会出现在 `rename list` / `rename search` / `rename stats` 里
- ✅ **自动改名**对所有产生过 brain artifact 的对话都生效(也就是那些长一点、有计划文档的
  会话——标题最容易跑偏的就是这一类)。短对话还没生成 artifact 的会被「实质内容」闸门跳过,
  这是合理的——没素材也起不了名字。
- ✅ `rename once --tool antigravity` 手动改名任何时候都能用。

如果以后 Antigravity 出了官方扩展 API 直接暴露对话正文,我们再把那一层接上做全覆盖。
跟进:[#1](https://github.com/study8677/rename/issues/1).

---

## 命名后端（namer）—— 无需 API key

默认的 **`auto`** **完全不需要 API key**：rename 直接复用你**已经登录**的 `claude`
或 `codex` 命令行来生成高质量标题；两个都没装时，退回完全离线的启发式。你一个字
的 key 都不用填。

| `namer` | 作用 | 要 API key 吗？ |
|---------|------|----------------|
| `auto` | 用你已登录的 `claude` / `codex` CLI，否则 `heuristic` | **不要** · 默认 |
| `heuristic` | 把你最近一条消息清洗成标题；即时、离线 | 不要 |
| `claude` | 始终用 `claude` CLI（默认快速的 Haiku 模型） | 不要——复用登录 |
| `codex` | 始终用 `codex` CLI（默认 `gpt-5.3-codex-spark`） | 不要——复用登录 |
| `anthropic` | 直连 Anthropic API,用**你自己的 key** | `api_key` 或 `ANTHROPIC_API_KEY` |
| `openai` | 直连 OpenAI API,用**你自己的 key** | `api_key` 或 `OPENAI_API_KEY` |

开箱即用、零配置、不用粘贴任何 key，你就能得到 LLM 质量的标题（花的是你已有的
额度）。想要零成本/完全离线？设 `namer = "heuristic"`。
想固定使用 Codex？设 `namer = "codex"`；模型可在 `[codex] model = "..."` 里改。

**用自己的 API key。** 想用自己的 Anthropic / OpenAI 账号而不是已登录的 CLI?把
`namer` 设为 `"anthropic"`(或 `"openai"`),然后在 `config.toml` 对应的小节里填上
`api_key = "sk-..."`,或导出 `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` 环境变量。在桌面
app 里就是 **设置 → Namer**:选好服务商、把 key 粘进去即可。key 只会写进你本机的
`config.toml`(权限锁成 `chmod 600`,只有你能读),对话摘录也只发给你选的那家服务商。

```bash
rename status        # 会显示 auto 实际解析到了谁，例如 "namer=auto → claude"
```

---

## 可选:GUI app(菜单栏 + 仪表盘)

仓库里带了**两个**可选的 GUI 前端——都只是 Python CLI 的一层 viewer,真正
做改名的还是你之前 `rename install` 装好的那个 daemon。

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
open Rename.app
```

把 `Rename.app` 拖到 `~/Applications`,登录项加上,重启后自动启动菜单栏图标。
这是 `LSUIElement` app——只在菜单栏出现,不上 Dock。

### Windows 构建

```powershell
cd windows-app
python -m venv .venv ; .venv\Scripts\activate
pip install -e .
rename-gui
```

开机自启:把 `rename-gui` 的快捷方式扔到
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`。

### 架构

两个 app 都通过 `subprocess` / `Process` 调 Python CLI,数据走 JSON。CLI 提供
`rename status --json` / `list --json` / `stats --json` / `search --json` /
`once --session <id>` 等命令——GUI 调它们,展示结果。**没有新增任何状态、存储
或额外 daemon**,Python daemon 仍然是唯一的真理来源。

---

## 配置

`rename config` 会创建并打印 `~/.config/rename/config.toml`：

```toml
idle_seconds = 300          # 空闲 5 分钟后改名
poll_seconds = 60           # 每分钟扫一次
batch_size = 25             # 每次扫描最多改 N 个（0 = 不限）
tools = ["claude-code", "codex", "cursor"]
namer = "heuristic"         # heuristic | claude | codex | anthropic | openai
max_age_days = 7            # 忽略超过一周未活动的会话
min_user_messages = 1       # 至少要有这么多条真实消息
dry_run = false

[claude]
model = "haiku"

[codex]
model = "gpt-5.3-codex-spark"

[anthropic]
model = "claude-haiku-4-5"
# api_key = "sk-ant-..."    # 你自己的 key(或设 ANTHROPIC_API_KEY)

[openai]
model = "gpt-4o-mini"
# api_key = "sk-..."        # 你自己的 key(或设 OPENAI_API_KEY)
```

任何字段都能在单次运行时覆盖：`rename run --idle 600 --namer anthropic --tool cursor`。

## 命令

| 命令 | 说明 |
|------|------|
| `rename list` | 预览所有发现的会话及其建议标题（不写入任何东西） |
| `rename search <关键词>` | 跨所有工具按标题搜索会话（加 `--content` 连正文一起搜） |
| `rename stats` | 快速概览：各工具会话数、多少未命名 / 已空闲 |
| `rename once` | 立即改最近一批（`--limit N`、`--all`、`--dry-run`） |
| `rename run` | 在前台持续运行（可加 `--once`、`--dry-run`） |
| `rename install` | 安装并启动后台服务（macOS 用 launchd，Linux 用 systemd，Windows 用开机 Startup 快捷方式） |
| `rename uninstall` | 停止并移除后台服务 |
| `rename status` | 显示配置、检测到的工具、守护进程状态 |
| `rename config` | 创建 / 打印配置文件 |

> `rename list`、`rename search`、`rename stats` 都支持 `--json`，方便脚本集成。

---

## 隐私与安全

- **不用填 key；命名走你自己已登录的工具。** 默认的 `auto` 会让你已登录的 `claude`/`codex`
  CLI 来写标题，所以一小段对话摘录会发给对应服务商（花的是你已有的额度——无需 API key）。
  想要任何数据都不离开本机？设 `namer = "heuristic"`，就是 100% 离线。
- **不会"装上就把你历史聊天全改了"。** 首次运行会记一个基线时间戳，
  之前的旧会话默认全部跳过。要重命名积压，是你点一下 dashboard 上的按钮
  （或跑 `rename once --historical`）的主动行为，不是装守护进程的副作用。
- **它只改标题。** `rename` 读取对话、写入一个标题字段 / 追加一行，
  从不编辑、删除或重排你的对话内容。
- **可逆且幂等。** 标题改坏了也只是个标题——发条消息它就会重新评估。
  内容没变时重复运行什么都不做。

## 常见问题

**会和工具自带的自动命名打架吗?**
不会。工具只命名一次就停了；`rename` 只在会话空闲后才动手，两者不会同时写。

**会覆盖我自己设的标题吗?**
不会——除非你给那个会话发了新消息。在对话真正往前走之前，人工标题都会被尊重。

**需要填 API key 吗?**
不需要。默认会复用你已登录的 `claude` / `codex` CLI（不用粘贴任何 key），花的是你
已有的额度；想零成本就设 `namer = "heuristic"`（完全离线）。

**一直开着安全吗?**
安全——这就是它的设计目标。见[工作原理](#工作原理)。唯一的注意点是「Cursor 开着时改它的数据库」（见上文）。

**装上 rename 之后，我之前那些旧聊天会怎么样?**
默认什么都不会发生。首次运行会记一个基线时间戳，后台只会改"基线之后才活跃"
的会话。想把积压的历史也跑一遍？点 dashboard 上的 **"改名历史会话"**，
或者跑 `rename once --historical --dry-run` 先预览，没问题再去掉 `--dry-run`。

## 参与贡献

好奇它的内部原理——包括逆向出的三个工具的会话存储格式？见 **[ARCHITECTURE.md](ARCHITECTURE.md)**。

新增一个工具的支持只需一个文件——在 `src/rename/adapters/` 里实现四个方法
（`available`、`discover`、`read_transcript`、`set_title`）。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

```bash
git clone https://github.com/study8677/rename.git && cd rename
pip install -e ".[dev]"
pytest
```

## 社区

本项目在 **[LINUX DO](https://linux.do)** 社区开放交流——欢迎来打个招呼、反馈问题、一起折腾。

[![LINUX DO](https://img.shields.io/badge/LINUX%20DO-Community-FFB003?logo=discourse&logoColor=white)](https://linux.do)

## 致谢

[@xiongaox](https://github.com/xiongaox) 提出了 [#1](https://github.com/study8677/rename/issues/1)
要求支持 Antigravity。这个 issue 推动了整套 Antigravity 适配器的实现:反编译 protobuf
schema、发现 `brain/` 明文素材,以及后来通过他上传的 `.pb` 解锁的 Companion App 路径。

## 许可证

[MIT](LICENSE) © JingWen Fan
