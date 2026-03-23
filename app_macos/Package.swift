// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "LifeLine",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "LifeLine",
            path: "Sources/LifeLine"
        ),
        .testTarget(
            name: "LifeLineTests",
            dependencies: ["LifeLine"],
            path: "Tests/LifeLineTests"
        )
    ]
)
