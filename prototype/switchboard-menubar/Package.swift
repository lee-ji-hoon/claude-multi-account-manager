// swift-tools-version: 5.10

import PackageDescription

let package = Package(
    name: "SwitchboardMenuBarPrototype",
    platforms: [.macOS(.v14)],
    products: [
        .executable(
            name: "switchboard-prototype",
            targets: ["SwitchboardPrototype"]
        )
    ],
    targets: [
        .executableTarget(
            name: "SwitchboardPrototype",
            path: "Sources"
        )
    ]
)
