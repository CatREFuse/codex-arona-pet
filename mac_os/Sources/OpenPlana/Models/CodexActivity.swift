import Foundation

enum CodexStatus: String, Codable, CaseIterable, Identifiable {
    case idle
    case running
    case waiting
    case review
    case failed
    case success

    var id: String { rawValue }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        let rawStatus = try container.decode(String.self)
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
        switch rawStatus {
        case "completed", "complete", "finished", "finish", "succeeded", "done":
            self = .success
        default:
            self = CodexStatus(rawValue: rawStatus) ?? .idle
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(rawValue)
    }

    var displayName: String {
        switch self {
        case .idle: "空闲"
        case .running: "运行中"
        case .waiting: "等待"
        case .review: "检查"
        case .failed: "失败"
        case .success: "完成"
        }
    }

    var animationState: PetAnimationState {
        switch self {
        case .idle: .idle
        case .running: .running
        case .waiting: .awaiting
        case .review: .review
        case .failed: .failed
        case .success: .success
        }
    }
}

enum CodexActivityPhase: String, Codable, CaseIterable, Identifiable {
    case idle
    case start
    case active
    case authorization
    case finish
    case failed

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .idle: "空闲"
        case .start: "开始"
        case .active: "进行中"
        case .authorization: "请求授权"
        case .finish: "结束"
        case .failed: "异常"
        }
    }
}

struct CodexActivity: Equatable {
    var version: Int
    var event: String
    var phase: CodexActivityPhase
    var status: CodexStatus
    var statusText: String
    var taskTitle: String
    var taskDetail: String
    var detail: String
    var message: String
    var sessionId: String?
    var cwd: String?
    var updatedAt: Date?
    var tasks: [CodexTaskBubble]

    var bubbleText: String {
        let trimmedMessage = message.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedMessage.isEmpty {
            return trimmedMessage
        }

        guard phase != .active else { return "" }
        let trimmedDetail = detail.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedDetail.isEmpty {
            return "\(phase.displayName)：\(trimmedDetail)"
        }
        return ""
    }

    var taskBubbleTitle: String {
        taskBubbles.first?.title ?? legacyTaskBubble.title
    }

    var taskBubbleDetail: String {
        taskBubbles.first?.detail ?? legacyTaskBubble.detail
    }

    var taskBubbles: [CodexTaskBubble] {
        let activeTasks = Self.deduplicatedTasks(tasks.filter { $0.showsBubble && !$0.isInternalSystemTask })
        if !activeTasks.isEmpty {
            return activeTasks
        }

        guard legacyShowsTaskBubble else { return [] }
        return [legacyTaskBubble]
    }

    var showsTaskBubble: Bool {
        !taskBubbles.isEmpty
    }

    var hasActiveSession: Bool {
        if tasks.contains(where: { $0.isActiveSession && !$0.isInternalSystemTask }) {
            return true
        }
        guard !isInternalSystemTask else { return false }
        if status == .running || status == .waiting || status == .review {
            return true
        }
        if phase == .start || phase == .active || phase == .authorization {
            return true
        }
        return false
    }

    var isInternalSystemTask: Bool {
        Self.isInternalSystemText(taskTitle)
            || Self.isInternalSystemText(taskDetail)
            || Self.isInternalSystemText(detail)
            || Self.isInternalSystemText(message)
            || cwd.map(Self.isInternalSystemText) == true
    }

    private var legacyShowsTaskBubble: Bool {
        !isInternalSystemTask
            && (status == .running || status == .failed || status == .success || phase == .start || phase == .active || phase == .finish || phase == .failed)
    }

    static func isInternalSystemText(_ value: String) -> Bool {
        value.contains("## Memory Writing Agent:")
            || value.contains("Memory Writing Agent: Phase 2")
            || value.contains("/.codex/memories")
            || value.contains("/.codex/rollout_summaries")
    }

    private static func deduplicatedTasks(_ tasks: [CodexTaskBubble]) -> [CodexTaskBubble] {
        var seen: Set<String> = []
        var result: [CodexTaskBubble] = []
        for task in tasks {
            let key = task.semanticKey
            guard !seen.contains(key) else { continue }
            seen.insert(key)
            result.append(task)
        }
        return result
    }

