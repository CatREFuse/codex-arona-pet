import SwiftUI

struct PetOverlayView: View {
    @ObservedObject var model: AppModel
    @State private var tick = 0
    @State private var lastFrameDate = Date()

    private let timer = Timer.publish(every: 1.0 / 30.0, on: .main, in: .common).autoconnect()

    var body: some View {
        ZStack {
            Color.clear

            VStack(spacing: 0) {
                Spacer(minLength: 0)

                SpriteFrameView(
                    model: model,
                    state: model.currentAnimation,
                    tick: tick
                )
                .frame(width: spriteSize.width, height: spriteSize.height)
                .overlay {
                    ResizeHandleOverlay(
                        spriteSize: spriteSize,
                        visibleUnitBounds: visibleUnitBounds,
                        scale: petScale,
                        isLeadingSide: isResizeHandleOnLeadingSide
                    )
                        .opacity(model.isPointerOverPet || model.isResizingPet ? 1 : 0)
                        .scaleEffect(model.isPointerOverPet || model.isResizingPet ? 1 : 0.92)
                }
                .offset(x: spriteEdgeOffset)
            }
            .frame(width: layoutSize.width, height: layoutSize.height, alignment: contentAlignment)

            VStack(spacing: 0) {
                if !model.isDragging, !taskBubbles.isEmpty {
                    TaskBubbleStackView(
                        tasks: taskBubbles,
                        side: model.dockSide,
                        isCollapsed: model.areTaskBubblesCollapsed,
                        scale: bubbleScale
                    ) {
                        model.toggleTaskBubblesCollapsed()
                    }
                        .transition(.opacity.combined(with: .scale(scale: 0.96)))
                } else if shouldShowBubble {
                    SpeechBubbleView(text: bubbleText, side: model.dockSide, scale: bubbleScale)
                        .transition(.opacity.combined(with: .scale(scale: 0.96)))
                }

                Spacer(minLength: 0)
            }
            .frame(width: layoutSize.width, height: layoutSize.height, alignment: bubbleAlignment)
            .offset(y: bubbleStackOffsetY)
        }
        .frame(width: layoutSize.width, height: layoutSize.height)
        .onReceive(timer) { date in
            let duration = model.characterStore.frameDuration(for: model.currentAnimation)
            guard date.timeIntervalSince(lastFrameDate) >= duration else { return }
            let count = model.characterStore.frameCount(for: model.currentAnimation)
            if model.characterStore.isLooping(for: model.currentAnimation) {
                tick = (tick + 1) % max(count, 1)
            } else {
                tick = min(tick + 1, max(count - 1, 0))
            }
            lastFrameDate = date
        }
        .onChange(of: model.currentAnimation) { _, _ in
            tick = 0
            lastFrameDate = Date()
        }
        .animation(.easeOut(duration: 0.16), value: model.isDragging)
        .animation(.easeOut(duration: 0.16), value: model.activityStore.activity.bubbleText)
        .animation(.easeOut(duration: 0.16), value: taskBubbles.count)
        .animation(.easeOut(duration: 0.16), value: model.areTaskBubblesCollapsed)
        .animation(model.isResizingPet ? nil : .easeOut(duration: 0.16), value: model.petScale)
        .animation(.easeOut(duration: 0.12), value: model.isPointerOverPet)
        .animation(.easeOut(duration: 0.12), value: model.isResizingPet)
    }

    private var petScale: CGFloat {
        CGFloat(model.petScale)
    }

    private var bubbleScale: CGFloat {
        PetLayout.bubbleScale
    }

    private var taskBubbles: [CodexTaskBubble] {
        model.activityStore.activity.petOverlayTaskBubbles
    }

    private var layoutSize: CGSize {
        PetLayout.windowSize(
            scale: petScale,
            taskBubbleCount: taskBubbles.count,
            taskBubblesCollapsed: model.areTaskBubblesCollapsed
        )
    }

    private var spriteSize: CGSize {
        PetLayout.spriteSize(scale: petScale)
    }

    private var bubbleText: String {
        return model.activityStore.activity.bubbleText
    }

