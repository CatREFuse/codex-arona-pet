import AppKit
import Combine
import Foundation

final class HookInstaller: ObservableObject {
    @Published private(set) var status = HookInstallStatus.unchecked
    @Published private(set) var lastActionMessage: String?

    private let requiredEvents = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "Notification"]
    private let eventSlugs = [
        "SessionStart": "session_start",
        "UserPromptSubmit": "user_prompt_submit",
        "PreToolUse": "pre_tool_use",
        "PostToolUse": "post_tool_use",
        "Stop": "stop",
        "Notification": "notification"
    ]
    private var monitorTimer: Timer?

    var expectedCommandPath: URL {
        ProjectPaths.scriptsDirectory.appendingPathComponent("codex_hook.py")
    }

    func refresh() {
        let hooksURL = ProjectPaths.hooksFile
        let configURL = ProjectPaths.configFile
        let stateURL = ProjectPaths.stateFile
        let data = try? Data(contentsOf: hooksURL)
        let stateKeys = data.flatMap { hookStateKeys(from: $0, hooksURL: hooksURL) } ?? []
        let installedSlugs = Set(stateKeys.compactMap { key in key.split(separator: ":").dropLast(2).last.map(String.init) })
        let hooksJSONInstalled = requiredEvents.allSatisfy { event in
            guard let slug = eventSlugs[event] else { return false }
            return installedSlugs.contains(slug)
        }
        let configText = (try? String(contentsOf: configURL, encoding: .utf8)) ?? ""
        let enabledStateKeys = hookStateEnabledMap(from: configText)
        let configEnabled = codexHooksFeatureEnabled(in: configText)
            && !stateKeys.isEmpty
            && stateKeys.allSatisfy { enabledStateKeys[$0] == true }

        let stateExists = FileManager.default.fileExists(atPath: stateURL.path)
        let snapshot = (try? Data(contentsOf: stateURL))
            .flatMap { try? JSONDecoder().decode(CodexActivitySnapshot.self, from: $0) }

        status = HookInstallStatus(
            isInstalled: hooksJSONInstalled && configEnabled,
            hooksJSONInstalled: hooksJSONInstalled,
            configEnabled: configEnabled,
            hooksURL: hooksURL,
            configURL: configURL,
            stateURL: stateURL,
            stateExists: stateExists,
            lastEvent: snapshot?.event,
            lastPhase: snapshot?.activity.phase,
            lastStatus: snapshot?.status,
            lastStatusText: snapshot?.activity.statusText,
            lastTaskTitle: snapshot?.activity.taskTitle,
            lastTaskDetail: snapshot?.activity.taskDetail,
            lastDetail: snapshot?.activity.detail,
            lastUpdate: DateParser.parse(snapshot?.updatedAt)
        )
    }

    func install() {
        let installer = ProjectPaths.scriptsDirectory.appendingPathComponent("install_codex_hooks.py")
        guard FileManager.default.fileExists(atPath: installer.path) else {
            lastActionMessage = "未找到安装脚本"
            refresh()
            return
        }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.arguments = ["python3", installer.path]

        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe

        do {
            try process.run()
            process.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let output = String(data: data, encoding: .utf8)?
                .trimmingCharacters(in: .whitespacesAndNewlines)
            lastActionMessage = process.terminationStatus == 0 ? "Hooks 已安装" : (output ?? "安装失败")
        } catch {
            lastActionMessage = error.localizedDescription
        }

        refresh()
    }

    func ensureInstalled() {
        refresh()
        guard !status.isInstalled else { return }
        install()
    }

    func startMonitoring() {
        ensureInstalled()
        monitorTimer?.invalidate()
        monitorTimer = Timer.scheduledTimer(withTimeInterval: 20, repeats: true) { [weak self] _ in
            self?.ensureInstalled()
        }
    }

    func openStateFolder() {
        try? FileManager.default.createDirectory(at: ProjectPaths.stateDirectory, withIntermediateDirectories: true)
        NSWorkspace.shared.activateFileViewerSelecting([ProjectPaths.stateFile])
    }

    private func hookStateKeys(from data: Data, hooksURL: URL) -> [String] {
        guard let document = try? JSONDecoder().decode(CodexHooksDocument.self, from: data) else {
            return []
        }

        var keys: [String] = []
        for event in requiredEvents {
            guard let slug = eventSlugs[event],
                  let entries = document.hooks[event] else {
                continue
            }
            for (entryIndex, entry) in entries.enumerated() {
                for (hookIndex, hook) in entry.hooks.enumerated() where hook.command.contains(expectedCommandPath.path) {
                    keys.append("\(hooksURL.path):\(slug):\(entryIndex):\(hookIndex)")
                }
            }
        }
        return keys
    }

    private func codexHooksFeatureEnabled(in configText: String) -> Bool {
        var inFeatures = false
        for rawLine in configText.split(separator: "\n", omittingEmptySubsequences: false) {
            let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
            if line == "[features]" {
                inFeatures = true
                continue
            }
            if line.hasPrefix("[") {
                inFeatures = false
                continue
            }
            guard inFeatures, line.hasPrefix("codex_hooks") else { continue }
            return line.range(of: #"^codex_hooks\s*=\s*true\b"#, options: .regularExpression) != nil
        }
        return false
    }

    private func hookStateEnabledMap(from configText: String) -> [String: Bool] {
        var result: [String: Bool] = [:]
        var currentKey: String?
        let prefix = #"[hooks.state.""#
        let suffix = #""]"#

        for rawLine in configText.split(separator: "\n", omittingEmptySubsequences: false) {
            let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
            if line.hasPrefix("[") {
                currentKey = nil
                if line.hasPrefix(prefix), line.hasSuffix(suffix) {
                    let keyStart = line.index(line.startIndex, offsetBy: prefix.count)
                    let keyEnd = line.index(line.endIndex, offsetBy: -suffix.count)
                    let key = String(line[keyStart..<keyEnd])
                    currentKey = key
                    result[key] = result[key] ?? false
                }
                continue
            }
            guard let currentKey, line.hasPrefix("enabled") else { continue }
            result[currentKey] = line.range(of: #"^enabled\s*=\s*true\b"#, options: .regularExpression) != nil
        }

        return result
    }
}

private struct CodexHooksDocument: Decodable {
    var hooks: [String: [CodexHookEntry]]
}

private struct CodexHookEntry: Decodable {
    var hooks: [CodexCommandHook]
}

private struct CodexCommandHook: Decodable {
    var command: String
}

struct HookInstallStatus {
    var isInstalled: Bool
    var hooksJSONInstalled: Bool
    var configEnabled: Bool
    var hooksURL: URL
    var configURL: URL
    var stateURL: URL
    var stateExists: Bool
    var lastEvent: String?
    var lastPhase: CodexActivityPhase?
    var lastStatus: CodexStatus?
    var lastStatusText: String?
    var lastTaskTitle: String?
    var lastTaskDetail: String?
    var lastDetail: String?
    var lastUpdate: Date?

    static let unchecked = HookInstallStatus(
        isInstalled: false,
        hooksJSONInstalled: false,
        configEnabled: false,
        hooksURL: ProjectPaths.hooksFile,
        configURL: ProjectPaths.configFile,
        stateURL: ProjectPaths.stateFile,
        stateExists: false,
        lastEvent: nil,
        lastPhase: nil,
        lastStatus: nil,
        lastStatusText: nil,
        lastTaskTitle: nil,
        lastTaskDetail: nil,
        lastDetail: nil,
        lastUpdate: nil
    )
}
