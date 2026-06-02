import SwiftUI

/// Main window: stats header, tool filter, search, session table, footer.
struct DashboardView: View {
    @EnvironmentObject var state: AppState
    @State private var selectedTool: String? = nil    // nil = all tools
    @State private var searchText = ""
    @State private var renamingSessionId: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            statsHeader
            Divider()
            filterBar
            Divider()
            sessionTable
            Divider()
            footer
        }
        .frame(minWidth: 720, minHeight: 480)
        .onAppear {
            state.dashboardOpen = true
            Task { await state.refresh() }
        }
        .onDisappear { state.dashboardOpen = false }
    }

    // MARK: - Stats header --------------------------------------------------

    private var statsHeader: some View {
        HStack(spacing: 16) {
            statCard(LocalizedStringKey("dash_tracked"), value: "\(state.status?.tracked ?? 0)")
            statCard(
                LocalizedStringKey("dash_total_sessions"),
                value: "\(state.stats?.total.sessions ?? state.sessions.count)"
            )
            statCard(
                LocalizedStringKey("dash_stale"),
                value: "\(state.stats?.total.stale ?? 0)"
            )
            statCard(
                LocalizedStringKey("dash_renamed_lifetime"),
                value: "\(state.stats?.total.renamed ?? 0)"
            )
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                if let st = state.status {
                    HStack(spacing: 6) {
                        Circle()
                            .fill(st.daemon.isRunning ? Color.green : Color.orange)
                            .frame(width: 8, height: 8)
                        Text(st.daemon.isRunning
                             ? LocalizedStringKey("dash_daemon_running")
                             : LocalizedStringKey("dash_daemon_stopped"))
                            .font(.callout)
                    }
                    Text(verbatim: "namer: \(st.namerResolved)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(16)
    }

    @ViewBuilder
    private func statCard(_ title: LocalizedStringKey, value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            Text(verbatim: value).font(.title2).fontWeight(.semibold)
        }
        .padding(10)
        .background(RoundedRectangle(cornerRadius: 8).fill(.quaternary.opacity(0.5)))
    }

    // MARK: - Filter bar ----------------------------------------------------

    private var filterBar: some View {
        HStack(spacing: 10) {
            Button(action: { selectedTool = nil }) {
                Text(LocalizedStringKey("dash_filter_all"))
                    .fontWeight(selectedTool == nil ? .semibold : .regular)
            }
            .buttonStyle(.plain)
            .padding(.horizontal, 10).padding(.vertical, 4)
            .background(
                RoundedRectangle(cornerRadius: 6)
                    .fill(selectedTool == nil ? Color.accentColor.opacity(0.2) : .clear)
            )

            ForEach(state.status?.tools ?? []) { tool in
                Button(action: { selectedTool = tool.name }) {
                    HStack(spacing: 4) {
                        Text(verbatim: tool.label)
                            .fontWeight(selectedTool == tool.name ? .semibold : .regular)
                        if !tool.enabled {
                            Image(systemName: "minus.circle")
                                .foregroundStyle(.secondary)
                                .font(.caption)
                        }
                    }
                }
                .buttonStyle(.plain)
                .padding(.horizontal, 10).padding(.vertical, 4)
                .background(
                    RoundedRectangle(cornerRadius: 6)
                        .fill(selectedTool == tool.name ? Color.accentColor.opacity(0.2) : .clear)
                )
                .disabled(!tool.available)
                .opacity(tool.available ? 1 : 0.4)
            }

            Spacer()
            TextField(LocalizedStringKey("dash_search_placeholder"), text: $searchText)
                .textFieldStyle(.roundedBorder)
                .frame(maxWidth: 220)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
    }

    // MARK: - Session table -------------------------------------------------

    private var filteredSessions: [SessionPlan] {
        var rows = state.sessions
        if let tool = selectedTool {
            rows = rows.filter { $0.tool == tool }
        }
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

    private var sessionTable: some View {
        ScrollView {
            if filteredSessions.isEmpty {
                VStack(spacing: 8) {
                    if state.isRefreshing {
                        ProgressView()
                        Text(LocalizedStringKey("dash_loading"))
                            .foregroundStyle(.secondary)
                    } else {
                        Image(systemName: "tray").font(.largeTitle).foregroundStyle(.secondary)
                        Text(LocalizedStringKey("dash_no_sessions"))
                            .foregroundStyle(.secondary)
                    }
                }
                .frame(maxWidth: .infinity).padding(40)
            } else {
                LazyVStack(spacing: 0) {
                    ForEach(filteredSessions) { row in
                        SessionRowView(plan: row, busy: renamingSessionId == row.id) {
                            renamingSessionId = row.id
                            Task {
                                await state.renameNow(row)
                                renamingSessionId = nil
                            }
                        }
                        Divider()
                    }
                }
            }
        }
    }

    // MARK: - Footer --------------------------------------------------------

    private var footer: some View {
        HStack(spacing: 10) {
            Button {
                Task { await state.refresh() }
            } label: {
                Label(LocalizedStringKey("dash_refresh"), systemImage: "arrow.clockwise")
            }
            .disabled(state.isRefreshing)

            if let st = state.status {
                if st.daemon.isRunning {
                    Button {
                        state.pauseDaemon()
                    } label: {
                        Label(LocalizedStringKey("dash_pause_daemon"), systemImage: "pause.circle")
                    }
                } else if st.daemon.isInstalled {
                    Button {
                        state.resumeDaemon()
                    } label: {
                        Label(LocalizedStringKey("dash_resume_daemon"), systemImage: "play.circle")
                    }
                }

                Button {
                    state.openExternally(st.configPath)
                } label: {
                    Label(LocalizedStringKey("dash_open_config"), systemImage: "gearshape")
                }
                Button {
                    state.openExternally(st.logPath)
                } label: {
                    Label(LocalizedStringKey("dash_show_log"), systemImage: "doc.text")
                }
            }
            Spacer()
            if state.isRefreshing {
                ProgressView().controlSize(.small)
            }
            if let err = state.lastError, !err.isEmpty {
                Text(verbatim: err)
                    .font(.caption).foregroundStyle(.red).lineLimit(1).truncationMode(.tail)
                    .help(err)
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
    let onRenameNow: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            iconForTool(plan.tool)
                .frame(width: 28)
                .foregroundStyle(.secondary)
            VStack(alignment: .leading, spacing: 2) {
                Text(verbatim: plan.title ?? "—")
                    .font(.body)
                    .lineLimit(1)
                if let proposed = plan.proposedTitle, plan.action == "rename" {
                    Text(verbatim: "→ \(proposed)")
                        .font(.caption)
                        .foregroundStyle(.blue)
                        .lineLimit(1)
                } else {
                    Text(verbatim: plan.reason)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }
            Spacer()
            if let cwd = plan.cwd, !cwd.isEmpty {
                Text(verbatim: shortenCwd(cwd))
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .frame(maxWidth: 180, alignment: .trailing)
                    .help(cwd)
            }
            Text(verbatim: shortIdle(plan.idleSeconds))
                .font(.caption2)
                .foregroundStyle(.secondary)
                .frame(width: 60, alignment: .trailing)

            Button(action: onRenameNow) {
                if busy {
                    ProgressView().controlSize(.small)
                } else {
                    Image(systemName: "arrow.triangle.2.circlepath")
                }
            }
            .help(Text(LocalizedStringKey("dash_rename_now_tooltip")))
            .buttonStyle(.borderless)
            .disabled(busy)
        }
        .padding(.horizontal, 16).padding(.vertical, 8)
        .contentShape(Rectangle())
    }

    private func iconForTool(_ tool: String) -> Image {
        switch tool {
        case "claude-code": return Image(systemName: "c.circle")
        case "codex":       return Image(systemName: "chevron.left.forwardslash.chevron.right")
        case "cursor":      return Image(systemName: "cursorarrow.rays")
        case "antigravity": return Image(systemName: "atom")
        default:            return Image(systemName: "doc")
        }
    }

    private func shortenCwd(_ s: String) -> String {
        var path = s
        if let r = path.range(of: "file://") { path.removeSubrange(r) }
        if let r = path.range(of: "vscode-remote://") { path.removeSubrange(r) }
        let home = NSHomeDirectory()
        if path.hasPrefix(home) {
            path = "~" + path.dropFirst(home.count)
        }
        // Show last 2 path components for orientation.
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