    private var shouldShowBubble: Bool {
        guard !model.isDragging else { return false }
        return !bubbleText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private var bubbleAlignment: Alignment {
        guard model.isDockedToEdge else { return .top }
        return model.dockSide == .left ? .topLeading : .topTrailing
    }

    private var contentAlignment: Alignment {
        guard model.isDockedToEdge else { return .bottom }
        return model.dockSide == .left ? .bottomLeading : .bottomTrailing
    }

    private var isResizeHandleOnLeadingSide: Bool {
        model.isDockedToEdge && model.dockSide == .right
    }

    private var visibleUnitBounds: CGRect {
        model.characterStore.visibleUnitBounds(for: model.currentAnimation)
    }

    private var bubbleStackOffsetY: CGFloat {
        guard shouldShowBubble || !taskBubbles.isEmpty else { return 0 }
        let topPadding = PetLayout.scaled(PetLayout.baseBubbleTopPadding, scale: bubbleScale)
        let gap = PetLayout.scaled(PetLayout.baseBubbleSpriteGap, scale: bubbleScale)
        let targetBubbleTop = layoutSize.height - spriteSize.height - gap - bubbleContentHeight
        return max(0, targetBubbleTop - topPadding)
    }

    private var bubbleContentHeight: CGFloat {
        if !taskBubbles.isEmpty {
            return PetLayout.taskBubbleStackHeight(
                taskBubbleCount: taskBubbles.count,
                collapsed: model.areTaskBubblesCollapsed,
                scale: bubbleScale
            )
        }
        return PetLayout.speechBubbleHeight(scale: bubbleScale)
    }

    private var spriteEdgeOffset: CGFloat {
        guard !model.isDragging, model.isDockedToEdge else { return 0 }
        return PetLayout.edgeSpriteOffset(
            for: model.dockSide,
            state: model.currentAnimation,
            scale: petScale,
            taskBubbleCount: taskBubbles.count,
            taskBubblesCollapsed: model.areTaskBubblesCollapsed
        )
    }
}

struct ResizeHandleOverlay: View {
    let spriteSize: CGSize
    let visibleUnitBounds: CGRect
    let scale: CGFloat
    let isLeadingSide: Bool

    var body: some View {
        ResizeHandleView(scale: scale, isLeadingSide: isLeadingSide)
            .position(handleCenter)
            .allowsHitTesting(false)
    }

    private var handleCenter: CGPoint {
        let handleSize = PetLayout.resizeHandleSize(scale: scale)
        let inset = PetLayout.scaled(10, scale: scale)
        let visible = visibleSpriteRect
        let x = isLeadingSide
            ? visible.minX + inset + handleSize / 2
            : visible.maxX - inset - handleSize / 2
        let bottomY = visible.minY + inset + handleSize / 2
        return CGPoint(
            x: min(max(x, handleSize / 2), spriteSize.width - handleSize / 2),
            y: min(max(spriteSize.height - bottomY, handleSize / 2), spriteSize.height - handleSize / 2)
        )
    }

    private var visibleSpriteRect: CGRect {
        CGRect(
            x: visibleUnitBounds.minX * spriteSize.width,
            y: visibleUnitBounds.minY * spriteSize.height,
            width: visibleUnitBounds.width * spriteSize.width,
            height: visibleUnitBounds.height * spriteSize.height
        )
    }
}

struct ResizeHandleView: View {
    let scale: CGFloat
    let isLeadingSide: Bool

    var body: some View {
        Image(systemName: "arrow.up.left.and.arrow.down.right")
            .font(.system(size: PetLayout.scaled(11, scale: scale), weight: .bold))
            .foregroundStyle(.white)
            .rotationEffect(.degrees(isLeadingSide ? 90 : 0))
            .frame(
                width: PetLayout.resizeHandleSize(scale: scale),
                height: PetLayout.resizeHandleSize(scale: scale)
            )
            .background(Color.black.opacity(0.72), in: Circle())
            .overlay(
                Circle()
                    .stroke(Color.white.opacity(0.2), lineWidth: 1)
            )
            .shadow(color: .black.opacity(0.28), radius: PetLayout.scaled(8, scale: scale), y: PetLayout.scaled(3, scale: scale))
            .padding(PetLayout.scaled(10, scale: scale))
            .allowsHitTesting(false)
    }
}

struct SpeechBubbleView: View {
    let text: String
    let side: DockSide
    let scale: CGFloat

    var body: some View {
        Text(text)
            .font(.system(size: PetLayout.scaled(13, scale: scale), weight: .medium))
            .lineLimit(4)
            .multilineTextAlignment(.leading)
            .foregroundStyle(.primary)
            .padding(.horizontal, PetLayout.scaled(12, scale: scale))
            .padding(.vertical, PetLayout.scaled(9, scale: scale))
            .frame(maxWidth: PetLayout.scaled(210, scale: scale), alignment: .leading)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(.quaternary, lineWidth: 1)
            )
            .shadow(color: .black.opacity(0.18), radius: PetLayout.scaled(10, scale: scale), y: PetLayout.scaled(4, scale: scale))
            .padding(.top, PetLayout.scaled(PetLayout.baseBubbleTopPadding, scale: scale))
            .padding(side == .left ? .leading : .trailing, PetLayout.scaled(PetLayout.edgeContentInset, scale: scale))
    }
}

struct TaskBubbleStackView: View {
    let tasks: [CodexTaskBubble]
    let side: DockSide
    let isCollapsed: Bool
    let scale: CGFloat
    let onToggle: () -> Void

