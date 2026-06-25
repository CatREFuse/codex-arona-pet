import Foundation

enum PetAnimationState: String, Codable, CaseIterable, Identifiable {
    case idle
    case runningRight = "running-right"
    case runningLeft = "running-left"
    case waving
    case jumping
    case failed
    case waiting
    case running
    case review
    case carried
    case idleRead = "idle-read"
    case idleNormal = "idle-normal"
    case idleSleep = "idle-sleep"
    case coding
    case checking
    case awaiting
    case rejected
    case success
    case pinched
    case edgePeekLeft = "edge-peek-left"
    case edgePeekRight = "edge-peek-right"
    case edgeIdleReadLeft = "edge-idle-read-left"
    case edgeIdleReadRight = "edge-idle-read-right"
    case edgeIdleNormalLeft = "edge-idle-normal-left"
    case edgeIdleNormalRight = "edge-idle-normal-right"
    case edgeIdleSleepLeft = "edge-idle-sleep-left"
    case edgeIdleSleepRight = "edge-idle-sleep-right"
    case edgeCodingLeft = "edge-coding-left"
    case edgeCodingRight = "edge-coding-right"
    case edgeCheckingLeft = "edge-checking-left"
    case edgeCheckingRight = "edge-checking-right"
    case edgeAwaitingLeft = "edge-awaiting-left"
    case edgeAwaitingRight = "edge-awaiting-right"
    case edgeRejectedLeft = "edge-rejected-left"
    case edgeRejectedRight = "edge-rejected-right"
    case edgeSuccessLeft = "edge-success-left"
    case edgeSuccessRight = "edge-success-right"
    case edgePinchedLeft = "edge-pinched-left"
    case edgePinchedRight = "edge-pinched-right"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .idle: "待机"
        case .runningRight: "向右"
        case .runningLeft: "向左"
        case .waving: "挥手"
        case .jumping: "跳起"
        case .failed: "失败"
        case .waiting: "等待"
        case .running: "运行"
        case .review: "检查"
        case .carried: "拎起"
        case .idleRead: "看书"
        case .idleNormal: "待机"
        case .idleSleep: "睡觉"
        case .coding: "敲键盘"
        case .checking: "检查"
        case .awaiting: "等待"
        case .rejected: "未通过"
        case .success: "完成"
        case .pinched: "捏脸"
        case .edgePeekLeft: "左侧探出"
        case .edgePeekRight: "右侧探出"
        case .edgeIdleReadLeft: "左侧看书"
        case .edgeIdleReadRight: "右侧看书"
        case .edgeIdleNormalLeft: "左侧待机"
        case .edgeIdleNormalRight: "右侧待机"
        case .edgeIdleSleepLeft: "左侧睡觉"
        case .edgeIdleSleepRight: "右侧睡觉"
        case .edgeCodingLeft: "左侧平板"
        case .edgeCodingRight: "右侧平板"
        case .edgeCheckingLeft: "左侧检查"
        case .edgeCheckingRight: "右侧检查"
        case .edgeAwaitingLeft: "左侧等待"
        case .edgeAwaitingRight: "右侧等待"
        case .edgeRejectedLeft: "左侧未通过"
        case .edgeRejectedRight: "右侧未通过"
        case .edgeSuccessLeft: "左侧完成"
        case .edgeSuccessRight: "右侧完成"
        case .edgePinchedLeft: "左侧捏脸"
        case .edgePinchedRight: "右侧捏脸"
        }
    }
}

struct SpriteRow: Equatable {
    let state: PetAnimationState
    let row: Int
    let frames: Int

    static let cellWidth = 256
    static let cellHeight = 256
    static let columns = 12
    static let rows = 9

    static let codexRows: [PetAnimationState: SpriteRow] = [
        .idle: SpriteRow(state: .idle, row: 0, frames: 12),
        .runningRight: SpriteRow(state: .runningRight, row: 1, frames: 12),
        .runningLeft: SpriteRow(state: .runningLeft, row: 2, frames: 12),
        .waving: SpriteRow(state: .waving, row: 3, frames: 12),
        .jumping: SpriteRow(state: .jumping, row: 4, frames: 12),
        .failed: SpriteRow(state: .failed, row: 5, frames: 12),
        .waiting: SpriteRow(state: .waiting, row: 6, frames: 12),
        .running: SpriteRow(state: .running, row: 7, frames: 12),
        .review: SpriteRow(state: .review, row: 8, frames: 12)
    ]
}
