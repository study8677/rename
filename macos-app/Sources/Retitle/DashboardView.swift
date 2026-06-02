import SwiftUI

/// Main dashboard window. Built to be friendly at a glance: card-style stats,
/// brand-coloured tool filters, hover effects, clear rename diff, and toast
/// notifications instead of raw stderr.
struct DashboardView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var toasts: ToastCenter
    @Environment(\.openWindow) private var openWindow
    @State private var selectedTool: String? = nil
    @State private var searchText = ""
    @State private var renamingSessionId: String? = nil
    @State private var hoveredId: String? = nil

    var body: some View {
        VStack(spacing: 0) {
            statsHeader
            Divider()
            filterBar
            sessionTable
            Divider()
            footer
        }
        .frame(minWidth: 760, minHeight: 520)
        .background(Color(NSColor.windowBackgroundColor))
        .onAppear {
            state.dashboardOpen = true
            Task { await state.refreshSessions() }
        }
        .onDisappear { state.dashboardOpen = false }
        .toastOverlay(toasts)
    }

    // MARK: - stats header -------------------------------------------------

    private var statsHeader: some View {
        VStack(spacing: 0) {
            HStack(alignment: .center, spacing: 12) {
                statCard(
                    title: LocalizedStringKey("dash_tracked"),
                    value: "\(state.status?.tracked ?? 0)",
                    icon: "tray.full",
                    tint: .blue
                )
                statCard(
                    title: LocalizedStringKey("dash_total_sessions"),
                    value: "\(state.stats?.total.sessions ?? state.sessions.count)",
                    icon: "doc.on.doc",
                    tint: .purple
                )
                statCard(
                    title: LocalizedStringKey("dash_stale"),
                    value: "\(state.stats?.total.stale ?? 0)",
                    icon: "clock.badge",
                    tint: .orange
                )
                statCard(
                    title: LocalizedStringKey("dash_renamed_lifetime"),
                    value: "\(state.stats?.total.renamed ?? 0)",
                    icon: "sparkles",
                    tint: .green
                )
                Spacer()
                statusPill
            }
            .padding(.horizontal, 18).padding(.vertical, 16)
        }
    }

    @ViewBuilder
    private func statCard(
        title: LocalizedStringKey, value: String, icon: String, tint: Color
    ) -> some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 8)
                    .fill(tint.opacity(0.18))
                    .frame(width: 36, height: 36)
                Image(systemName: icon).foregroundStyle(tint)
            }
            VStack(alignment: .leading, spacing: 0) {
                Text(verbatim: value).font(.title2).fontWeight(.semibold).monospacedDigit()
                Text(title).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
        }
        .padding(10)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(.quaternary.opacity(0.4))
        )
    }

    @ViewBuilder
    private var statusPill: some View {
        if let st = state.status {
            HStack(spacing: 8) {
                Circle()
                    .fill(st.daemon.isRunning ? Color.green : Color.orange)
                    .frame(width: 8, height: 8)
                VStack(alignment: .leading, spacing: 1) {
                    Text(st.daemon.isRunning
                         ? LocalizedStringKey("dash_daemon_running")
                         : LocalizedStringKey("dash_daemon_stopped"))
                        .font(.callout).fontWeight(.medium)
                    Text(verbatim: "namer: \(st.namerResolved)")
                        .font(.caption2).foregroundStyle(.secondary)
                }
            }
            .padding(.horizontal, 12).padding(.vertical, 8)
            .background(
                Capsule().fill(.quaternary.opacity(0.4))
            )
        }
    }

    // MARK: - filter bar --------------------------------------------------

    private var filterBar: some View {
        HStack(spacing: 8) {
            chip(label: nil, selected: selectedTool == nil) {
                Text(LocalizedStringKey("dash_filter_all"))
            } onTap: {
                selectedTool = nil
            }

            ForEach(state.status?.tools ?? []) { tool in
                Button {
                    if tool.available { selectedTool = tool.name }
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: ToolBadge(tool: tool.name).icon)
                            .font(.caption)
                        Text(verbatim: tool.label).font(.callout)
                        if !tool.enabled {
                            Image(systemName: "minus.circle")
                                .foregroundStyle(.secondary).font(.caption2)
                        }
                    }
                    .padding(.horizontal, 12).padding(.vertical, 5)
                    .background(
                        Capsule().fill(
                            selectedTool == tool.name
                            ? ToolBadge(tool: tool.name).color.opacity(0.25)
                            : Color.clear
                        )
                    )
                    .overlay(
                        Capsule().stroke(
                            selectedTool == tool.name
                            ? ToolBadge(tool: tool.name).color
                            : Color.gray.opacity(0.25),
                            lineWidth: 1
                        )
                    )
                    .foregroundStyle(tool.available ? Color.primary : Color.secondary)
                }
                .buttonStyle(.plain)
                .disabled(!tool.available)
            }

            Spacer()
            HStack(spacing: 6) {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(.secondary).font(.callout)
                TextField(LocalizedStringKey("dash_search_placeholder"), text: $searchText)
                    .textFieldStyle(.plain)
            }
            .padding(.horizontal, 10).padding(.vertical, 5)
            .background(Capsule().fill(.quaternary.opacity(0.4)))
            .frame(maxWidth: 240)
        }
        .padding(.horizontal, 18).padding(.vertical, 10)
    }

    @ViewBuilder
    private func chip<Label: View>(
        label: String?,
        selected: Bool,
        @ViewBuilder content: () -> Label,
        onTap: @escaping () -> Void
    ) -> some View {
        Button(action: onTap) {
            content()
                .font(.callout)
                .padding(.horizontal, 12).padding(.vertical, 5)
                .background(
                    Capsule().fill(selected ? Color.accentColor.opacity(0.18) : Color.clear)
                )
                .overlay(
                    Capsule().stroke(
                        selected ? Color.accentColor : Color.gray.opacity(0.25),
                        lineWidth: 1
                    )
                )
        }
        .buttonStyle(.plain)
    }

    // MARK: - session table -----------------------------------------------

    private var filteredSessions: [SessionPlan] {
        var rows = state.sessions
        if let tool = selectedTool { rows = rows.filter { $0.tool == tool } }
        let q = searchText.trimmingCharacters(in: .whitespaces).lowercased()
        if !q.isEmpty {
            rows = rows.filter {
                ($0.title?.lowercased().contains(q) ?? false)
                || ($0.proposedTitle?.lowercased().contains(q) ?? false)
                || ($0.cwd?.lowercased().contains(q) ?? false)
            }
        }
        return rows
    }

    @ViewBuilder
    private var sessionTable: some View {
        if state.isRefreshing && state.sessions.isEmpty {
            loadingScreen
        } else if filteredSessions.isEmpty {
            emptyScreen
        } else {
            ScrollView {
                LazyVStack(spacing: 0) {
                    ForEach(filteredSessions) { row in
                        SessionRowView(
                            plan: row,
                            busy: renamingSessionId == row.id,
                            hovered: hoveredId == row.id,
                            onRenameNow: { renameNow(row) },
                            onHover: { isHovering in
                                hoveredId = isHovering ? row.id : nil
                            }
                        )
                        Divider().opacity(0.4)
                    }
                }
            }
        }
    }

    private var loadingScreen: some View {
        VStack(spacing: 12) {
            ProgressView().controlSize(.large)
            Text(LocalizedStringKey("dash_loading"))
                .foregroundStyle(.secondary)
            Text(LocalizedStringKey("dash_loading_sub"))
                .font(.caption).foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 60)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity).padding(40)
    }

    private var emptyScreen: some View {
        VStack(spacing: 10) {
            Image(systemName: state.sessions.isEmpty ? "questionmark.folder" : "magnifyingglass")
                .font(.system(size: 36)).foregroundStyle(.secondary)
            Text(state.sessions.isEmpty
                 ? LocalizedStringKey("dash_empty_initial")
                 : LocalizedStringKey("dash_empty_filtered"))
                .foregroundStyle(.secondary)
            if state.sessions.isEmpty {
                Button(LocalizedStringKey("dash_empty_scan_now")) {
                    Task { await state.refreshSessions() }
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity).padding(40)
    }

    private func renameNow(_ row: SessionPlan) {
        renamingSessionId = row.id
        Task {
            await state.renameNow(row)
            renamingSessionId = nil
            if state.lastError == nil {
                toasts.success(
                    String(
                        format: NSLocalizedString("toast_renamed_session_%@", comment: ""),
                        row.proposedTitle ?? row.title ?? row.id.prefix(8) + "…"
                    )
                )
            } else if let e = state.lastError {
                toasts.error(e)
                state.lastError = nil
            }
        }
    }

    // MARK: - footer ------------------------------------------------------

    private var footer: some View {
        HStack(spacing: 10) {
            Button {
                Task {
                    await state.refreshSessions()
                    if state.lastError == nil {
                        toasts.success(NSLocalizedString("toast_refreshed", comment: ""))
                    }
                }
            } label: {
                Label(LocalizedStringKey("dash_refresh"), systemImage: "arrow.clockwise")
            }
            .disabled(state.isRefreshing)

            if let st = state.status {
                if st.daemon.isRunning {
                    Button {
                        state.pauseDaemon()
                        toasts.info(NSLocalizedString("toast_daemon_paused", comment: ""))
                    } label: {
                        Label(LocalizedStringKey("dash_pause_daemon"), systemImage: "pause.circle")
                    }
                } else if st.daemon.isInstalled {
                    Button {
                        state.resumeDaemon()
                        toasts.success(NSLocalizedString("toast_daemon_resumed", comment: ""))
                    } label: {
                        Label(LocalizedStringKey("dash_resume_daemon"),
                              systemImage: "play.circle")
                    }
                }
            }

            Button {
                state.settingsOpen = true
                openWindow(id: "settings")
                NSApp.activate(ignoringOtherApps: true)
            } label: {
                Label(LocalizedStringKey("dash_settings"), systemImage: "gearshape")
            }
            .keyboardShortcut(",")

            if let log = state.status?.logPath {
                Button {
                    state.openExternally(log)
                } label: {
                    Label(LocalizedStringKey("dash_show_log"), systemImage: "doc.text")
                }
            }

            Spacer()
            if state.isRefreshing {
                HStack(spacing: 6) {
                    ProgressView().controlSize(.small)
                    Text(LocalizedStringKey("dash_scanning_status"))
                        .font(.caption).foregroundStyle(.secondary)
                }
            } else {
                Text(verbatim: "\(filteredSessions.count) / \(state.sessions.count)")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 16).padding(.vertical, 10)
    }
}

private struct SessionRowView: View {
    let plan: SessionPlan
    let busy: Bool
    let hovered: Bool
    let onRenameNow: () -> Void
    let onHover: (Bool) -> Void

    var body: some View {
        HStack(spacing: 12) {
            ToolBadge(tool: plan.tool)
                .frame(minWidth: 90, alignment: .leading)

            VStack(alignment: .leading, spacing: 3) {
                if let proposed = plan.proposedTitle, plan.action == "rename" {
                    HStack(spacing: 6) {
                        Text(verbatim: plan.title ?? "—")
                            .font(.callout)
                            .foregroundStyle(.secondary)
                            .strikethrough(color: .secondary)
                            .lineLimit(1)
                        Image(systemName: "arrow.right").foregroundStyle(.secondary).font(.caption)
                        Text(verbatim: proposed)
                            .font(.callout).fontWeight(.medium)
                            .foregroundStyle(.green)
                            .lineLimit(1)
                    }
                } else {
                    Text(verbatim: plan.title ?? "—")
                        .font(.callout)
                        .lineLimit(1)
                }
                HStack(spacing: 6) {
                    Image(systemName: "clock").font(.caption2)
                    Text(verbatim: shortIdle(plan.idleSeconds))
                    if let cwd = plan.cwd, !cwd.isEmpty {
                        Text(verbatim: "·")
                        Image(systemName: "folder").font(.caption2)
                        Text(verbatim: shortenCwd(cwd))
                            .lineLimit(1).help(cwd)
                    }
                    Text(verbatim: "·")
                    Text(verbatim: humanReason(plan.reason))
                }
                .font(.caption).foregroundStyle(.secondary)
            }

            Spacer(minLength: 8)

            Button(action: onRenameNow) {
                if busy {
                    HStack(spacing: 4) {
                        ProgressView().controlSize(.small)
                        Text(LocalizedStringKey("dash_rename_in_progress"))
                            .font(.caption)
                    }
                } else {
                    Label(
                        LocalizedStringKey("dash_rename_now_button"),
                        systemImage: "arrow.triangle.2.circlepath"
                    )
                    .labelStyle(.iconOnly)
                }
            }
            .help(Text(LocalizedStringKey("dash_rename_now_tooltip")))
            .buttonStyle(.bordered)
            .controlSize(.small)
            .disabled(busy)
            .opacity(hovered || busy ? 1 : 0.55)
        }
        .padding(.horizontal, 18).padding(.vertical, 10)
        .background(hovered ? Color.accentColor.opacity(0.06) : Color.clear)
        .contentShape(Rectangle())
        .onHover(perform: onHover)
    }

    /// Make engine "skip / not_idle / too_short / already current / rename ..."
    /// reasons readable for end users.
    private func humanReason(_ raw: String) -> String {
        if raw.hasPrefix("idle ") {
            return String(format: NSLocalizedString("reason_idle_%@", comment: ""),
                          String(raw.dropFirst("idle ".count)))
        }
        switch raw {
        case "active":           return NSLocalizedString("reason_active", comment: "")
        case "too short":        return NSLocalizedString("reason_too_short", comment: "")
        case "already current":  return NSLocalizedString("reason_already_current", comment: "")
        case "user edited":      return NSLocalizedString("reason_user_edited", comment: "")
        case "no namer":         return NSLocalizedString("reason_no_namer", comment: "")
        case "no content":       return NSLocalizedString("reason_no_content", comment: "")
        default:                 return raw
        }
    }

    private func shortenCwd(_ s: String) -> String {
        var path = s
        if path.hasPrefix("file://") { path.removeFirst("file://".count) }
        if path.hasPrefix("vscode-remote://") {
            path.removeFirst("vscode-remote://".count)
        }
        let home = NSHomeDirectory()
        if path.hasPrefix(home) { path = "~" + path.dropFirst(home.count) }
        let parts = path.split(separator: "/").suffix(2)
        return parts.isEmpty ? path : ".../" + parts.joined(separator: "/")
    }

    private func shortIdle(_ seconds: Int) -> String {
        if seconds < 60 { return "\(seconds)s" }
        if seconds < 3600 { return "\(seconds / 60)m" }
        if seconds < 86400 { return "\(seconds / 3600)h" }
        return "\(seconds / 86400)d"
    }
}