    var body: some View {
        VStack(alignment: side == .left ? .trailing : .leading, spacing: PetLayout.scaled(8, scale: scale)) {
            if isCollapsed {
                CollapsedTaskBubbleView(count: tasks.count, scale: scale, onToggle: onToggle)
            } else {
                ForEach(tasks) { task in
                    RunningTaskBubbleView(task: task, scale: scale, onToggle: onToggle)
                }
            }
        }
        .padding(.top, PetLayout.scaled(PetLayout.baseBubbleTopPadding, scale: scale))
        .padding(side == .left ? .leading : .trailing, PetLayout.scaled(PetLayout.edgeContentInset, scale: scale))
    }
}

struct RunningTaskBubbleView: View {
    let task: CodexTaskBubble
    let scale: CGFloat
    let onToggle: () -> Void

    private var title: String {
        task.sessionTitle
    }

    private var message: String {
        task.realtimeMessage
    }

    private var resultMarker: TaskBubbleResultMarker? {
        task.petOverlayResultMarker
    }

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(alignment: .leading, spacing: PetLayout.scaled(5, scale: scale)) {
                Text(title)
                    .font(.system(size: PetLayout.scaled(11, scale: scale), weight: .semibold))
                    .lineLimit(1)
                    .foregroundStyle(.white.opacity(0.58))

                Text(message)
                    .font(.system(size: PetLayout.scaled(15, scale: scale), weight: .semibold))
                    .lineLimit(2)
                    .foregroundStyle(.white)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            if let resultMarker {
                TaskBubbleResultMarkerView(marker: resultMarker, scale: scale)
            }

            Button(action: onToggle) {
                Image(systemName: "minus")
                    .font(.system(size: PetLayout.scaled(12, scale: scale), weight: .semibold))
                    .foregroundStyle(.white.opacity(0.86))
                    .frame(width: PetLayout.scaled(22, scale: scale), height: PetLayout.scaled(22, scale: scale))
                    .background(Color.white.opacity(0.08), in: Circle())
                    .contentShape(Circle())
            }
            .buttonStyle(.plain)
            .focusable(false)
            .help("收起")
        }
        .padding(.horizontal, PetLayout.scaled(14, scale: scale))
        .padding(.vertical, PetLayout.scaled(10, scale: scale))
        .frame(
            width: PetLayout.taskBubbleWidth(scale: scale, collapsed: false),
            height: PetLayout.scaled(PetLayout.baseTaskBubbleHeight, scale: scale),
            alignment: .leading
        )
        .background(RunningTaskBubbleBackground(scale: scale))
        .shadow(color: .black.opacity(0.3), radius: PetLayout.scaled(12, scale: scale), y: PetLayout.scaled(5, scale: scale))
    }
}

struct TaskBubbleResultMarkerView: View {
    let marker: TaskBubbleResultMarker
    let scale: CGFloat

    var body: some View {
        marker.icon
            .stroke(.white, style: StrokeStyle(lineWidth: PetLayout.scaled(2.4, scale: scale), lineCap: .round, lineJoin: .round))
            .frame(width: PetLayout.scaled(10, scale: scale), height: PetLayout.scaled(10, scale: scale))
            .frame(width: PetLayout.scaled(22, scale: scale), height: PetLayout.scaled(22, scale: scale))
            .background(marker.background, in: Circle())
            .overlay(
                Circle()
                    .stroke(Color.white.opacity(0.16), lineWidth: 1)
            )
            .accessibilityLabel(marker.accessibilityLabel)
    }
}

enum TaskBubbleResultMarker {
    case success
    case failure

    var icon: TaskBubbleResultMarkerIcon {
        switch self {
        case .success: .check
        case .failure: .xmark
        }
    }

    var background: Color {
        switch self {
        case .success: Color.green.opacity(0.92)
        case .failure: Color.red.opacity(0.92)
        }
    }

    var accessibilityLabel: String {
        switch self {
        case .success: "成功"
        case .failure: "失败"
        }
    }
}

struct TaskBubbleResultMarkerIcon: Shape {
    enum Kind {
        case check
        case xmark
    }

    var kind: Kind

    static let check = TaskBubbleResultMarkerIcon(kind: .check)
    static let xmark = TaskBubbleResultMarkerIcon(kind: .xmark)

