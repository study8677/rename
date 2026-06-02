import SwiftUI

/// Compact menu-bar popover. We only display human-friendly summaries —
/// no raw CLI output, no stderr.
struct MenuBarView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var toasts: ToastCenter
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            statusHeader
            Divider()
            recentSection
            Divider()
            controls
        }
        .padding(14)
        .frame(width: 340)
        .onAppear { Task { await state.refreshStatusOnly() } }
    }

    // MARK: - status header ------------------------------------------------

    private var statusHeader: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: statusIcon)
                .foregroundStyle(statusColor)
                .font(.title2)
                .frame(width: 28, height: 28)
            VStack(alignment: .leading, spacing: 2) {
                Text(statusHeadline).font(.headline)
                Text(statusSubline).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            if let v = state.status?.version {
                Text(verbatim: "v\(v)").font(.caption2).foregroundStyle(.secondary)
            }
        }
    }

    private var statusIcon: String {
        if state.cli == nil { return "exclamationmark.triangle.fill" }
        guard let st = state.status else { return "ellipsis.circle" }
        if st.daemon.isRunning { return "checkmark.circle.fill" }
        if st.daemon.isInstalled { return "pause.circle.fill" }
        return "circle.dashed"
    }

    private var statusColor: Color {
        if state.cli == nil { return .orange }
        guard let st = state.status else { return .secondary }
        if st.daemon.isRunning { return .green }
        if st.daemon.isInstalled { return .orange }
        return .secondary
    }

    private var statusHeadline: LocalizedStringKey {
        if state.cli == nil { return "menubar_cli_not_found" }
        guard let st = state.status else { return "menubar_loading" }
        if st.daemon.isRunning { return "menubar_running" }
        if st.daemon.isInstalled { return "menubar_paused" }
        return "menubar_no_daemon"
    }

    private var statusSubline: LocalizedStringKey {
        guard let st = state.status else { return "menubar_loading_sub" }
        if st.daemon.isRunning { return "menubar_running_sub" }
        if st.daemon.isInstalled { return "menubar_paused_sub" }
        return "menubar_no_daemon_sub"
    }

    // MARK: - recent renames ----------------------------------------------

    @ViewBuilder
    private var recentSection: some View {
        Text(LocalizedStringKey("menubar_recent_renames"))
            .font(.caption).fontWeight(.medium).foregroundStyle(.secondary)
        if state.recentRenames.isEmpty {
            VStack(alignment: .leading, spacing: 4) {
                Text(LocalizedStringKey("menubar_no_recent"))
                    .foregroundStyle(.secondary).font(.callout)
                Text(LocalizedStringKey("menubar_no_recent_sub"))
                    .foregroundStyle(.secondary).font(.caption)
            }
        } else {
            ForEach(state.recentRenames.prefix(5)) { rename in
                VStack(alignment: .leading, spacing: 2) {
                    Text(verbatim: rename.newTitle)
                        .font(.callout).lineLimit(1)
                    HStack(spacing: 4) {
                        ToolBadge(tool: rename.tool, mini: true)
                        Text(verbatim: rename.oldTitle)
                            .strikethrough().font(.caption)
                            .foregroundStyle(.secondary).lineLimit(1)
                    }
                }
            }
        }
    }

    // MARK: - controls -----------------------------------------------------

    @ViewBuilder
    private var controls: some View {
        Button {
            state.dashboardOpen = true
            openWindow(id: "dashboard")
            NSApp.activate(ignoringOtherApps: true)
        } label: {
            Label(LocalizedStringKey("menubar_open_dashboard"), systemImage: "rectangle.stack")
        }
        .keyboardShortcut("d")

        Button {
            state.settingsOpen = true
            openWindow(id: "settings")
            NSApp.activate(ignoringOtherApps: true)
        } label: {
            Label(LocalizedStringKey("menubar_settings"), systemImage: "gearshape")
        }
        .keyboardShortcut(",")

        if let st = state.status {
            if st.daemon.isRunning {
                Button {
                    state.pauseDaemon()
                    toasts.info(NSLocalizedString("toast_daemon_paused", comment: ""))
                } label: {
                    Label(LocalizedStringKey("menubar_pause_daemon"),
                          systemImage: "pause.circle")
                }
            } else if st.daemon.isInstalled {
                Button {
                    state.resumeDaemon()
                    toasts.success(NSLocalizedString("toast_daemon_resumed", comment: ""))
                } label: {
                    Label(LocalizedStringKey("menubar_resume_daemon"),
                          systemImage: "play.circle")
                }
            }
        }

        Divider()
        Button {
            if let log = state.status?.logPath { state.openExternally(log) }
        } label: {
            Label(LocalizedStringKey("menubar_show_log"), systemImage: "doc.text")
        }
        .disabled(state.status?.logPath == nil)

        Button(role: .destructive) {
            NSApp.terminate(nil)
        } label: {
            Label(LocalizedStringKey("menubar_quit"), systemImage: "power")
        }
        .keyboardShortcut("q")
    }
}

/// Brand-coloured pill badge for one of the four tool adapters.
struct ToolBadge: View {
    let tool: String
    var mini: Bool = false

    var body: some View {
        HStack(spacing: 3) {
            Image(systemName: icon)
                .font(mini ? .caption2 : .caption)
            if !mini {
                Text(verbatim: label).font(.caption)
            }
        }
        .padding(.horizontal, mini ? 4 : 8)
        .padding(.vertical, mini ? 1 : 3)
        .background(
            Capsule().fill(color.opacity(0.18))
        )
        .foregroundStyle(color)
    }

    var label: String {
        switch tool {
        case "claude-code": return "Claude"
        case "codex":       return "Codex"
        case "cursor":      return "Cursor"
        case "antigravity": return "Antigr."
        default:            return tool
        }
    }

    var icon: String {
        switch tool {
        case "claude-code": return "c.circle"
        case "codex":       return "chevron.left.forwardslash.chevron.right"
        case "cursor":      return "cursorarrow.rays"
        case "antigravity": return "atom"
        default:            return "doc"
        }
    }

    var color: Color {
        switch tool {
        case "claude-code": return Color(red: 0.88, green: 0.49, blue: 0.20)
        case "codex":       return Color(red: 0.10, green: 0.62, blue: 0.45)
        case "cursor":      return Color(red: 0.42, green: 0.40, blue: 0.92)
        case "antigravity": return Color(red: 0.20, green: 0.50, blue: 0.92)
        default:            return .secondary
        }
    }
}
