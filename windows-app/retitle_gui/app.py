"""Main application: QApp, tray icon, dashboard window, settings dialog,
toast notifications. Single-file because the surface is small and the
constructors lean on each other heavily.

Designed for Windows but runs on macOS / Linux too (kept here as a fallback
for users who can't or don't want to build the native Swift app).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Callable

from PySide6.QtCore import (
    QObject,
    QPoint,
    QRect,
    QSize,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QGuiApplication,
    QIcon,
    QPainter,
    QPalette,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import config_store
from .bridge import DaemonControl, RetitleCLI, RetitleError, find_retitle
from .i18n import t

# --------------------------------------------------------------------------- #
# Tool branding (mirrors the Swift app)
# --------------------------------------------------------------------------- #
_TOOL_COLOR = {
    "claude-code": "#e07d33",
    "codex": "#1a9d72",
    "cursor": "#6b67eb",
    "antigravity": "#3380eb",
}
_TOOL_LABEL = {
    "claude-code": "Claude",
    "codex": "Codex",
    "cursor": "Cursor",
    "antigravity": "Antigr.",
}


def _make_tag_icon() -> QIcon:
    """Procedurally draw a small tag icon for the tray. Avoids shipping a PNG."""
    pix = QPixmap(QSize(64, 64))
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    color = QColor("#2563eb")
    painter.setBrush(color)
    painter.setPen(Qt.NoPen)
    # Pentagon tag shape.
    pts = [
        QPoint(6, 18),
        QPoint(40, 18),
        QPoint(58, 32),
        QPoint(40, 46),
        QPoint(6, 46),
    ]
    painter.drawPolygon(pts)
    painter.setBrush(Qt.white)
    painter.drawEllipse(QPoint(16, 32), 4, 4)
    painter.end()
    return QIcon(pix)


# --------------------------------------------------------------------------- #
# Background workers — keep the UI thread responsive while CLI calls run.
# --------------------------------------------------------------------------- #
class _Worker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], object], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
        except RetitleError as e:
            self.failed.emit(str(e))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"{type(e).__name__}: {e}")
        else:
            self.done.emit(result)


# --------------------------------------------------------------------------- #
# Tiny in-app toast
# --------------------------------------------------------------------------- #
class Toast(QWidget):
    """Small floating notification anchored to its parent window."""

    def __init__(self, parent: QWidget, message: str, level: str = "info") -> None:
        super().__init__(parent, Qt.SubWindow | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName("toast")
        color = {
            "info": "#2563eb",
            "success": "#16a34a",
            "warning": "#f59e0b",
            "error": "#dc2626",
        }.get(level, "#2563eb")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)
        dot = QLabel()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(f"background:{color}; border-radius:5px;")
        layout.addWidget(dot)
        label = QLabel(message)
        label.setWordWrap(True)
        layout.addWidget(label, stretch=1)
        self.setStyleSheet(
            "QWidget#toast { background: palette(window); "
            "border:1px solid palette(mid); border-radius:8px; }"
        )
        QTimer.singleShot(3500, self.deleteLater)
        self.adjustSize()
        # bottom-right of parent
        if parent:
            pos = parent.rect().bottomRight() - self.rect().bottomRight() - QPoint(20, 20)
            self.move(pos)
        self.show()


# --------------------------------------------------------------------------- #
# Dashboard window
# --------------------------------------------------------------------------- #
class DashboardWindow(QMainWindow):
    def __init__(self, state: "AppState") -> None:
        super().__init__()
        self.state = state
        self.setWindowTitle("Retitle")
        self.resize(900, 600)
        self.setMinimumSize(760, 480)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addLayout(self._build_stats_header())
        layout.addWidget(self._hline())
        layout.addLayout(self._build_filter_bar())

        self.session_scroll = QScrollArea()
        self.session_scroll.setWidgetResizable(True)
        self.session_scroll.setFrameShape(QFrame.NoFrame)
        self.session_list = QVBoxLayout()
        self.session_list.setContentsMargins(0, 0, 0, 0)
        self.session_list.setSpacing(0)
        self.session_list.addStretch(1)
        inner = QWidget()
        inner.setLayout(self.session_list)
        self.session_scroll.setWidget(inner)
        layout.addWidget(self.session_scroll, stretch=1)

        layout.addWidget(self._hline())
        layout.addLayout(self._build_footer())

        # Wire state updates
        self.state.status_changed.connect(self._on_status_changed)
        self.state.sessions_changed.connect(self._on_sessions_changed)
        self.state.toast_requested.connect(self._show_toast)

    # ----- builders ----------------------------------------------------

    def _build_stats_header(self) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setContentsMargins(18, 14, 18, 14)
        h.setSpacing(12)
        self.card_tracked = self._stat_card(t("tracked"), "0", "#3b82f6")
        self.card_total = self._stat_card(t("total_sessions"), "0", "#a855f7")
        self.card_stale = self._stat_card(t("stale"), "0", "#f59e0b")
        self.card_renamed = self._stat_card(t("renamed"), "0", "#10b981")
        for w in (self.card_tracked, self.card_total, self.card_stale, self.card_renamed):
            h.addWidget(w)
        h.addStretch(1)
        self.status_pill = QLabel()
        self.status_pill.setStyleSheet(
            "padding:6px 14px; border-radius:14px; background:palette(midlight);"
        )
        h.addWidget(self.status_pill)
        return h

    def _stat_card(self, title: str, value: str, color: str) -> QWidget:
        w = QFrame()
        w.setStyleSheet(
            "QFrame { background:palette(alternate-base); border-radius:10px; }"
        )
        layout = QHBoxLayout(w)
        layout.setContentsMargins(12, 10, 16, 10)
        layout.setSpacing(10)
        dot = QFrame()
        dot.setFixedSize(36, 36)
        dot.setStyleSheet(f"background:{color}; border-radius:8px; opacity:0.7;")
        layout.addWidget(dot)
        v = QVBoxLayout()
        v.setSpacing(0)
        value_lbl = QLabel(value)
        value_lbl.setStyleSheet("font-size:20px; font-weight:600;")
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color:palette(mid); font-size:11px;")
        v.addWidget(value_lbl)
        v.addWidget(title_lbl)
        layout.addLayout(v)
        layout.addStretch(1)
        w.value_lbl = value_lbl   # type: ignore[attr-defined]
        return w

    def _build_filter_bar(self) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setContentsMargins(18, 6, 18, 10)
        h.setSpacing(6)
        self.filter_buttons: dict[str | None, QPushButton] = {}
        self.selected_tool: str | None = None

        def make_chip(key: str | None, label: str) -> QPushButton:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked, k=key: self._select_tool(k))
            btn.setStyleSheet(
                "QPushButton { padding:5px 14px; border-radius:14px; "
                "border:1px solid palette(mid); background:transparent; } "
                "QPushButton:checked { background:rgba(37,99,235,0.18); "
                "border-color:#2563eb; color:#2563eb; }"
            )
            self.filter_buttons[key] = btn
            return btn

        all_btn = make_chip(None, t("filter_all"))
        all_btn.setChecked(True)
        h.addWidget(all_btn)
        # Tool chips are populated on first status update (we need labels).
        self._tool_chip_layout = h

        h.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("search_placeholder"))
        self.search.setMaximumWidth(260)
        self.search.textChanged.connect(lambda _t: self._refresh_session_rows())
        h.addWidget(self.search)
        return h

    def _build_footer(self) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setContentsMargins(18, 10, 18, 12)
        h.setSpacing(8)

        self.refresh_btn = QPushButton(t("refresh"))
        self.refresh_btn.clicked.connect(self.state.refresh_sessions)
        h.addWidget(self.refresh_btn)

        self.pause_btn = QPushButton(t("pause_daemon"))
        self.pause_btn.clicked.connect(self.state.pause_daemon)
        h.addWidget(self.pause_btn)

        self.settings_btn = QPushButton(t("settings"))
        self.settings_btn.clicked.connect(self.state.open_settings)
        h.addWidget(self.settings_btn)

        self.historical_btn = QPushButton(t("rename_historical"))
        self.historical_btn.clicked.connect(self._confirm_historical)
        h.addWidget(self.historical_btn)

        h.addStretch(1)
        self.footer_status = QLabel("")
        self.footer_status.setStyleSheet("color:palette(mid); font-size:11px;")
        h.addWidget(self.footer_status)

        return h

    @staticmethod
    def _hline() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setFrameShadow(QFrame.Plain)
        f.setStyleSheet("color:palette(mid);")
        return f

    # ----- updates ------------------------------------------------------

    def _on_status_changed(self, status: dict) -> None:
        self.card_tracked.value_lbl.setText(str(status.get("tracked", 0)))   # type: ignore[attr-defined]
        running = "running" in status.get("daemon", {}).get("status_line", "")
        installed = "not installed" not in status.get("daemon", {}).get("status_line", "")
        if running:
            self.status_pill.setText("● " + t("daemon_running"))
            self.status_pill.setStyleSheet(
                "padding:6px 14px; border-radius:14px; "
                "background:rgba(16,185,129,0.18); color:#10b981;"
            )
            self.pause_btn.setText(t("pause_daemon"))
            self.pause_btn.setEnabled(True)
        elif installed:
            self.status_pill.setText("● " + t("daemon_stopped"))
            self.status_pill.setStyleSheet(
                "padding:6px 14px; border-radius:14px; "
                "background:rgba(245,158,11,0.18); color:#f59e0b;"
            )
            self.pause_btn.setText(t("resume_daemon"))
            self.pause_btn.setEnabled(True)
        else:
            self.status_pill.setText("○ " + t("no_daemon"))
            self.pause_btn.setEnabled(False)

        # Tool chips
        existing = {k for k in self.filter_buttons if k is not None}
        for tool in status.get("tools", []):
            name = tool["name"]
            if name in existing:
                continue
            btn = QPushButton(tool["label"])
            btn.setCheckable(True)
            btn.setEnabled(tool.get("available", True))
            color = _TOOL_COLOR.get(name, "#2563eb")
            btn.setStyleSheet(
                "QPushButton { padding:5px 14px; border-radius:14px; "
                "border:1px solid palette(mid); background:transparent; } "
                "QPushButton:checked { background:rgba(37,99,235,0.18); "
                f"border-color:{color}; color:{color}; }}"
            )
            btn.clicked.connect(lambda _checked, k=name: self._select_tool(k))
            self.filter_buttons[name] = btn
            # Insert before the stretch.
            self._tool_chip_layout.insertWidget(
                self._tool_chip_layout.count() - 2, btn
            )

    def _on_sessions_changed(self, sessions: list[dict], stats: dict | None) -> None:
        if stats:
            self.card_total.value_lbl.setText(str(stats.get("total", {}).get("sessions", 0)))   # type: ignore[attr-defined]
            self.card_stale.value_lbl.setText(str(stats.get("total", {}).get("stale", 0)))      # type: ignore[attr-defined]
            self.card_renamed.value_lbl.setText(str(stats.get("total", {}).get("renamed", 0)))  # type: ignore[attr-defined]
        else:
            self.card_total.value_lbl.setText(str(len(sessions)))   # type: ignore[attr-defined]
        self._refresh_session_rows()

    def _select_tool(self, key: str | None) -> None:
        self.selected_tool = key
        for k, btn in self.filter_buttons.items():
            btn.setChecked(k == key)
        self._refresh_session_rows()

    def _refresh_session_rows(self) -> None:
        # Clear existing rows (keep the trailing stretch).
        while self.session_list.count() > 1:
            item = self.session_list.takeAt(0)
            if w := item.widget():
                w.deleteLater()
        q = self.search.text().lower().strip()
        rows = self.state.sessions
        if self.selected_tool:
            rows = [s for s in rows if s.get("tool") == self.selected_tool]
        if q:
            rows = [
                s for s in rows
                if q in (s.get("title") or "").lower()
                or q in (s.get("proposed_title") or "").lower()
                or q in (s.get("cwd") or "").lower()
            ]
        for s in rows:
            row = self._make_session_row(s)
            self.session_list.insertWidget(self.session_list.count() - 1, row)
        self.footer_status.setText(f"{len(rows)} / {len(self.state.sessions)}")

    def _make_session_row(self, s: dict) -> QWidget:
        w = QFrame()
        w.setStyleSheet(
            "QFrame { background:transparent; border-bottom:1px solid palette(mid); }"
            "QFrame:hover { background:rgba(37,99,235,0.06); }"
        )
        h = QHBoxLayout(w)
        h.setContentsMargins(18, 10, 18, 10)
        h.setSpacing(10)

        tool_name = s.get("tool", "")
        color = _TOOL_COLOR.get(tool_name, "#2563eb")
        badge = QLabel(_TOOL_LABEL.get(tool_name, tool_name))
        badge.setStyleSheet(
            f"background:rgba(0,0,0,0); color:{color}; padding:2px 8px; "
            f"border:1px solid {color}; border-radius:10px; font-size:11px;"
        )
        badge.setMinimumWidth(64)
        h.addWidget(badge)

        body = QVBoxLayout()
        body.setSpacing(2)
        if s.get("proposed_title") and s.get("action") == "rename":
            title_row = QHBoxLayout()
            title_row.setSpacing(6)
            old = QLabel(s.get("title") or "—")
            old.setStyleSheet("color:palette(mid); text-decoration:line-through;")
            arrow = QLabel("→")
            arrow.setStyleSheet("color:palette(mid);")
            new = QLabel(s["proposed_title"])
            new.setStyleSheet("color:#16a34a; font-weight:600;")
            title_row.addWidget(old)
            title_row.addWidget(arrow)
            title_row.addWidget(new)
            title_row.addStretch(1)
            body.addLayout(title_row)
        else:
            t_lbl = QLabel(s.get("title") or "—")
            body.addWidget(t_lbl)
        meta = QLabel(self._meta_line(s))
        meta.setStyleSheet("color:palette(mid); font-size:11px;")
        body.addWidget(meta)
        h.addLayout(body, stretch=1)

        rename_btn = QToolButton()
        rename_btn.setText("↻")
        rename_btn.setToolTip(t("rename_now"))
        rename_btn.clicked.connect(lambda: self.state.rename_now(s))
        h.addWidget(rename_btn)
        return w

    def _meta_line(self, s: dict) -> str:
        secs = s.get("idle_seconds", 0)
        if secs < 60:
            idle = f"{secs}s"
        elif secs < 3600:
            idle = f"{secs // 60}m"
        elif secs < 86400:
            idle = f"{secs // 3600}h"
        else:
            idle = f"{secs // 86400}d"
        parts = [f"⏱ {idle}"]
        cwd = (s.get("cwd") or "").replace("file://", "")
        home = str(Path.home())
        if cwd.startswith(home):
            cwd = "~" + cwd[len(home):]
        if cwd:
            short = "/".join(cwd.split("/")[-2:]) if "/" in cwd else cwd
            parts.append(f"📁 …/{short}")
        reason_text = self._reason_label(s.get("reason", ""))
        if reason_text:
            parts.append(reason_text)
        return "  ·  ".join(parts)

    @staticmethod
    def _reason_label(raw: str) -> str:
        if not raw:
            return ""
        if raw.startswith("idle "):
            return t("reason_idle", raw[5:])
        return {
            "active": t("reason_active"),
            "too short": t("reason_too_short"),
            "already current": t("reason_already_current"),
            "user edited": t("reason_user_edited"),
            "no namer": t("reason_no_namer"),
            "no content": t("reason_no_content"),
        }.get(raw, raw)

    def _confirm_historical(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(t("historical_confirm_title"))
        box.setText(t("historical_confirm_title"))
        box.setInformativeText(t("historical_confirm_body"))
        run_btn = box.addButton(t("historical_run"), QMessageBox.AcceptRole)
        dry_btn = box.addButton(t("historical_dry"), QMessageBox.ActionRole)
        box.addButton(t("historical_cancel"), QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is run_btn:
            self.state.rename_historical(dry_run=False)
        elif clicked is dry_btn:
            self.state.rename_historical(dry_run=True)

    # ----- toast ----------------------------------------------------------

    def _show_toast(self, level: str, message: str) -> None:
        Toast(self, message, level)


# --------------------------------------------------------------------------- #
# Settings dialog
# --------------------------------------------------------------------------- #
class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None, state: "AppState") -> None:
        super().__init__(parent)
        self.state = state
        self.setWindowTitle(t("settings_title"))
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        self.values = config_store.load()

        # Renaming section
        gb = QGroupBox(t("settings_section_renaming"))
        form = QFormLayout(gb)
        self.idle = self._spin(0, 86400, 30, self.values.idle_seconds)
        form.addRow(t("settings_idle_seconds"), self.idle)
        self.min_msgs = self._spin(0, 50, 1, self.values.min_user_messages)
        form.addRow(t("settings_min_user_messages"), self.min_msgs)
        self.max_age = self._spin(1, 3650, 1, self.values.max_age_days)
        form.addRow(t("settings_max_age_days"), self.max_age)
        layout.addWidget(gb)

        # Daemon section
        gb2 = QGroupBox(t("settings_section_daemon"))
        form2 = QFormLayout(gb2)
        self.poll = self._spin(5, 3600, 10, self.values.poll_seconds)
        form2.addRow(t("settings_poll_seconds"), self.poll)
        self.batch = self._spin(0, 500, 5, self.values.batch_size)
        form2.addRow(t("settings_batch_size"), self.batch)
        self.dry = QCheckBox(t("settings_dry_run"))
        self.dry.setChecked(self.values.dry_run)
        form2.addRow(self.dry)
        layout.addWidget(gb2)

        # Namer section
        gb3 = QGroupBox(t("settings_section_namer"))
        form3 = QFormLayout(gb3)
        self.namer = QComboBox()
        self.namer.addItems(config_store.ALL_NAMERS)
        self.namer.setCurrentText(self.values.namer)
        form3.addRow(t("settings_namer"), self.namer)
        layout.addWidget(gb3)

        # Tools section
        gb4 = QGroupBox(t("settings_section_tools"))
        v = QVBoxLayout(gb4)
        self.tool_boxes: dict[str, QCheckBox] = {}
        for tool in config_store.ALL_TOOLS:
            cb = QCheckBox(tool)
            cb.setChecked(tool in self.values.tools)
            self.tool_boxes[tool] = cb
            v.addWidget(cb)
        layout.addWidget(gb4)

        # Save / cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Save).setText(t("settings_save"))
        layout.addWidget(buttons)

    @staticmethod
    def _spin(lo: int, hi: int, step: int, value: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setSingleStep(step)
        s.setValue(value)
        return s

    def _save(self) -> None:
        v = config_store.Values(
            idle_seconds=self.idle.value(),
            poll_seconds=self.poll.value(),
            batch_size=self.batch.value(),
            max_age_days=self.max_age.value(),
            min_user_messages=self.min_msgs.value(),
            namer=self.namer.currentText(),
            dry_run=self.dry.isChecked(),
            tools=[name for name, cb in self.tool_boxes.items() if cb.isChecked()],
        )
        try:
            config_store.save(v)
        except OSError as e:
            QMessageBox.critical(self, "Retitle", str(e))
            return
        self.state.toast("success", t("settings_saved"))
        self.state.refresh_status()
        self.accept()


# --------------------------------------------------------------------------- #
# Central state coordinator
# --------------------------------------------------------------------------- #
class AppState(QObject):
    status_changed = Signal(object)            # dict
    sessions_changed = Signal(object, object)  # (list, stats|None)
    toast_requested = Signal(str, str)         # (level, message)

    def __init__(self, cli: RetitleCLI | None) -> None:
        super().__init__()
        self.cli = cli
        self.daemon = DaemonControl(cli.executable if cli else "")
        self.status: dict | None = None
        self.sessions: list[dict] = []
        self.stats: dict | None = None
        self._titles_seen: dict[str, str] = {}
        self._dashboard: DashboardWindow | None = None
        self._workers: list[QThread] = []

        # Periodic status poll (5 min). Sessions are refreshed on demand only,
        # because the list/stats commands hit TCC-protected paths.
        self._status_timer = QTimer()
        self._status_timer.setInterval(5 * 60 * 1000)
        self._status_timer.timeout.connect(self.refresh_status)
        self._status_timer.start()

        QTimer.singleShot(0, self.refresh_status)

    # ----- ops --------------------------------------------------------

    def _spawn(self, fn: Callable[[], object], on_done: Callable[[object], None],
               on_fail: Callable[[str], None] | None = None) -> None:
        if not self.cli:
            self.toast("error", t("cli_not_found"))
            return
        w = _Worker(fn)
        w.done.connect(on_done)
        if on_fail:
            w.failed.connect(on_fail)
        else:
            w.failed.connect(lambda msg: self.toast("error", msg))
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w)
        w.start()

    def refresh_status(self) -> None:
        if not self.cli:
            return
        self._spawn(self.cli.status, self._on_status)

    def refresh_sessions(self) -> None:
        if not self.cli:
            return
        self._spawn(
            lambda: (self.cli.list_sessions(limit=500), self._safe_stats()),
            self._on_sessions,
        )

    def _safe_stats(self) -> dict | None:
        try:
            return self.cli.stats() if self.cli else None
        except RetitleError:
            return None

    def _on_status(self, status: object) -> None:
        if not isinstance(status, dict):
            return
        self.status = status
        self.status_changed.emit(status)

    def _on_sessions(self, result: object) -> None:
        if not (isinstance(result, tuple) and len(result) == 2):
            return
        sessions, stats = result
        if isinstance(sessions, list):
            self._detect_renames(sessions)
            self.sessions = sessions
            self.stats = stats if isinstance(stats, dict) else None
            self.sessions_changed.emit(self.sessions, self.stats)

    def _detect_renames(self, sessions: list[dict]) -> None:
        new_titles: dict[str, str] = {}
        for s in sessions:
            key = f"{s.get('tool')}|{s.get('id')}"
            title = s.get("title") or ""
            new_titles[key] = title
            old = self._titles_seen.get(key, "")
            if old and title and old != title:
                self.toast(
                    "success",
                    t("toast_renamed", title),
                )
        self._titles_seen = new_titles

    # ----- actions --------------------------------------------------

    def pause_daemon(self) -> None:
        self.daemon.pause(self.status)
        self.refresh_status()
        self.toast("info", t("toast_daemon_paused"))

    def resume_daemon(self) -> None:
        self.daemon.resume(self.status)
        self.refresh_status()
        self.toast("success", t("toast_daemon_resumed"))

    def rename_now(self, session: dict) -> None:
        if not self.cli:
            self.toast("error", t("cli_not_found"))
            return
        sid = session.get("id")
        tool = session.get("tool")
        if not sid:
            return

        def do_rename() -> None:
            self.cli.rename_session(sid, tool)

        def done(_unused: object) -> None:
            self.toast("success", t("toast_renamed", session.get("proposed_title") or sid))
            self.refresh_sessions()

        self._spawn(do_rename, done)

    def rename_historical(self, dry_run: bool = False) -> None:
        """User-initiated full historical pass — sends every backlog session
        through the namer. Runs on a worker thread; surface progress via
        toasts."""
        if not self.cli:
            self.toast("error", t("cli_not_found"))
            return

        self.toast("info", t("toast_historical_started"))

        def do_run() -> str:
            return self.cli.rename_historical(dry_run=dry_run)

        def done(result: object) -> None:
            # Last non-empty line of stderr is the CLI summary
            # ("done — renamed N of M candidate(s)").
            text = result if isinstance(result, str) else ""
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            summary = lines[-1] if lines else t("toast_historical_done")
            self.toast("success", summary)
            self.refresh_sessions()

        self._spawn(do_run, done)

    def open_dashboard(self) -> None:
        if not self._dashboard:
            self._dashboard = DashboardWindow(self)
        self._dashboard.show()
        self._dashboard.raise_()
        self._dashboard.activateWindow()
        # First open triggers a session refresh.
        self.refresh_sessions()

    def open_settings(self) -> None:
        parent = self._dashboard if self._dashboard else None
        dlg = SettingsDialog(parent, self)
        dlg.exec()

    def open_log(self) -> None:
        log = self.status.get("log_path") if self.status else None
        if log:
            QGuiApplication.instance().processEvents()
            self._open_externally(log)

    def _open_externally(self, path: str) -> None:
        if sys.platform == "win32":
            import os
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", path])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", path])

    def toast(self, level: str, message: str) -> None:
        self.toast_requested.emit(level, message)
        # Also surface as a tray balloon when no dashboard is visible.
        if not (self._dashboard and self._dashboard.isVisible()):
            tray = QApplication.instance().property("tray")
            if isinstance(tray, QSystemTrayIcon):
                icon_kind = {
                    "info": QSystemTrayIcon.Information,
                    "success": QSystemTrayIcon.Information,
                    "warning": QSystemTrayIcon.Warning,
                    "error": QSystemTrayIcon.Critical,
                }.get(level, QSystemTrayIcon.Information)
                tray.showMessage("Retitle", message, icon_kind, 3500)


# --------------------------------------------------------------------------- #
# Tray icon
# --------------------------------------------------------------------------- #
class TrayIcon(QSystemTrayIcon):
    def __init__(self, app: QApplication, state: AppState) -> None:
        super().__init__(_make_tag_icon(), app)
        self.app = app
        self.state = state
        self.setToolTip("Retitle")

        menu = QMenu()
        self.status_action = QAction(t("loading"))
        self.status_action.setEnabled(False)
        menu.addAction(self.status_action)
        menu.addSeparator()
        menu.addAction(t("open_dashboard"), state.open_dashboard)
        menu.addAction(t("settings"), state.open_settings)
        menu.addSeparator()
        self.pause_action = QAction(t("pause_daemon"))
        self.pause_action.triggered.connect(self._toggle_daemon)
        menu.addAction(self.pause_action)
        menu.addAction(t("show_log"), state.open_log)
        menu.addSeparator()
        menu.addAction(t("quit"), app.quit)
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

        state.status_changed.connect(self._on_status_changed)

    def _toggle_daemon(self) -> None:
        running = "running" in (
            self.state.status or {}).get("daemon", {}).get("status_line", "")
        if running:
            self.state.pause_daemon()
        else:
            self.state.resume_daemon()

    def _on_status_changed(self, status: dict) -> None:
        running = "running" in status.get("daemon", {}).get("status_line", "")
        installed = "not installed" not in status.get("daemon", {}).get("status_line", "")
        if running:
            self.status_action.setText("● " + t("running"))
            self.pause_action.setText(t("pause_daemon"))
        elif installed:
            self.status_action.setText("● " + t("paused"))
            self.pause_action.setText(t("resume_daemon"))
        else:
            self.status_action.setText("○ " + t("no_daemon"))
            self.pause_action.setText(t("resume_daemon"))

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.state.open_dashboard()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Retitle")
    app.setQuitOnLastWindowClosed(False)  # tray stays even if dashboard closed

    binary = find_retitle()
    if not binary:
        QMessageBox.critical(
            None, "Retitle",
            t("cli_not_found"),
        )
        return 1
    cli = RetitleCLI(binary)
    state = AppState(cli)
    tray = TrayIcon(app, state)
    tray.show()
    app.setProperty("tray", tray)

    return app.exec()
