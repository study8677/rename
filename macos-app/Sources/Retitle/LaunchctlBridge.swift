import Foundation

/// Controls the launchd agent that `retitle install` registered.
/// We do NOT touch the .plist — only load/unload it.
struct LaunchctlBridge {
    static let plistPath = ("~/Library/LaunchAgents/com.github.retitle.plist" as NSString)
        .expandingTildeInPath

    static var plistExists: Bool {
        FileManager.default.fileExists(atPath: plistPath)
    }

    static func unload() throws {
        try runLaunchctl(["unload", plistPath])
    }

    static func load() throws {
        try runLaunchctl(["load", "-w", plistPath])
    }

    private static func runLaunchctl(_ args: [String]) throws {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        p.arguments = args
        p.standardOutput = Pipe()
        let err = Pipe()
        p.standardError = err
        try p.run()
        p.waitUntilExit()
        if p.terminationStatus != 0 {
            let stderr =
                String(data: err.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            throw NSError(
                domain: "Retitle.Launchctl",
                code: Int(p.terminationStatus),
                userInfo: [NSLocalizedDescriptionKey: stderr]
            )
        }
    }
}
