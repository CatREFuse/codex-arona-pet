import Foundation

enum ProjectPaths {
    static var codexHome: URL {
        if let value = ProcessInfo.processInfo.environment["CODEX_HOME"], !value.isEmpty {
            return URL(fileURLWithPath: value, isDirectory: true)
        }
        return URL(fileURLWithPath: NSHomeDirectory(), isDirectory: true)
            .appendingPathComponent(".codex", isDirectory: true)
    }

    static var appSupport: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
        return (base ?? URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Library/Application Support"))
            .appendingPathComponent("OpenPlana", isDirectory: true)
    }

    static var stateDirectory: URL {
        codexHome.appendingPathComponent("open-plana", isDirectory: true)
    }

    static var stateFile: URL {
        stateDirectory.appendingPathComponent("state.json")
    }

    static var hooksFile: URL {
        codexHome.appendingPathComponent("hooks.json")
    }

    static var configFile: URL {
        codexHome.appendingPathComponent("config.toml")
    }

    static var projectRoot: URL {
        if let value = ProcessInfo.processInfo.environment["OPEN_PLANA_ROOT"], !value.isEmpty {
            return URL(fileURLWithPath: value, isDirectory: true)
        }

        let bundleURL = Bundle.main.bundleURL
        if bundleURL.pathExtension == "app" {
            let parent = bundleURL.deletingLastPathComponent()
            if parent.lastPathComponent == "dist" {
                return parent.deletingLastPathComponent()
            }
        }

        return URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true)
    }

    static var scriptsDirectory: URL {
        projectRoot.appendingPathComponent("script", isDirectory: true)
    }
}
