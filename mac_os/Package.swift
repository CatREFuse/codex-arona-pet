// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "OpenPlana",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "OpenPlana", targets: ["OpenPlana"])
    ],
    targets: [
        .executableTarget(
            name: "OpenPlana",
            path: "Sources/OpenPlana",
            resources: [
                .copy("Resources")
            ]
        )
    ],
    swiftLanguageVersions: [.v5]
)
