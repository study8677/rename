"""Tiny dict-based i18n for the GUI.

The translation map mirrors the macOS Localizable.strings 1:1 so behavior is
consistent across platforms. Language is auto-detected from the system locale
at startup; users can override with the ``RENAME_GUI_LANG`` env var
(``en`` or ``zh-Hans``).
"""

from __future__ import annotations

import locale
import os

_STRINGS = {
    # status
    "running": {"en": "rename is running", "zh-Hans": "rename 运行中"},
    "running_sub": {
        "en": "Scanning idle sessions and renaming in the background.",
        "zh-Hans": "正在后台扫描空闲会话并改名。",
    },
    "paused": {"en": "Paused", "zh-Hans": "已暂停"},
    "paused_sub": {
        "en": "The daemon is installed but not running. Click Resume to start.",
        "zh-Hans": "后台服务已安装但没在跑。点 “恢复” 启动。",
    },
    "no_daemon": {"en": "Daemon not installed", "zh-Hans": "后台服务未安装"},
    "no_daemon_sub": {
        "en": "Run `rename install` (Linux/macOS) or just keep this app open "
              "to keep renaming in the foreground.",
        "zh-Hans": "可以跑一次 `rename install`(Linux/macOS),或者就开着这个 app,"
                   "让它在前台跑改名。",
    },
    "loading": {"en": "Loading…", "zh-Hans": "加载中…"},
    "cli_not_found": {
        "en": "rename CLI not found. Install with: pipx install rename-cli",
        "zh-Hans": "找不到 rename 命令。请用 pipx install rename-cli 安装。",
    },
    "recent_renames": {"en": "Recent renames", "zh-Hans": "最近改名"},
    "no_recent": {
        "en": "Nothing renamed yet. The daemon will catch up on its next pass.",
        "zh-Hans": "暂无改名记录。后台服务下一轮扫描时会处理。",
    },
    # tray menu
    "open_dashboard": {"en": "Open Dashboard…", "zh-Hans": "打开仪表盘…"},
    "settings": {"en": "Settings…", "zh-Hans": "设置…"},
    "pause_daemon": {"en": "Pause daemon", "zh-Hans": "暂停后台服务"},
    "resume_daemon": {"en": "Resume daemon", "zh-Hans": "恢复后台服务"},
    "show_log": {"en": "Show log", "zh-Hans": "查看日志"},
    "quit": {"en": "Quit Rename", "zh-Hans": "退出 Rename"},
    # dashboard
    "tracked": {"en": "Tracked", "zh-Hans": "已追踪"},
    "total_sessions": {"en": "Sessions", "zh-Hans": "会话总数"},
    "stale": {"en": "Stale", "zh-Hans": "待处理"},
    "renamed": {"en": "Renamed", "zh-Hans": "累计改名"},
    "filter_all": {"en": "All", "zh-Hans": "全部"},
    "search_placeholder": {
        "en": "Search titles, proposed names, or paths",
        "zh-Hans": "搜索标题、新名字或路径",
    },
    "rename_now": {"en": "Rename now", "zh-Hans": "立即改名"},
    "rename_historical": {
        "en": "Rename historical sessions",
        "zh-Hans": "改名历史会话",
    },
    "historical_confirm_title": {
        "en": "Rename all historical sessions?",
        "zh-Hans": "确定改名所有历史会话?",
    },
    "historical_confirm_body": {
        "en": "rename will send every pre-existing conversation through the "
              "namer. This can take a while and (with claude/codex/anthropic/openai) "
              "consume tokens. Continue?",
        "zh-Hans": "rename 会把每一个历史会话都送给 namer。这可能需要一段时间,"
                   "如果你用的是 claude / codex / anthropic / openai,还会消耗 token。继续?",
    },
    "historical_run": {"en": "Rename everything", "zh-Hans": "全部改名"},
    "historical_dry": {"en": "Preview only", "zh-Hans": "只预览"},
    "historical_cancel": {"en": "Cancel", "zh-Hans": "取消"},
    "toast_historical_started": {
        "en": "Historical rename started — this can take a while.",
        "zh-Hans": "历史改名已开始——会有一段时间。",
    },
    "toast_historical_done": {
        "en": "Historical rename finished.",
        "zh-Hans": "历史改名已完成。",
    },
    "rename_in_progress": {"en": "Renaming…", "zh-Hans": "改名中…"},
    "refresh": {"en": "Refresh", "zh-Hans": "刷新"},
    "scanning": {"en": "Scanning…", "zh-Hans": "扫描中…"},
    "empty_initial": {"en": "No sessions yet.", "zh-Hans": "目前没有会话。"},
    "empty_filtered": {
        "en": "No sessions match this filter.",
        "zh-Hans": "当前过滤条件下没有会话。",
    },
    "scan_now": {"en": "Scan now", "zh-Hans": "立即扫描"},
    "loading_sub": {
        "en": "Reading your AI session stores. On the very first run, the OS "
              "may briefly stutter while indexing each path.",
        "zh-Hans": "正在读取你的 AI 会话存储。首次扫描时,系统可能会卡一下。",
    },
    # reasons (engine plan.reason translations)
    "reason_active": {"en": "still active", "zh-Hans": "对话还活跃"},
    "reason_too_short": {"en": "too short to title yet", "zh-Hans": "内容太短"},
    "reason_already_current": {"en": "title already accurate", "zh-Hans": "标题已经准确"},
    "reason_user_edited": {"en": "edited by hand", "zh-Hans": "用户手动改过"},
    "reason_no_namer": {"en": "namer unavailable", "zh-Hans": "namer 不可用"},
    "reason_no_content": {"en": "no readable content", "zh-Hans": "没有可读内容"},
    "reason_idle": {"en": "idle %s", "zh-Hans": "已空闲 %s"},
    # toasts
    "toast_renamed": {"en": "Renamed to: %s", "zh-Hans": "已改名为:%s"},
    "toast_refreshed": {"en": "Sessions refreshed.", "zh-Hans": "会话已刷新。"},
    "toast_daemon_paused": {
        "en": "Background renaming paused.",
        "zh-Hans": "后台改名已暂停。",
    },
    "toast_daemon_resumed": {
        "en": "Background renaming resumed.",
        "zh-Hans": "后台改名已恢复。",
    },
    # settings
    "settings_title": {"en": "Rename Settings", "zh-Hans": "Rename 设置"},
    "settings_section_renaming": {"en": "Renaming", "zh-Hans": "改名规则"},
    "settings_section_daemon": {"en": "Background daemon", "zh-Hans": "后台服务"},
    "settings_section_namer": {
        "en": "Namer (how new titles are generated)",
        "zh-Hans": "命名后端(新标题怎么生成)",
    },
    "settings_section_tools": {"en": "Tools to manage", "zh-Hans": "管理哪些工具"},
    "settings_idle_seconds": {
        "en": "Wait until session is idle (seconds)",
        "zh-Hans": "会话空闲多久才动(秒)",
    },
    "settings_min_user_messages": {
        "en": "Minimum user messages",
        "zh-Hans": "至少需要多少条用户消息",
    },
    "settings_max_age_days": {
        "en": "Look back at most (days)",
        "zh-Hans": "最多往前看(天)",
    },
    "settings_poll_seconds": {
        "en": "Daemon poll interval (seconds)",
        "zh-Hans": "后台扫描间隔(秒)",
    },
    "settings_batch_size": {
        "en": "Max renames per pass (0 = no cap)",
        "zh-Hans": "每轮最多改多少个(0 = 不限)",
    },
    "settings_dry_run": {
        "en": "Dry-run (preview only, no writes)",
        "zh-Hans": "Dry-run(只预览,不写入)",
    },
    "settings_namer": {"en": "Namer", "zh-Hans": "Namer"},
    "settings_claude_model": {"en": "Claude model", "zh-Hans": "Claude 模型"},
    "settings_codex_model": {"en": "Codex model", "zh-Hans": "Codex 模型"},
    "settings_save": {"en": "Save", "zh-Hans": "保存"},
    "settings_revert": {"en": "Revert", "zh-Hans": "撤销改动"},
    "settings_saved": {
        "en": "Saved. The daemon picks up the new values on its next pass.",
        "zh-Hans": "已保存。下次后台扫描时会用上新值。",
    },
    # daemon status pill
    "daemon_running": {"en": "Daemon running", "zh-Hans": "后台运行中"},
    "daemon_stopped": {"en": "Daemon stopped", "zh-Hans": "后台已停止"},
}


def detect_lang() -> str:
    override = os.environ.get("RENAME_GUI_LANG")
    if override in ("en", "zh-Hans"):
        return override
    try:
        loc = locale.getlocale()[0] or ""
    except (locale.Error, AttributeError):
        loc = ""
    if "zh" in loc.lower():
        return "zh-Hans"
    return "en"


_LANG = detect_lang()


def t(key: str, *args) -> str:
    bundle = _STRINGS.get(key)
    if not bundle:
        return key
    text = bundle.get(_LANG) or bundle.get("en") or key
    if args:
        try:
            return text % args
        except (TypeError, ValueError):
            return text
    return text