    func path(in rect: CGRect) -> Path {
        var path = Path()
        switch kind {
        case .check:
            path.move(to: CGPoint(x: rect.minX + rect.width * 0.12, y: rect.minY + rect.height * 0.56))
            path.addLine(to: CGPoint(x: rect.minX + rect.width * 0.42, y: rect.minY + rect.height * 0.84))
            path.addLine(to: CGPoint(x: rect.minX + rect.width * 0.9, y: rect.minY + rect.height * 0.18))
        case .xmark:
            path.move(to: CGPoint(x: rect.minX + rect.width * 0.18, y: rect.minY + rect.height * 0.18))
            path.addLine(to: CGPoint(x: rect.minX + rect.width * 0.82, y: rect.minY + rect.height * 0.82))
            path.move(to: CGPoint(x: rect.minX + rect.width * 0.82, y: rect.minY + rect.height * 0.18))
            path.addLine(to: CGPoint(x: rect.minX + rect.width * 0.18, y: rect.minY + rect.height * 0.82))
        }
        return path
    }
}

private struct RunningTaskBubbleBackground: View {
    let scale: CGFloat
    @State private var isSweeping = false

    var body: some View {
        GeometryReader { proxy in
            let shape = RoundedRectangle(cornerRadius: 8, style: .continuous)
            let sweepWidth = max(proxy.size.width * 0.58, PetLayout.scaled(128, scale: scale))
            let sweepHeight = max(proxy.size.height * 2.8, PetLayout.scaled(180, scale: scale))

            shape
                .fill(Color.black.opacity(0.88))
                .overlay {
                    Rectangle()
                        .fill(
                            LinearGradient(
                                stops: [
                                    .init(color: .white.opacity(0), location: 0),
                                    .init(color: .white.opacity(0.025), location: 0.16),
                                    .init(color: .white.opacity(0.1), location: 0.34),
                                    .init(color: .white.opacity(0.21), location: 0.5),
                                    .init(color: .white.opacity(0.1), location: 0.66),
                                    .init(color: .white.opacity(0.025), location: 0.84),
                                    .init(color: .white.opacity(0), location: 1)
                                ],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .frame(width: sweepWidth, height: sweepHeight)
                        .blur(radius: PetLayout.scaled(7, scale: scale))
                        .rotationEffect(.degrees(8))
                        .offset(x: isSweeping ? proxy.size.width + sweepWidth * 1.2 : -proxy.size.width - sweepWidth * 1.2)
                        .blendMode(.screen)
                        .allowsHitTesting(false)
                }
                .clipShape(shape)
                .overlay {
                    shape
                        .stroke(Color.white.opacity(0.12), lineWidth: 1)
                }
                .onAppear {
                    isSweeping = false
                    withAnimation(.linear(duration: 2.35).delay(0.18).repeatForever(autoreverses: false)) {
                        isSweeping = true
                    }
                }
        }
    }
}

struct CollapsedTaskBubbleView: View {
    let count: Int
    let scale: CGFloat
    let onToggle: () -> Void

    var body: some View {
        Button(action: onToggle) {
            Text("\(count)")
                .font(.system(size: PetLayout.scaled(14, scale: scale), weight: .bold, design: .rounded))
                .monospacedDigit()
                .lineLimit(1)
                .minimumScaleFactor(0.75)
                .foregroundStyle(.white)
                .frame(
                    width: PetLayout.taskBubbleWidth(scale: scale, collapsed: true),
                    height: PetLayout.scaled(PetLayout.baseCollapsedTaskBubbleHeight, scale: scale)
                )
            .background(Color.black.opacity(0.9), in: Circle())
            .contentShape(Circle())
            .shadow(color: .black.opacity(0.3), radius: PetLayout.scaled(8, scale: scale), y: PetLayout.scaled(3, scale: scale))
        }
        .buttonStyle(.plain)
        .focusable(false)
        .help("展开")
    }
}

struct SpriteFrameView: View {
    @ObservedObject var model: AppModel
    let state: PetAnimationState
    let tick: Int

    var body: some View {
        if let image = model.characterStore.frameImage(for: state, tick: tick) {
            Image(nsImage: image)
                .resizable()
                .interpolation(.high)
                .scaledToFit()
                .accessibilityLabel(model.characterStore.selectedCharacter?.displayName ?? "Plana")
        } else {
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(.regularMaterial)
                .overlay {
                    Text("素材缺失")
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(.secondary)
                }
        }
    }
}

extension CodexActivity {
    var petOverlayTaskBubbles: [CodexTaskBubble] {
        let displayTasks = Self.petOverlayDeduplicatedTasks(tasks.filter(\.petOverlayShowsBubble))
        if !displayTasks.isEmpty {
            return displayTasks
        }
        return taskBubbles
    }

    private static func petOverlayDeduplicatedTasks(_ tasks: [CodexTaskBubble]) -> [CodexTaskBubble] {
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
}

extension CodexTaskBubble {
    var petOverlayShowsBubble: Bool {
        showsBubble || petOverlayResultMarker != nil
    }

    var petOverlayResultMarker: TaskBubbleResultMarker? {
        if status == .failed || phase == .failed {
            return .failure
        }
        if status == .success || phase == .finish {
            return .success
        }
        return nil
    }
}
