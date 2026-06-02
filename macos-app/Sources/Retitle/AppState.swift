import Foundation
import SwiftUI

/// Single source of truth for the SwiftUI app. Holds the last-refreshed
/// status / list / stats, plus an inbox of recent renames inferred by diffing
/// the list between refreshes.
@MainActor
final class AppState: ObservableObject {
    @Published var cli: RetitleCLI?
    @Published var status: RetitleStatus?
    @Published var sessions: [SessionPlan] = []
    @Published var stats: RetitleStats?
    @Published var recentRenames: [RecentRename] = []     // most-recent-first, capped
    @Published var lastError: String?
    @Published var isRefreshing = false
    @Published var dashboardOpen = false

    private var refreshTask: Task<Void, Never>?
    private var titlesById: [String: String] = [:]        // tool|id -> title

    init() {
        self.cli = RetitleCLI.locate()
    }

    func startAutoRefresh() {
        refreshTask?.cancel()
        refreshTask = Task { [weak self] in
            while !Task.isCancelled {
                await self?.refresh()
                try? await Task.sleep(nanoseconds: 30 * 1_000_000_000)
            }
        }
    }

    func stopAutoRefresh() {
        refreshTask?.cancel()
        refreshTask = nil
    }

    /// Reload status/list/stats. Diff titles vs. the previous snapshot and
    /// emit RecentRename entries for anything whose title changed since the
    /// last refresh — that's how we surface "the daemon just renamed X".
    func refresh() async {
        guard let cli else { return }
        isRefreshing = true
        defer { isRefreshing = false }
        do {
            let s = try await Task.detached(priority: .utility) {
                try cli.status()
            }.value
            self.status = s
            self.lastError = nil
        } catch {
            self.lastError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            return
        }
        do {
            let list = try await Task.detached(priority: .utility) {
                try cli.list(limit: 500)
            }.value
            detectRenames(in: list)
            self.sessions = list
        } catch {
            self.lastError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
        if dashboardOpen {
            do {
                self.stats = try await Task.detached(priority: .utility) {
                    try cli.stats()
                }.value
            } catch {
                // stats failure is non-critical; surface but don't clobber the list
                self.lastError = (error as? LocalizedError)?.errorDescription
                    ?? error.localizedDescription
            }
        }
    }

    private func detectRenames(in fresh: [SessionPlan]) {
        var newTitles: [String: String] = [:]
        for s in fresh {
            let key = "\(s.tool)|\(s.id)"
            newTitles[key] = s.title ?? ""
            if let old = titlesById[key], old != (s.title ?? ""), !old.isEmpty, !(s.title ?? "").isEmpty {
                recentRenames.insert(
                    RecentRename(
                        tool: s.tool,
                        sessionId: s.id,
                        oldTitle: old,
                        newTitle: s.title ?? "",
                        at: Date()
                    ),
                    at: 0
                )
            }
        }
        titlesById = newTitles
        if recentRenames.count > 50 { recentRenames = Array(recentRenames.prefix(50)) }
    }

    // MARK: - Actions -------------------------------------------------------

    func pauseDaemon() {
        do {
            try LaunchctlBridge.unload()
        } catch {
            lastError = error.localizedDescription
        }
        Task { await refresh() }
    }

    func resumeDaemon() {
        do {
            try LaunchctlBridge.load()
        } catch {
            lastError = error.localizedDescription
        }
        Task { await refresh() }
    }

    func renameNow(_ session: SessionPlan) async {
        guard let cli else { return }
        do {
            _ = try await Task.detached(priority: .userInitiated) {
                try cli.renameSession(id: session.id, tool: session.tool)
            }.value
        } catch {
            lastError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
        await refresh()
    }

    func openInFinder(_ path: String) {
        let url = URL(fileURLWithPath: (path as NSString).expandingTildeInPath)
        NSWorkspace.shared.activateFileViewerSelecting([url])
    }

    func openExternally(_ path: String) {
        let url = URL(fileURLWithPath: (path as NSString).expandingTildeInPath)
        NSWorkspace.shared.open(url)
    }
}

struct RecentRename: Identifiable, Hashable {
    let id = UUID()
    let tool: String
    let sessionId: String
    let oldTitle: String
    let newTitle: String
    let at: Date
}
