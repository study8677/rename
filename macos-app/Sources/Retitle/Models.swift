import Foundation

// JSON shapes mirroring `retitle <cmd> --json` output.

struct ToolInfo: Codable, Identifiable, Hashable {
    let name: String
    let label: String
    let available: Bool
    let enabled: Bool
    var id: String { name }
}

struct DaemonInfo: Codable, Hashable {
    let statusLine: String

    enum CodingKeys: String, CodingKey {
        case statusLine = "status_line"
    }

    var isRunning: Bool { statusLine.contains("running") }
    var isInstalled: Bool { !statusLine.contains("not installed") }
}

struct RetitleStatus: Codable, Hashable {
    let version: String
    let configPath: String
    let configExists: Bool
    let statePath: String
    let tracked: Int
    let baselineTs: Double?
    let logPath: String
    let namer: String
    let namerResolved: String
    let idleSeconds: Int
    let pollSeconds: Int
    let maxAgeDays: Int
    let minUserMessages: Int
    let batchSize: Int
    let dryRun: Bool
    let daemon: DaemonInfo
    let tools: [ToolInfo]

    enum CodingKeys: String, CodingKey {
        case version
        case configPath = "config_path"
        case configExists = "config_exists"
        case statePath = "state_path"
        case tracked
        case baselineTs = "baseline_ts"
        case logPath = "log_path"
        case namer
        case namerResolved = "namer_resolved"
        case idleSeconds = "idle_seconds"
        case pollSeconds = "poll_seconds"
        case maxAgeDays = "max_age_days"
        case minUserMessages = "min_user_messages"
        case batchSize = "batch_size"
        case dryRun = "dry_run"
        case daemon
        case tools
    }
}

/// One row from `retitle list --json`. Fields mirror the Python output 1:1.
struct SessionPlan: Codable, Identifiable, Hashable {
    let tool: String           // "claude-code" | "codex" | "cursor" | "antigravity"
    let id: String             // session uuid
    let title: String?
    let proposedTitle: String?
    let action: String         // "rename" | "skip"
    let reason: String
    let idleSeconds: Int
    let cwd: String?

    enum CodingKeys: String, CodingKey {
        case tool, id, title
        case proposedTitle = "proposed_title"
        case action, reason
        case idleSeconds = "idle_seconds"
        case cwd
    }
}

struct ToolStats: Codable, Identifiable, Hashable {
    let tool: String
    let label: String
    let sessions: Int
    let untitled: Int
    let stale: Int
    let renamed: Int

    var id: String { tool }
}

struct RetitleStats: Codable, Hashable {
    let scopeDays: Int?
    let tools: [ToolStats]
    let total: StatTotal
    let oldestActiveSeconds: Int?

    enum CodingKeys: String, CodingKey {
        case scopeDays = "scope_days"
        case tools, total
        case oldestActiveSeconds = "oldest_active_seconds"
    }
}

struct StatTotal: Codable, Hashable {
    let sessions: Int
    let untitled: Int
    let stale: Int
    let renamed: Int
}
