import Foundation

/// Reads and writes ``~/.config/retitle/config.toml``.
///
/// retitle's config is a small, flat TOML with a couple of trivial subtables —
/// not worth bringing in a full TOML parser. We just regex-replace the keys
/// we care about while preserving comments and ordering. New keys are added
/// at the end before the first ``[section]`` header (or at end of file).
struct ConfigStore {
    /// Subset of the config the GUI exposes for editing.
    struct Values: Equatable {
        var idleSeconds: Int
        var pollSeconds: Int
        var batchSize: Int
        var maxAgeDays: Int
        var minUserMessages: Int
        var namer: String          // "auto" | "heuristic" | "claude" | "codex" | "anthropic" | "openai"
        var dryRun: Bool
        var tools: [String]        // "claude-code" | "codex" | "cursor" | "antigravity"

        static let allNamers = ["auto", "heuristic", "claude", "codex", "anthropic", "openai"]
        static let allTools = ["claude-code", "codex", "cursor", "antigravity"]
    }

    /// Default location. Honours XDG_CONFIG_HOME like retitle does.
    static var path: URL {
        let xdg = ProcessInfo.processInfo.environment["XDG_CONFIG_HOME"]
        let base: URL
        if let xdg, !xdg.isEmpty {
            base = URL(fileURLWithPath: (xdg as NSString).expandingTildeInPath)
        } else {
            base = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent(".config")
        }
        return base.appendingPathComponent("retitle/config.toml")
    }

    static func load() -> Values? {
        guard let raw = try? String(contentsOf: path, encoding: .utf8) else { return nil }
        return Values(
            idleSeconds: int(raw, "idle_seconds") ?? 300,
            pollSeconds: int(raw, "poll_seconds") ?? 60,
            batchSize: int(raw, "batch_size") ?? 25,
            maxAgeDays: int(raw, "max_age_days") ?? 7,
            minUserMessages: int(raw, "min_user_messages") ?? 1,
            namer: string(raw, "namer") ?? "auto",
            dryRun: bool(raw, "dry_run") ?? false,
            tools: array(raw, "tools") ?? ["claude-code", "codex", "cursor"]
        )
    }

    static func save(_ v: Values) throws {
        var text = (try? String(contentsOf: path, encoding: .utf8)) ?? ""
        text = setInt(text, key: "idle_seconds", value: v.idleSeconds)
        text = setInt(text, key: "poll_seconds", value: v.pollSeconds)
        text = setInt(text, key: "batch_size", value: v.batchSize)
        text = setInt(text, key: "max_age_days", value: v.maxAgeDays)
        text = setInt(text, key: "min_user_messages", value: v.minUserMessages)
        text = setString(text, key: "namer", value: v.namer)
        text = setBool(text, key: "dry_run", value: v.dryRun)
        text = setArray(text, key: "tools", values: v.tools)
        try FileManager.default.createDirectory(
            at: path.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try text.write(to: path, atomically: true, encoding: .utf8)
    }

    // MARK: - Readers -------------------------------------------------------

    private static func int(_ raw: String, _ key: String) -> Int? {
        guard let m = match(raw, key: key) else { return nil }
        return Int(m.trimmingCharacters(in: .whitespaces))
    }

    private static func bool(_ raw: String, _ key: String) -> Bool? {
        guard let m = match(raw, key: key) else { return nil }
        let v = m.trimmingCharacters(in: .whitespaces).lowercased()
        if v == "true" { return true }
        if v == "false" { return false }
        return nil
    }

    private static func string(_ raw: String, _ key: String) -> String? {
        guard let m = match(raw, key: key) else { return nil }
        let trimmed = m.trimmingCharacters(in: .whitespaces)
        guard trimmed.hasPrefix("\""), trimmed.hasSuffix("\""), trimmed.count >= 2 else {
            return nil
        }
        return String(trimmed.dropFirst().dropLast())
    }

    private static func array(_ raw: String, _ key: String) -> [String]? {
        guard let m = match(raw, key: key) else { return nil }
        let trimmed = m.trimmingCharacters(in: .whitespaces)
        guard trimmed.hasPrefix("["), trimmed.hasSuffix("]") else { return nil }
        let body = trimmed.dropFirst().dropLast()
        return body.split(separator: ",").compactMap { piece -> String? in
            let t = piece.trimmingCharacters(in: .whitespaces)
            guard t.hasPrefix("\""), t.hasSuffix("\""), t.count >= 2 else { return nil }
            return String(t.dropFirst().dropLast())
        }
    }

    /// Returns the value-side of the first matching `key = <value>` line
    /// at top level (ignoring lines after the first `[section]` header).
    private static func match(_ raw: String, key: String) -> String? {
        let topLevel = raw.components(separatedBy: "\n").prefix(while: { line in
            !line.trimmingCharacters(in: .whitespaces).hasPrefix("[")
        })
        let prefix = "\(key)"
        for line in topLevel {
            let stripped = line.trimmingCharacters(in: .whitespaces)
            if stripped.hasPrefix("#") { continue }
            guard stripped.hasPrefix(prefix) else { continue }
            // require what follows to be optional whitespace then '='
            let after = stripped.dropFirst(prefix.count)
            let rest = after.drop(while: { $0 == " " || $0 == "\t" })
            guard rest.hasPrefix("=") else { continue }
            return String(rest.dropFirst())
        }
        return nil
    }

    // MARK: - Writers -------------------------------------------------------

    private static func setInt(_ text: String, key: String, value: Int) -> String {
        replaceOrAppend(text, key: key, newValue: "\(value)")
    }

    private static func setBool(_ text: String, key: String, value: Bool) -> String {
        replaceOrAppend(text, key: key, newValue: value ? "true" : "false")
    }

    private static func setString(_ text: String, key: String, value: String) -> String {
        let escaped = value.replacingOccurrences(of: "\"", with: "\\\"")
        return replaceOrAppend(text, key: key, newValue: "\"\(escaped)\"")
    }

    private static func setArray(_ text: String, key: String, values: [String]) -> String {
        let body = values.map { "\"\($0)\"" }.joined(separator: ", ")
        return replaceOrAppend(text, key: key, newValue: "[\(body)]")
    }

    /// Replace top-level `key = ...` line, or insert before the first
    /// `[section]` (or at end of file) if missing.
    private static func replaceOrAppend(_ text: String, key: String, newValue: String) -> String {
        var lines = text.components(separatedBy: "\n")
        var sectionStart: Int? = nil
        for (i, line) in lines.enumerated() {
            let stripped = line.trimmingCharacters(in: .whitespaces)
            if stripped.hasPrefix("[") {
                sectionStart = i
                break
            }
        }
        let scanEnd = sectionStart ?? lines.count
        for i in 0..<scanEnd {
            let stripped = lines[i].trimmingCharacters(in: .whitespaces)
            if stripped.hasPrefix("#") { continue }
            if stripped.hasPrefix("\(key) ") || stripped.hasPrefix("\(key)=") {
                lines[i] = "\(key) = \(newValue)"
                return lines.joined(separator: "\n")
            }
        }
        let insertAt = sectionStart ?? lines.count
        lines.insert("\(key) = \(newValue)", at: insertAt)
        return lines.joined(separator: "\n")
    }
}