    private var legacyTaskBubble: CodexTaskBubble {
        let trimmedTaskDetail = taskDetail.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedTaskTitle = taskTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        let title = !trimmedTaskTitle.isEmpty ? trimmedTaskTitle : (!trimmedTaskDetail.isEmpty ? trimmedTaskDetail : statusText)
        let detail: String
        if phase == .active {
            if !trimmedTaskDetail.isEmpty, trimmedTaskDetail != title {
                detail = trimmedTaskDetail
            } else {
                detail = statusText
            }
        } else {
            let trimmedDetail = self.detail.trimmingCharacters(in: .whitespacesAndNewlines)
            if !trimmedDetail.isEmpty {
                detail = trimmedDetail
            } else if !trimmedTaskDetail.isEmpty, trimmedTaskDetail != title {
                detail = trimmedTaskDetail
            } else {
                detail = statusText
            }
        }

        return CodexTaskBubble(
            id: sessionId ?? cwd ?? "current",
            title: title,
            detail: detail,
            message: detail,
            statusText: statusText,
            status: status,
            phase: phase,
            sessionId: sessionId,
            cwd: cwd,
            updatedAt: updatedAt
        )
    }

    static let idle = CodexActivity(
        version: 1,
        event: "Idle",
        phase: .idle,
        status: .idle,
        statusText: "空闲",
        taskTitle: "",
        taskDetail: "",
        detail: "",
        message: "",
        sessionId: nil,
        cwd: nil,
        updatedAt: nil,
        tasks: []
    )
}

struct CodexTaskBubble: Identifiable, Equatable {
    var id: String
    var title: String
    var detail: String
    var message: String
    var statusText: String
    var status: CodexStatus
    var phase: CodexActivityPhase
    var sessionId: String?
    var cwd: String?
    var updatedAt: Date?

    var showsBubble: Bool {
        status == .running || status == .waiting || status == .failed || status == .success || phase == .start || phase == .active || phase == .authorization || phase == .finish || phase == .failed
    }

    var isActiveSession: Bool {
        status == .running || status == .waiting || status == .review || phase == .start || phase == .active || phase == .authorization
    }

    var isInternalSystemTask: Bool {
        CodexActivity.isInternalSystemText(title)
            || CodexActivity.isInternalSystemText(detail)
            || CodexActivity.isInternalSystemText(message)
            || cwd.map(CodexActivity.isInternalSystemText) == true
    }

    var sessionTitle: String {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmedTitle.hasPrefix("# Files mentioned by the user:"),
           let requestTitle = Self.requestTitle(from: detail) ?? Self.requestTitle(from: message) {
            return requestTitle
        }
        if !trimmedTitle.isEmpty {
            return trimmedTitle
        }
        return "Codex"
    }

    var realtimeMessage: String {
        let trimmedMessage = message.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedMessage.isEmpty, trimmedMessage != sessionTitle {
            return trimmedMessage
        }

        let trimmedDetail = detail.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedDetail.isEmpty, trimmedDetail != sessionTitle {
            return trimmedDetail
        }

        let trimmedStatus = statusText.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmedStatus.isEmpty ? "正在处理" : trimmedStatus
    }

    var semanticKey: String {
        let normalizedTitle = sessionTitle
            .folding(options: [.caseInsensitive, .diacriticInsensitive], locale: .current)
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: #"\s+"#, with: " ", options: .regularExpression)
        return normalizedTitle.isEmpty ? id : normalizedTitle
    }

    private static func requestTitle(from value: String) -> String? {
        let marker = "## My request for Codex:"
        guard let markerRange = value.range(of: marker) else { return nil }
        var tail = String(value[markerRange.upperBound...])
            .replacingOccurrences(of: #"\s+"#, with: " ", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        for separator in ["<image", "##", "# Files mentioned"] {
            if let range = tail.range(of: separator) {
                tail = String(tail[..<range.lowerBound])
                    .trimmingCharacters(in: .whitespacesAndNewlines)
            }
        }
        guard !tail.isEmpty else { return nil }
        return String(tail.prefix(44))
    }
}

