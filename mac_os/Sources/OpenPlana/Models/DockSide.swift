import Foundation

enum DockSide: String, Codable, CaseIterable {
    case left
    case right

    var displayName: String {
        switch self {
        case .left: "左侧"
        case .right: "右侧"
        }
    }
}
