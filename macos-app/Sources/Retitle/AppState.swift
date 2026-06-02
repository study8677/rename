import Foundation
import SwiftUI

/// Single source of truth for the SwiftUI app.
///
/// We're careful about how often we call `retitle list / stats` because each
/// call walks across all of the user's session stores (~/.claude/, ~/.codex/,
/// ~/Library/Application Support/{Cursor,Antigravity}/) — most of which sit
/// behind macOS TCC. Without Full Disk Access for Retitle.app, every single
/// call triggers a permission dialog. So:
///
///   * The lightweight `status` poll runs on a 5-minute timer in the background
///     (it doesn't touch the protected stores).
///   * The heavier `list` / `stats` calls only run when the Dashboard window is
///     open and on explicit user-initiated refresh.
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
    @Published var settingsOpen = false
    @Published var showFDAOnboarding = false
    @Published var hasFullDiskAccess: Bool = false
    @Published var isRunningHistorical = false
    @Published var historicalSummary: String?

    private var statusTimer: Task<Void, Never>?
    private var titlesById: [String: String] = [:]        // tool|id -> title

    init() {
        self.cli = RetitleCLI.locate()
        self.hasFullDiskAccess = PermissionsProbe.likelyHasFullDiskAccess()
        // First launch: show onboarding unless user dismissed it.
        if !UserDefaults.standard.bool(forKey: "hasShownFDAGuide") {
            // Defer to next runloop so the view is ready when we set this.
            DispatchQueue.main.async { [weak self] in
                self?.showFDAOnboarding = true
            }
        }
    }

    func startBackgroundStatusPolling() {
        statusTimer?.cancel()
        statusTimer = Task { [weak self] in
            // Immediate status fetch on launch (fast, no TCC),
            // then every 5 minutes.
            while !Task.isCancelled {
                await self?.refreshStatusOnly()
                try? await Task.sleep(nanoseconds: 5 * 60 * 1_000_000_000)
            }
        }
    }

    func stopBackgroundStatusPolling() {
        statusTimer?.cancel()
        statusTimer = nil
    }

    /// Cheap: only `retitle status --json`. Does NOT scan session stores.
    func refreshStatusOnly() async {
        guard let cli else { return }
        do {
            let s = try await Task.detached(priority: .utility) { try cli.status() }.value
            self.status = s
            self.lastError = nil
        } catch {
            self.lastError = (error as? LocalizedError)?.errorDescription
                ?? error.localizedDescription
        }
    }

    /// Heavy: scans sessions across all stores. Costs TCC prompts the first
    /// time on each store, every time without Full Disk Access. Only called
    /// when Dashboard is visible or the user explicitly hits Refresh.
    func refreshSessions() async {
        guard let cli else { return }
        await refreshStatusOnly()
        isRefreshing = true
        defer { isRefreshing = false }
        do {
            let list = try await Task.detached(priority: .utility) {
                try cli.list(limit: 500)
            }.value
            detectRenames(in: list)
            self.sessions = list
        } catch {
            self.lastError = (error as? LocalizedError)?.errorDescription
                ?? error.localizedDescription
        }
        do {
            self.stats = try await Task.detached(priority: .utility) { try cli.stats() }.value
        } catch {
            // Stats failure is non-critical; the list table is the main view.
            // Keep the error message but don't clobber the table.
        }
    }

    private func detectRenames(in fresh: [SessionPlan]) {
        var newTitles: [String: String] = [:]
        for s in fresh {
            let key = "\(s.tool)|\(s.id)"
            newTitles[key] = s.title ?? ""
            if let old = titlesById[key], old != (s.title ?? ""),
               !old.isEmpty, !(s.title ?? "").isEmpty {
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
        do { try LaunchctlBridge.unload() } catch { lastError = error.localizedDescription }
        Task { await refreshStatusOnly() }
    }

    func resumeDaemon() {
        do { try LaunchctlBridge.load() } catch { lastError = error.localizedDescription }
        Task { await refreshStatusOnly() }
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
        await refreshSessions()
    }

    /// User-initiated full historical rename pass. Runs every backlog session
    /// through the namer. Surfaces progress as `isRunningHistorical`; callers
    /// should show a confirmation dialog before invoking.
    func renameHistorical(dryRun: Bool = false) async {
        guard let cli else { return }
        isRunningHistorical = true
        historicalSummary = nil
        defer { isRunningHistorical = false }
        do {
            let out = try await Task.detached(priority: .utility) {
                try cli.renameHistorical(dryRun: dryRun)
            }.value
            // CLI's "done — renamed N of M candidate(s)" lands on stderr.
            // Take the last non-empty line as the summary for the toast.
            let lines = out.split(whereSeparator: { $0.isNewline })
                .map { String($0).trimmingCharacters(in: .whitespaces) }
                .filter { !$0.isEmpty }
            historicalSummary = lines.last
        } catch {
            lastError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
        await refreshSessions()
    }

    func openInFinder(_ path: String) {
        let url = URL(fileURLWithPath: (path as NSString).expandingTildeInPath)
        NSWorkspace.shared.activateFileViewerSelecting([url])
    }

    func openExternally(_ path: String) {
        let url = URL(fileURLWithPath: (path as NSString).expandingTildeInPath)
        NSWorkspace.shared.open(url)
    }

    func openFullDiskAccessSettings() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles") {
            NSWorkspace.shared.open(url)
        }
    }

    func dismissFDAOnboarding(remember: Bool) {
        showFDAOnboarding = false
        if remember {
            UserDefaults.standard.set(true, forKey: "hasShownFDAGuide")
        }
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

/// Best-effort detection of Full Disk Access: try to open a file we know is
/// behind TCC. If we succeed, FDA is granted; if we get EPERM, it's not.
enum PermissionsProbe {
    static func likelyHasFullDiskAccess() -> Bool {
        // ~/Library/Mail/V10 is a classic FDA-protected location. We don't
        // need to read it — just see if opendir(2) is allowed.
        let path = ("~/Library/Mail" as NSString).expandingTildeInPath
        let fd = open(path, O_RDONLY | O_DIRECTORY)
        if fd >= 0 {
            close(fd)
            return true
        }
        return false
    }
}
