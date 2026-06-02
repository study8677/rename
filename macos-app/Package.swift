// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "Retitle",
    defaultLocalization: "en",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "Retitle",
            path: "Sources/Retitle",
            resources: [
                .process("Resources"),
            ]
        )
    ]
)
