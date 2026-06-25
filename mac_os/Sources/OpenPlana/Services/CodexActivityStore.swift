import Combine
import Foundation

final class CodexActivityStore: ObservableObject {
    @Published private(set) var activity: CodexActivity = .idle
    @Published private(set) var stateFileURL: URL = ProjectPaths.stateFile
    @Published private(set) var lastError: String?

    private var timer: Timer?
    private let decoder = JSONDecoder()
    private var clearedSuccessKey: String?
    private let activeSessionTimeout: TimeInterval = 5 * 60

    func start() {
        refresh()
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 0.7, repeats: true) { [weak self] _ in
            self?.refresh()
        }
    }

    func refresh() {
        stateFileURL = ProjectPaths.stateFile

        guard FileManager.default.fileExists(atPath: stateFileURL.path) else {
            activity = .idle
            lastError = nil
            return
        }

        do {
            let data = try Data(contentsOf: stateFileURL)
            let snapshot = try decoder.decode(CodexActivitySnapshot.self, from: data)
            var next = snapshot.activity

            if next.event.range(of: "tool", options: .caseInsensitive) != nil {
                next.message = ""
            }

            next.tasks = next.tasks.filter { task in
                guard !task.isInternalSystemTask else { return false }
                guard let updatedAt = task.updatedAt else { return true }
                return Date().timeIntervalSince(updatedAt) <= activeSessionTimeout
            }

            if next.isInternalSystemTask {
                resetToIdle(&next)
            }

            if next.status == .success {
                if successKey(for: next) == clearedSuccessKey {
                    next = .idle
                }
            } else if next.status == .running || next.status == .waiting {
                clearedSuccessKey = nil
            }

            if let updatedAt = next.updatedAt,
               next.hasActiveSession,
               Date().timeIntervalSince(updatedAt) > activeSessionTimeout {
                resetToIdle(&next)
            }

            if let updatedAt = next.updatedAt,
               next.status == .review,
               Date().timeIntervalSince(updatedAt) > 12 {
                resetToIdle(&next)
            }

            activity = next
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func clearSuccessDisplay() {
        guard activity.status == .success else { return }
        clearedSuccessKey = successKey(for: activity)
        activity = .idle
    }

    private func successKey(for activity: CodexActivity) -> String {
        [
            activity.sessionId ?? "",
            activity.cwd ?? "",
            activity.event,
            activity.updatedAt.map { String($0.timeIntervalSince1970) } ?? "",
            activity.taskTitle,
            activity.taskDetail
        ].joined(separator: "|")
    }

    private func resetToIdle(_ activity: inout CodexActivity) {
        activity.status = .idle
        activity.phase = .idle
        activity.statusText = CodexStatus.idle.displayName
        activity.taskTitle = ""
        activity.taskDetail = ""
        activity.detail = ""
        activity.message = ""
        activity.tasks = []
    }
}
