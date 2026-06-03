import Foundation

/// Reads and writes ``~/.config/rename/config.toml``.
///
/// rename's config is a small, flat TOML with a couple of trivial subtables —
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

        // Bring-your-own-key namers (the [anthropic] / [openai] tables). An empty
        // key falls back to the matching env var, then to the offline heuristic.
        var anthropicKey: String
        var anthropicModel: String
        var openaiKey: String
        var openaiModel: String

        static let allNamers = ["auto", "heuristic", "claude", "codex", "anthropic", "openai"]
        static let allTools = ["claude-code", "codex", "cursor", "antigravity"]

        /// Built-in defaults, mirrored from the Python ApiNamer, shown as field
        /// placeholders so an empty model box clearly means "use the default".
        static let defaultAnthropicModel = "claude-haiku-4-5"
        static let defaultOpenAIModel = "gpt-4o-mini"

        /// Whether `namer` is one the user supplies an API key for.
        static func usesAPIKey(_ namer: String) -> Bool {
            namer == "anthropic" || namer == "openai"
        }
    }

    /// Default location. Honours XDG_CONFIG_HOME like rename does.
    static var path: URL {
        let xdg = ProcessInfo.processInfo.environment["XDG_CONFIG_HOME"]
        let base: URL
        if let xdg, !xdg.isEmpty {
            base = URL(fileURLWithPath: (xdg as NSString).expandingTildeInPath)
        } else {
            base = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent(".config")
        }
        return base.appendingPathComponent("rename/config.toml")
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
            tools: array(raw, "tools") ?? ["claude-code", "codex", "cursor"],
            anthropicKey: sectionString(raw, section: "anthropic", key: "api_key") ?? "",
            anthropicModel: sectionString(raw, section: "anthropic", key: "model") ?? "",
            openaiKey: sectionString(raw, section: "openai", key: "api_key") ?? "",
            openaiModel: sectionString(raw, section: "openai", key: "model") ?? ""
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
        text = setSectionString(text, section: "anthropic", key: "api_key", value: v.anthropicKey)
        text = setSectionString(text, section: "anthropic", key: "model", value: v.anthropicModel)
        text = setSectionString(text, section: "openai", key: "api_key", value: v.openaiKey)
        text = setSectionString(text, section: "openai", key: "model", value: v.openaiModel)
        try FileManager.default.createDirectory(
            at: path.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try text.write(to: path, atomically: true, encoding: .utf8)
        // The file may hold an API key — keep it readable only by the user.
        try? FileManager.default.setAttributes(
            [.posixPermissions: 0o600], ofItemAtPath: path.path
        )
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

    /// Reads a string `key = "..."` from inside a `[section]` table, scanning
    /// only the lines between the `[section]` header and the next `[header]`
    /// (or end of file). Commented lines (`# api_key = ...`) are ignored.
    private static func sectionString(_ raw: String, section: String, key: String) -> String? {
        let lines = raw.components(separatedBy: "\n")
        guard let header = lines.firstIndex(where: {
            $0.trimmingCharacters(in: .whitespaces) == "[\(section)]"
        }) else { return nil }
        var i = header + 1
        while i < lines.count {
            let stripped = lines[i].trimmingCharacters(in: .whitespaces)
            i += 1
            if stripped.hasPrefix("[") { break }       // next table — stop
            if stripped.hasPrefix("#") { continue }     // comment / example
            guard stripped.hasPrefix(key) else { continue }
            let rest = stripped.dropFirst(key.count).drop(while: { $0 == " " || $0 == "\t" })
            guard rest.hasPrefix("=") else { continue }
            // Value side: a quoted string, tolerating a trailing inline comment
            // (`api_key = "sk-…"  # note`) by closing at the first `"` after the
            // opening one rather than trusting the line to end in a quote.
            let afterEq = rest.dropFirst().drop(while: { $0 == " " || $0 == "\t" })
            guard afterEq.first == "\"" else { return nil }
            let body = afterEq.dropFirst()
            guard let close = body.firstIndex(of: "\"") else { return nil }
            return String(body[body.startIndex..<close])
        }
        return nil
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

    /// Sets a string `key = "value"` inside a `[section]` table:
    /// - replaces an existing key in the table in place,
    /// - inserts it under the header if the table exists but lacks the key,
    /// - appends a fresh `[section]` at end of file if the table is missing,
    /// - removes the key (writing nothing new) when `value` is empty, so the
    ///   namer falls back to its env var / default rather than seeing `key = ""`.
    private static func setSectionString(
        _ text: String, section: String, key: String, value: String
    ) -> String {
        let isEmpty = value.trimmingCharacters(in: .whitespaces).isEmpty
        let quoted = "\"\(value.replacingOccurrences(of: "\"", with: "\\\""))\""
        var lines = text.components(separatedBy: "\n")

        let header = lines.firstIndex(where: {
            $0.trimmingCharacters(in: .whitespaces) == "[\(section)]"
        })

        guard let h = header else {
            guard !isEmpty else { return text }   // no table and nothing to add
            var out = text
            if !out.isEmpty && !out.hasSuffix("\n") { out += "\n" }
            out += "\n[\(section)]\n\(key) = \(quoted)\n"
            return out
        }

        // The table body spans (h, next table header or end of file).
        var end = lines.count
        var j = h + 1
        while j < lines.count {
            if lines[j].trimmingCharacters(in: .whitespaces).hasPrefix("[") { end = j; break }
            j += 1
        }
        // Look for an existing, non-comment `key =` line within the body.
        var keyLine: Int? = nil
        var i = h + 1
        while i < end {
            let stripped = lines[i].trimmingCharacters(in: .whitespaces)
            if !stripped.hasPrefix("#"), stripped.hasPrefix(key) {
                let rest = stripped.dropFirst(key.count).drop(while: { $0 == " " || $0 == "\t" })
                if rest.hasPrefix("=") { keyLine = i; break }
            }
            i += 1
        }

        if let k = keyLine {
            if isEmpty { lines.remove(at: k) } else { lines[k] = "\(key) = \(quoted)" }
            return lines.joined(separator: "\n")
        }
        guard !isEmpty else { return text }
        lines.insert("\(key) = \(quoted)", at: h + 1)
        return lines.joined(separator: "\n")
    }
}
