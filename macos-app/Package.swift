// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "Rename",
    defaultLocalization: "en",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "Rename",
            path: "Sources/Rename",
            resources: [
                .process("Resources"),
            ]
        )
    ]
)
