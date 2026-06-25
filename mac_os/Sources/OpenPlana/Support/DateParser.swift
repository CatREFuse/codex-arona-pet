import Foundation

enum DateParser {
    private static let isoFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    private static let fallbackFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }()

    static func parse(_ value: String?) -> Date? {
        guard let value else { return nil }
        return isoFormatter.date(from: value) ?? fallbackFormatter.date(from: value)
    }

    static func shortTime(_ date: Date?) -> String {
        guard let date else { return "无" }
        return date.formatted(date: .omitted, time: .standard)
    }
}
