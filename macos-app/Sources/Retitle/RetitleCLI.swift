import Foundation

/// Thin wrapper around the `retitle` CLI installed elsewhere on the user's
/// machine. The Swift app is a viewer/controller — all real work happens in
/// the Python CLI we invoke here.
enum RetitleCLIError: Error, LocalizedError {
    case notFound
    case failed(stderr: String, code: Int32)
    case decodeFailed(String)

    var errorDescription: String? {
        switch self {
        case .notFound:
            return NSLocalizedString("retitle_not_found", comment: "")
        case .failed(let stderr, let code):
            let trimmed = stderr.trimmingCharacters(in: .whitespacesAndNewlines)
            return String(
                format: NSLocalizedString("retitle_command_failed_%d_%@", comment: ""),
                code, trimmed
            )
        case .decodeFailed(let msg):
            return String(format: NSLocalizedString("retitle_decode_failed_%@", comment: ""), msg)
        }
    }
}

struct RetitleCLI {
    /// Resolved path to the `retitle` executable on disk. ``nil`` means we
    /// could not find one — show an error in the menu bar.
    let executable: URL

    /// Try $PATH first, then a handful of common install locations. A `.app`
    /// bundle's PATH is restricted, so falling back to absolute paths matters.
    static func locate() -> RetitleCLI? {
        let candidates = [
            ProcessInfo.processInfo.environment["RETITLE_BIN"],
            Self.whichRetitle(),
            ("~/.local/bin/retitle" as NSString).expandingTildeInPath,
            "/opt/homebrew/bin/retitle",
            "/usr/local/bin/retitle",
            "/usr/bin/retitle",
        ]
        for raw in candidates {
            guard let raw, !raw.isEmpty else { continue }
            let url = URL(fileURLWithPath: raw)
            if FileManager.default.isExecutableFile(atPath: url.path) {
                return RetitleCLI(executable: url)
            }
        }
        return nil
    }

    private static func whichRetitle() -> String? {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/sh")
        p.arguments = ["-l", "-c", "command -v retitle"]
        let out = Pipe()
        p.standardOutput = out
        p.standardError = Pipe()
        do {
            try p.run()
            p.waitUntilExit()
        } catch {
            return nil
        }
        guard p.terminationStatus == 0 else { return nil }
        let data = out.fileHandleForReading.readDataToEndOfFile()
        let s = String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return (s?.isEmpty ?? true) ? nil : s
    }

    // MARK: - Generic runner ------------------------------------------------

    @discardableResult
    func run(_ args: [String], timeout: TimeInterval = 60) throws -> Data {
        let p = Process()
        p.executableURL = executable
        p.arguments = args
        let out = Pipe()
        let err = Pipe()
        p.standardOutput = out
        p.standardError = err
        try p.run()

        let deadline = Date().addingTimeInterval(timeout)
        while p.isRunning, Date() < deadline {
            Thread.sleep(forTimeInterval: 0.05)
        }
        if p.isRunning {
            p.terminate()
            Thread.sleep(forTimeInterval: 0.2)
            if p.isRunning { p.interrupt() }
        }
        let stdoutData = out.fileHandleForReading.readDataToEndOfFile()
        let stderrData = err.fileHandleForReading.readDataToEndOfFile()
        if p.terminationStatus != 0 {
            let stderr = String(data: stderrData, encoding: .utf8) ?? ""
            throw RetitleCLIError.failed(stderr: stderr, code: p.terminationStatus)
        }
        return stdoutData
    }

    // MARK: - Typed commands ------------------------------------------------

    func status() throws -> RetitleStatus {
        let data = try run(["status", "--json"], timeout: 30)
        return try decode(RetitleStatus.self, from: data)
    }

    func list(tool: String? = nil, limit: Int = 200) throws -> [SessionPlan] {
        var args = ["list", "--json", "--limit", String(limit)]
        if let tool { args += ["--tool", tool] }
        let data = try run(args, timeout: 120)
        return try decode([SessionPlan].self, from: data)
    }

    func stats() throws -> RetitleStats {
        let data = try run(["stats", "--json"], timeout: 60)
        return try decode(RetitleStats.self, from: data)
    }

    func search(query: String, content: Bool = false, limit: Int = 100) throws -> [SearchHit] {
        var args = ["search", query, "--json", "--limit", String(limit)]
        if content { args.append("--content") }
        let data = try run(args, timeout: 120)
        return try decode([SearchHit].self, from: data)
    }

    /// Synchronously trigger `retitle once --session <id>`. Blocks until the
    /// rename completes (or the namer call times out). Returns the stderr/log
    /// text the CLI emitted so the caller can show "renamed N of M".
    @discardableResult
    func renameSession(id: String, tool: String? = nil) throws -> String {
        var args = ["once", "--session", id]
        if let tool { args += ["--tool", tool] }
        return try runReturningStderr(args)
    }

    /// User-initiated full historical rename pass (the GUI "Rename historical
    /// sessions" button). Can take a long time — every backlog session may
    /// trigger a namer call. Caller should put this on a background queue and
    /// show a spinner.
    @discardableResult
    func renameHistorical(dryRun: Bool = false) throws -> String {
        var args = ["once", "--historical", "--all"]
        if dryRun { args.append("--dry-run") }
        return try runReturningStderr(args, timeout: 60 * 60)  // up to an hour
    }

    private func runReturningStderr(_ args: [String], timeout: TimeInterval = 240) throws -> String {
        let p = Process()
        p.executableURL = executable
        p.arguments = args
        let err = Pipe()
        p.standardOutput = Pipe()
        p.standardError = err
        try p.run()
        // We deliberately don't enforce the timeout for the historical pass —
        // the user has consented to a long-running operation. The timeout
        // here is just a parameter for future callers.
        _ = timeout
        p.waitUntilExit()
        let stderrData = err.fileHandleForReading.readDataToEndOfFile()
        let stderr = String(data: stderrData, encoding: .utf8) ?? ""
        if p.terminationStatus != 0 {
            throw RetitleCLIError.failed(stderr: stderr, code: p.terminationStatus)
        }
        return stderr
    }

    private func decode<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            let preview = String(data: data.prefix(200), encoding: .utf8) ?? "<binary>"
            throw RetitleCLIError.decodeFailed("\(error.localizedDescription) — got: \(preview)")
        }
    }
}

/// Search result shape (from `retitle search --json`).
struct SearchHit: Codable, Identifiable, Hashable {
    let tool: String
    let id: String
    let title: String?
    let idleSeconds: Int
    let cwd: String?
    let snippet: String?

    enum CodingKeys: String, CodingKey {
        case tool, id, title
        case idleSeconds = "idle_seconds"
        case cwd, snippet
    }
}
