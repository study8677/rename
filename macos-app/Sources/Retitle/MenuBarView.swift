import SwiftUI

/// Contents of the MenuBarExtra popover. Lightweight by design: a status
/// glance, a few recent renames, and a couple of control toggles. Anything
/// richer (session list, search) belongs in the Dashboard window.
struct MenuBarView: View {
    @EnvironmentObject var state: AppState
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            header
            Divider()
            recentSection
            Divider()
            controls
        }
        .padding(12)
        .frame(width: 320)
        .onAppear { Task { await state.refresh() } }
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline, spacing: 6) {
            if let st = state.status {
                Circle()
                    .fill(st.daemon.isRunning ? Color.green : Color.orange)
                    .frame(width: 8, height: 8)
                Text(st.daemon.isRunning
                     ? LocalizedStringKey("menubar_running")
                     : LocalizedStringKey("menubar_paused"))
                    .font(.headline)
                Spacer()
                Text(verbatim: "v\(st.version)")
                    .foregroundStyle(.secondary)
                    .font(.caption)
            } else if state.cli == nil {
                Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
                Text(LocalizedStringKey("menubar_cli_not_found"))
                    .font(.headline)
            } else {
                ProgressView().controlSize(.small)
                Text(LocalizedStringKey("menubar_loading")).font(.headline)
            }
        }
    }

    @ViewBuilder
    private var recentSection: some View {
        Text(LocalizedStringKey("menubar_recent_renames"))
            .font(.caption).foregroundStyle(.secondary)
        if state.recentRenames.isEmpty {
            Text(LocalizedStringKey("menubar_no_recent"))
                .foregroundStyle(.secondary)
                .font(.callout)
        } else {
            ForEach(state.recentRenames.prefix(5)) { rename in
                VStack(alignment: .leading, spacing: 2) {
                    Text(verbatim: rename.newTitle).font(.callout).lineLimit(1)
                    Text(verbatim: "← \(rename.oldTitle)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }
        }
    }

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

        if let st = state.status {
            if st.daemon.isRunning {
                Button {
                    state.pauseDaemon()
                } label: {
                    Label(LocalizedStringKey("menubar_pause_daemon"), systemImage: "pause.circle")
                }
            } else if st.daemon.isInstalled {
                Button {
                    state.resumeDaemon()
                } label: {
                    Label(LocalizedStringKey("menubar_resume_daemon"), systemImage: "play.circle")
                }
            }
            Button {
                Task { await state.refresh() }
            } label: {
                Label(LocalizedStringKey("menubar_refresh_now"), systemImage: "arrow.clockwise")
            }
            .keyboardShortcut("r")
        }

        Divider()
        Button {
            if let log = state.status?.logPath {
                state.openExternally(log)
            }
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