struct CodexActivitySnapshot: Codable {
    var version: Int
    var event: String
    var phase: CodexActivityPhase?
    var status: CodexStatus
    var statusText: String?
    var taskTitle: String?
    var taskDetail: String?
    var detail: String?
    var message: String
    var sessionId: String?
    var cwd: String?
    var updatedAt: String?
    var tasks: [CodexTaskSnapshot]?

    var activity: CodexActivity {
        let resolvedPhase = phase ?? Self.phase(for: event)
        let resolvedStatus = Self.status(for: event, phase: resolvedPhase, status: status)
        return CodexActivity(
            version: version,
            event: event,
            phase: resolvedPhase,
            status: resolvedStatus,
            statusText: statusText ?? resolvedStatus.displayName,
            taskTitle: taskTitle ?? "",
            taskDetail: taskDetail ?? "",
            detail: detail ?? "",
            message: message,
            sessionId: sessionId,
            cwd: cwd,
            updatedAt: DateParser.parse(updatedAt),
            tasks: (tasks ?? []).map(\.task)
        )
    }

    private static func status(for event: String, phase: CodexActivityPhase, status: CodexStatus) -> CodexStatus {
        guard status != .failed else { return .failed }
        guard phase == .finish || isCompletionEvent(event) else { return status }
        return .success
    }

    private static func phase(for event: String) -> CodexActivityPhase {
        let lower = event.lowercased()
        if isCompletionEvent(event) {
            return .finish
        }
        if lower.contains("error") || lower.contains("fail") {
            return .failed
        }
        if lower.contains("prompt") || lower.contains("session") {
            return .start
        }
        if lower.contains("notification") {
            return .authorization
        }
        if lower.contains("tool") {
            return .active
        }
        return .idle
    }

    private static func isCompletionEvent(_ event: String) -> Bool {
        let lower = event.lowercased()
        return lower.contains("stop")
            || lower.contains("finish")
            || lower.contains("complete")
            || lower.contains("success")
            || lower.contains("done")
    }
}

struct CodexTaskSnapshot: Codable {
    var id: String?
    var title: String?
    var taskTitle: String?
    var detail: String?
    var taskDetail: String?
    var message: String?
    var statusText: String?
    var status: CodexStatus?
    var phase: CodexActivityPhase?
    var sessionId: String?
    var cwd: String?
    var updatedAt: String?

    var task: CodexTaskBubble {
        let resolvedTitle = (title ?? taskTitle ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let resolvedDetail = (detail ?? taskDetail ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let resolvedMessage = (message ?? detail ?? taskDetail ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let resolvedPhase: CodexActivityPhase
        if let phase {
            resolvedPhase = phase
        } else if status == .success {
            resolvedPhase = .finish
        } else if status == .failed {
            resolvedPhase = .failed
        } else {
            resolvedPhase = .active
        }
        let baseStatus: CodexStatus
        if let status {
            baseStatus = status
        } else {
            switch resolvedPhase {
            case .finish:
                baseStatus = .success
            case .failed:
                baseStatus = .failed
            default:
                baseStatus = .running
            }
        }
        let resolvedStatus: CodexStatus = if resolvedPhase == .failed || baseStatus == .failed {
            .failed
        } else if resolvedPhase == .finish {
            .success
        } else {
            baseStatus
        }
        let fallbackTitle = statusText ?? resolvedStatus.displayName
        return CodexTaskBubble(
            id: id ?? sessionId ?? cwd ?? UUID().uuidString,
            title: resolvedTitle.isEmpty ? fallbackTitle : resolvedTitle,
            detail: resolvedDetail.isEmpty ? fallbackTitle : resolvedDetail,
            message: resolvedMessage,
            statusText: statusText ?? resolvedStatus.displayName,
            status: resolvedStatus,
            phase: resolvedPhase,
            sessionId: sessionId,
            cwd: cwd,
            updatedAt: DateParser.parse(updatedAt)
        )
    }
}
