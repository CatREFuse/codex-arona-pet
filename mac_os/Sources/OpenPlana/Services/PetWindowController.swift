import AppKit
import Combine
import SwiftUI

final class PetWindowController: NSWindowController {
    private let model: AppModel
    private let dragView: PetDragView
    private var cancellables: Set<AnyCancellable> = []
    private var isLoweredForSettings = false
    private var dockPreviewWindow: NSWindow?

    init(model: AppModel) {
        self.model = model
        let dragView = PetDragView(model: model)
        self.dragView = dragView
        let initialSize = PetLayout.windowSize(
            scale: model.petScale,
            taskBubbleCount: model.activityStore.activity.petOverlayTaskBubbles.count,
            taskBubblesCollapsed: model.areTaskBubblesCollapsed
        )

        let panel = PetPanel(
            contentRect: NSRect(x: 0, y: 0, width: initialSize.width, height: initialSize.height),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.backgroundColor = .clear
        panel.isOpaque = false
        panel.hasShadow = false
        panel.acceptsMouseMovedEvents = true
        panel.hidesOnDeactivate = false
        panel.canHide = false
        panel.isFloatingPanel = true
        panel.worksWhenModal = true
        panel.level = PetLayout.windowLevel
        panel.collectionBehavior = PetLayout.collectionBehavior
        panel.isReleasedWhenClosed = false
        panel.title = "Open Plana"

        super.init(window: panel)

        model.isDragging = false
        let rootView = PetOverlayView(model: model)
        let hostingView = NSHostingView(rootView: rootView)
        hostingView.frame = NSRect(origin: .zero, size: initialSize)

        dragView.frame = hostingView.frame
        dragView.installHostedView(hostingView)
        panel.contentView = dragView

        dock(animated: false)
        bindModel()
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        nil
    }

    func show() {
        guard let window else { return }
        configureForAllSpaces(window)
        orderForCurrentMode(window)
    }

    func setLoweredForSettings(_ lowered: Bool) {
        guard isLoweredForSettings != lowered else { return }
        isLoweredForSettings = lowered

        guard let window else { return }
        configureForAllSpaces(window)
        if !lowered {
            orderForCurrentMode(window)
        }
    }

    func dock(animated: Bool, targetVisibleFrame: NSRect? = nil) {
        guard let window else { return }
        hideDockPreview()
        let visible = targetVisibleFrame ?? visibleFrame(for: window)
        let context = layoutContext
        let target = PetLayout.edgeWindowFrame(
            for: model.dockSide,
            currentFrame: window.frame,
            visibleFrame: visible,
            scale: context.scale,
            taskBubbleCount: context.taskBubbleCount,
            taskBubblesCollapsed: context.taskBubblesCollapsed,
            preserveBottomEdge: true
        )
        dragView.contentOffsetX = PetLayout.edgeHostedContentOffset(
            for: model.dockSide,
            scale: context.scale,
            taskBubbleCount: context.taskBubbleCount,
            taskBubblesCollapsed: context.taskBubblesCollapsed
        )
        setFrame(target, animated: false)
        dragView.layoutSubtreeIfNeeded()
        model.startEdgeReveal()
    }

    func resetPet(animated: Bool) {
        guard let window else { return }
        hideDockPreview()
        let visible = visibleFrame(for: window)
        let size = layoutSize
        model.resetTransientPetState(dockedToEdge: false)
        dragView.contentOffsetX = 0
        let frame = NSRect(
            origin: centeredOrigin(for: NSRect(origin: .zero, size: size), in: visible),
            size: size
        )
        setFrame(frame, animated: animated)
        show()
    }

    @discardableResult
    func prepareForDragging(spritePoint: NSPoint? = nil, at screenPoint: NSPoint? = nil, animated: Bool) -> NSPoint? {
        guard let window else { return nil }
        let visible = visibleFrame(for: window)
        let currentFrame = window.frame
        let size = layoutSize
        var x: CGFloat
        var y = PetLayout.clampedWindowY(currentFrame.minY, height: size.height, visibleFrame: visible)
        var dragAnchorInWindow: NSPoint?

        if let spritePoint, let screenPoint {
            let context = layoutContext
            let spriteSize = PetLayout.spriteSize(scale: context.scale)
            let spriteX = PetLayout.contentBaseX(
                width: spriteSize.width,
                side: model.dockSide,
                isDocked: false,
                scale: context.scale,
                taskBubbleCount: context.taskBubbleCount,
                taskBubblesCollapsed: context.taskBubblesCollapsed
            )
            x = screenPoint.x - spriteX - spritePoint.x
            y = screenPoint.y - spritePoint.y
            dragAnchorInWindow = NSPoint(x: spriteX + spritePoint.x, y: spritePoint.y)
        } else if model.dockSide == .left {
            x = currentFrame.minX
        } else {
            x = currentFrame.maxX - size.width
        }
        let frame = NSRect(
            x: x,
            y: y,
            width: size.width,
            height: size.height
        )
        dragView.contentOffsetX = 0
        setFrame(frame, animated: animated)
        return dragAnchorInWindow ?? screenPoint.map { NSPoint(x: $0.x - frame.minX, y: $0.y - frame.minY) }
    }

    func updateDockPreview(for screenPoint: NSPoint, draggingFrame: NSRect) {
        let visible = PetLayout.visibleFrame(containing: screenPoint)
        guard let side = PetLayout.edgeDockSide(for: screenPoint, visibleFrame: visible) else {
            hideDockPreview()
            return
        }
        let context = layoutContext
        let target = PetLayout.edgeWindowFrame(
            for: side,
            currentFrame: draggingFrame,
            visibleFrame: visible,
            scale: context.scale,
            taskBubbleCount: context.taskBubbleCount,
            taskBubblesCollapsed: context.taskBubblesCollapsed,
            preserveBottomEdge: true
        )
        showDockPreview(frame: target)
    }

    func hideDockPreview() {
        dockPreviewWindow?.orderOut(nil)
    }

    func recoverVisibility(animated: Bool, forceReattach: Bool = false) {
        guard let window else { return }
        configureForAllSpaces(window)

        let visible = visibleFrame(for: window)
        let frame = window.frame
        let intersectsAnyVisibleScreen = NSScreen.screens.contains { screen in
            frame.intersects(screen.visibleFrame)
        }
        let isOnActiveSpace = isWindowListedOnActiveSpace(window)
        if model.isDockedToEdge {
            if forceReattach || !window.isVisible || !intersectsAnyVisibleScreen || !isDocked(frame: frame, in: visible) || !isOnActiveSpace {
                dock(animated: animated)
            } else {
                let context = layoutContext
                dragView.contentOffsetX = PetLayout.edgeHostedContentOffset(
                    for: model.dockSide,
                    scale: context.scale,
                    taskBubbleCount: context.taskBubbleCount,
                    taskBubblesCollapsed: context.taskBubblesCollapsed
                )
            }
            orderForCurrentMode(window)
            return
        }

        dragView.contentOffsetX = 0
        let size = layoutSize
        let floatingFrame = NSRect(origin: frame.origin, size: size)
        if forceReattach || !window.isVisible || !intersectsAnyVisibleScreen || !isOnActiveSpace {
            setFrame(NSRect(origin: centeredOrigin(for: floatingFrame, in: visible), size: size), animated: animated)
        } else {
            setFrame(NSRect(origin: clampedOrigin(for: floatingFrame, in: visible), size: size), animated: animated)
        }
        orderForCurrentMode(window)
    }

    private var layoutContext: PetLayoutContext {
        PetLayoutContext(
            scale: CGFloat(model.petScale),
            taskBubbleCount: model.activityStore.activity.petOverlayTaskBubbles.count,
            taskBubblesCollapsed: model.areTaskBubblesCollapsed
        )
    }

    private var layoutSize: NSSize {
        let context = layoutContext
        return PetLayout.windowSize(
            scale: context.scale,
            taskBubbleCount: context.taskBubbleCount,
            taskBubblesCollapsed: context.taskBubblesCollapsed
        )
    }

    private func bindModel() {
        model.$dockSide
            .removeDuplicates()
            .sink { [weak self] _ in
                guard self?.model.isDragging == false else { return }
                self?.dock(animated: false)
            }
            .store(in: &cancellables)

        model.activityStore.$activity
            .map { activity in
                PetTaskBubbleLayoutKey(taskBubbleCount: activity.petOverlayTaskBubbles.count)
            }
            .removeDuplicates()
            .sink { [weak self] _ in
                guard let self, model.isDockedToEdge, !model.isDragging else { return }
                dock(animated: false)
            }
            .store(in: &cancellables)

        model.$petScale
            .removeDuplicates()
            .sink { [weak self] _ in
                guard let self, !model.isDragging, !model.isResizingPet else { return }
                recoverVisibility(animated: false, forceReattach: model.isDockedToEdge)
            }
            .store(in: &cancellables)

        model.$areTaskBubblesCollapsed
            .removeDuplicates()
            .sink { [weak self] _ in
                guard let self, model.isDockedToEdge, !model.isDragging else { return }
                dock(animated: false)
            }
            .store(in: &cancellables)

    }

    private func setFrameOrigin(_ origin: NSPoint, animated: Bool) {
        guard let window else { return }
        setFrame(NSRect(origin: origin, size: window.frame.size), animated: animated)
    }

    private func setFrame(_ frame: NSRect, animated: Bool) {
        guard let window else { return }
        if animated {
            NSAnimationContext.runAnimationGroup { context in
                context.duration = 0.18
                context.timingFunction = CAMediaTimingFunction(name: .easeOut)
                window.animator().setFrame(frame, display: true)
            }
        } else {
            window.setFrame(frame, display: true)
        }
    }

    private func showDockPreview(frame: NSRect) {
        guard let window else { return }
        let preview = dockPreviewWindow ?? makeDockPreviewWindow()
        dockPreviewWindow = preview
        preview.setFrame(frame, display: true)
        preview.order(.below, relativeTo: window.windowNumber)
    }

    private func makeDockPreviewWindow() -> NSWindow {
        let preview = NSPanel(
            contentRect: .zero,
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        preview.backgroundColor = .clear
        preview.isOpaque = false
        preview.hasShadow = false
        preview.ignoresMouseEvents = true
        preview.hidesOnDeactivate = false
        preview.canHide = false
        preview.isFloatingPanel = true
        preview.worksWhenModal = true
        preview.level = PetLayout.windowLevel
        preview.collectionBehavior = PetLayout.collectionBehavior
        preview.isReleasedWhenClosed = false
        preview.contentView = DockPreviewView()
        return preview
    }

    private func configureForAllSpaces(_ window: NSWindow) {
        window.canHide = false
        window.level = isLoweredForSettings ? .normal : PetLayout.windowLevel
        window.collectionBehavior = PetLayout.collectionBehavior
        if let panel = window as? NSPanel {
            panel.isFloatingPanel = true
            panel.worksWhenModal = true
        }
    }

    private func orderForCurrentMode(_ window: NSWindow) {
        if isLoweredForSettings {
            return
        } else {
            window.orderFrontRegardless()
        }
    }

    private func isWindowListedOnActiveSpace(_ window: NSWindow) -> Bool {
        let target = window.windowNumber
        guard target > 0,
              let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] else {
            return window.isVisible
        }
        return windows.contains { item in
            (item[kCGWindowNumber as String] as? Int) == target
        }
    }

    private func visibleFrame(for window: NSWindow) -> NSRect {
        let screen = window.screen ?? NSScreen.main ?? NSScreen.screens.first
        return screen?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1280, height: 800)
    }

    private func centeredOrigin(for frame: NSRect, in visible: NSRect) -> NSPoint {
        NSPoint(
            x: visible.midX - frame.width / 2,
            y: visible.midY - frame.height / 2
        )
    }

    private func isDocked(frame: NSRect, in visible: NSRect) -> Bool {
        let context = layoutContext
        let expected = PetLayout.edgeWindowFrame(
            for: model.dockSide,
            currentFrame: frame,
            visibleFrame: visible,
            scale: context.scale,
            taskBubbleCount: context.taskBubbleCount,
            taskBubblesCollapsed: context.taskBubblesCollapsed,
            preserveBottomEdge: true
        )
        return abs(frame.origin.x - expected.origin.x) <= 2
            && abs(frame.origin.y - expected.origin.y) <= 2
            && abs(frame.width - expected.width) <= 2
            && abs(frame.height - expected.height) <= 2
    }

    private func clampedOrigin(for frame: NSRect, in visible: NSRect) -> NSPoint {
        let minX = visible.minX
        let maxX = max(visible.minX, visible.maxX - frame.width)
        return NSPoint(
            x: min(max(frame.origin.x, minX), maxX),
            y: PetLayout.clampedWindowY(frame.origin.y, height: frame.height, visibleFrame: visible)
        )
    }
}

private final class DockPreviewView: NSView {
    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        wantsLayer = true
        layer?.backgroundColor = NSColor.black.withAlphaComponent(0.2).cgColor
        layer?.cornerRadius = 16
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        nil
    }
}

final class PetPanel: NSPanel {
    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }
}

final class PetDragView: NSView {
    private let model: AppModel
    private weak var hostedView: NSView?
    private var lastScreenPoint: NSPoint?
    private var mouseDownScreenPoint: NSPoint?
    private var dragAnchorInWindow: NSPoint?
    private var trackingArea: NSTrackingArea?
    private var isResizing = false
    private var resizeSession: ResizeSession?
    private let spriteHitInset: CGFloat = 4
    private let dragThreshold: CGFloat = 5
    var contentOffsetX: CGFloat = 0 {
        didSet {
            layoutHostedView()
            needsLayout = true
        }
    }

    init(model: AppModel) {
        self.model = model
        super.init(frame: .zero)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        nil
    }

    func installHostedView(_ view: NSView) {
        hostedView = view
        addSubview(view)
        layoutHostedView()
    }

    override func layout() {
        super.layout()
        layoutHostedView()
    }

    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        if let trackingArea {
            removeTrackingArea(trackingArea)
        }
        let area = NSTrackingArea(
            rect: bounds,
            options: [.activeAlways, .inVisibleRect, .mouseEnteredAndExited, .mouseMoved],
            owner: self,
            userInfo: nil
        )
        trackingArea = area
        addTrackingArea(area)
    }

    override func mouseMoved(with event: NSEvent) {
        updateHoverState(at: event.locationInWindow)
    }

    override func mouseEntered(with event: NSEvent) {
        updateHoverState(at: event.locationInWindow)
    }

    override func mouseExited(with event: NSEvent) {
        model.isPointerOverPet = false
    }

    override func hitTest(_ point: NSPoint) -> NSView? {
        guard bounds.contains(point) else { return nil }
        if let bubble = bubbleBounds, bubble.contains(point), let hostedView {
            let converted = convert(point, to: hostedView)
            return hostedView.hitTest(converted) ?? hostedView
        }
        if resizeHandleBounds.contains(point) {
            return self
        }
        return interactiveBounds.contains(point) ? self : nil
    }

    override func mouseDown(with event: NSEvent) {
        guard let window else { return }
        let screenPoint = window.convertPoint(toScreen: event.locationInWindow)
        mouseDownScreenPoint = screenPoint
        lastScreenPoint = screenPoint
        dragAnchorInWindow = nil
        if resizeHandleBounds.contains(event.locationInWindow) {
            isResizing = true
            model.isResizingPet = true
            let sprite = resizeBoxBounds
            let handleCorner = resizeHandleCorner
            let anchorCorner = handleCorner.opposite
            let anchorLocalPoint = anchorCorner.point(in: sprite)
            let handleLocalPoint = handleCorner.point(in: sprite)
            let anchorScreenPoint = screenPointForLocalPoint(anchorLocalPoint, in: window)
            let handleScreenPoint = screenPointForLocalPoint(handleLocalPoint, in: window)
            resizeSession = ResizeSession(
                startScale: model.petScale,
                anchorCorner: anchorCorner,
                anchorScreenPoint: anchorScreenPoint,
                startHandleVector: CGVector(
                    dx: handleScreenPoint.x - anchorScreenPoint.x,
                    dy: handleScreenPoint.y - anchorScreenPoint.y
                ),
                pointerOffsetFromHandle: CGVector(
                    dx: screenPoint.x - handleScreenPoint.x,
                    dy: screenPoint.y - handleScreenPoint.y
                )
            )
        }
    }

    override func mouseDragged(with event: NSEvent) {
        guard let window, let mouseDownScreenPoint else { return }
        let current = window.convertPoint(toScreen: event.locationInWindow)

        if isResizing {
            updatePetScale(for: current)
            self.lastScreenPoint = current
            return
        }

        if !model.isDragging {
            let distance = hypot(current.x - mouseDownScreenPoint.x, current.y - mouseDownScreenPoint.y)
            guard distance >= dragThreshold else { return }
            let sprite = spriteBounds
            let pointInSprite = NSPoint(
                x: min(max(event.locationInWindow.x - sprite.origin.x, 0), sprite.width),
                y: min(max(event.locationInWindow.y - sprite.origin.y, 0), sprite.height)
            )
            if let controller = window.windowController as? PetWindowController {
                dragAnchorInWindow = controller.prepareForDragging(spritePoint: pointInSprite, at: current, animated: false)
            }
            model.beginDragging()
            if let controller = window.windowController as? PetWindowController {
                controller.updateDockPreview(for: current, draggingFrame: window.frame)
            }
            self.lastScreenPoint = current
            return
        }

        if let dragAnchorInWindow {
            window.setFrameOrigin(
                NSPoint(
                    x: current.x - dragAnchorInWindow.x,
                    y: current.y - dragAnchorInWindow.y
                )
            )
        }
        if let controller = window.windowController as? PetWindowController {
            controller.updateDockPreview(for: current, draggingFrame: window.frame)
        }
        self.lastScreenPoint = current
    }

    override func mouseUp(with event: NSEvent) {
        guard let window else { return }
        if isResizing {
            isResizing = false
            resizeSession = nil
            model.isResizingPet = false
            updateHoverState(at: event.locationInWindow)
            lastScreenPoint = nil
            mouseDownScreenPoint = nil
            dragAnchorInWindow = nil
            return
        }

        let wasDragging = model.isDragging
        lastScreenPoint = nil
        mouseDownScreenPoint = nil
        dragAnchorInWindow = nil

        guard wasDragging else {
            model.triggerClick()
            return
        }

        let releasePoint = window.convertPoint(toScreen: event.locationInWindow)
        let visible = PetLayout.visibleFrame(containing: releasePoint)
        let frame = window.frame
        let dockSide = PetLayout.edgeDockSide(for: releasePoint, visibleFrame: visible)
        if let controller = window.windowController as? PetWindowController {
            controller.hideDockPreview()
        }

        if let dockSide {
            model.dockSide = dockSide
        }
        model.isDragging = false

        if dockSide != nil, let controller = window.windowController as? PetWindowController {
            controller.dock(animated: false, targetVisibleFrame: visible)
        } else {
            model.isDockedToEdge = false
            model.edgeRevealProgress = 1
            window.setFrameOrigin(clampedOrigin(for: frame, in: visible))
        }
    }

    private var interactiveBounds: NSRect {
        var result = visibleSpriteBounds.insetBy(dx: -spriteHitInset, dy: -spriteHitInset)
        result = result.union(resizeHandleBounds)
        if let bubble = bubbleBounds {
            result = result.union(bubble)
        }
        return result
    }

    private var layoutContext: PetLayoutContext {
        layoutContext(scale: CGFloat(model.petScale))
    }

    private func layoutContext(scale: CGFloat) -> PetLayoutContext {
        PetLayoutContext(
            scale: scale,
            taskBubbleCount: model.activityStore.activity.petOverlayTaskBubbles.count,
            taskBubblesCollapsed: model.areTaskBubblesCollapsed
        )
    }

    private var spriteBounds: NSRect {
        spriteBounds(scale: CGFloat(model.petScale), contentOffsetX: contentOffsetX)
    }

    private func spriteBounds(scale: CGFloat, contentOffsetX: CGFloat) -> NSRect {
        let context = layoutContext(scale: scale)
        let size = PetLayout.spriteSize(scale: context.scale)
        let width = size.width
        let height = size.height
        let offset: CGFloat
        if model.isDragging || !model.isDockedToEdge {
            offset = 0
        } else {
            offset = PetLayout.edgeSpriteOffset(
                for: model.dockSide,
                state: model.currentAnimation,
                scale: context.scale,
                taskBubbleCount: context.taskBubbleCount,
                taskBubblesCollapsed: context.taskBubblesCollapsed
            )
        }

        let baseX = PetLayout.contentBaseX(
            width: width,
            side: model.dockSide,
            isDocked: model.isDockedToEdge,
            scale: context.scale,
            taskBubbleCount: context.taskBubbleCount,
            taskBubblesCollapsed: context.taskBubblesCollapsed
        )
        return NSRect(
            x: baseX + offset + contentOffsetX,
            y: 0,
            width: width,
            height: height
        )
    }

    private var visibleSpriteBounds: NSRect {
        visibleSpriteBounds(scale: CGFloat(model.petScale), contentOffsetX: contentOffsetX)
    }

    private func visibleSpriteBounds(scale: CGFloat, contentOffsetX: CGFloat) -> NSRect {
        let sprite = spriteBounds(scale: scale, contentOffsetX: contentOffsetX)
        let unitBounds = model.characterStore.visibleUnitBounds(for: model.currentAnimation)
        return NSRect(
            x: sprite.minX + unitBounds.minX * sprite.width,
            y: sprite.minY + unitBounds.minY * sprite.height,
            width: unitBounds.width * sprite.width,
            height: unitBounds.height * sprite.height
        )
    }

    private var resizeBoxBounds: NSRect {
        visibleSpriteBounds
    }

    private var resizeHandleBounds: NSRect {
        let context = layoutContext
        let handleSize = PetLayout.resizeHandleSize(scale: context.scale)
        let inset = PetLayout.scaled(10, scale: context.scale)
        let sprite = resizeBoxBounds
        let x: CGFloat
        if model.isDockedToEdge, model.dockSide == .right {
            x = sprite.minX + inset
        } else {
            x = sprite.maxX - handleSize - inset
        }
        return NSRect(
            x: x,
            y: sprite.minY + inset,
            width: handleSize,
            height: handleSize
        )
    }

    private var bubbleBounds: NSRect? {
        guard !model.isDragging else { return nil }
        let text = model.activityStore.activity.bubbleText
        let context = layoutContext
        let isTaskBubble = context.taskBubbleCount > 0
        guard isTaskBubble || !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return nil
        }

        let width: CGFloat = isTaskBubble
            ? PetLayout.taskBubbleWidth(scale: PetLayout.bubbleScale, collapsed: context.taskBubblesCollapsed)
            : PetLayout.speechBubbleWidth(scale: PetLayout.bubbleScale)
        let height: CGFloat = isTaskBubble
            ? PetLayout.taskBubbleStackHeight(
                taskBubbleCount: context.taskBubbleCount,
                collapsed: context.taskBubblesCollapsed,
                scale: PetLayout.bubbleScale
            )
            : PetLayout.speechBubbleHeight(scale: PetLayout.bubbleScale)
        let windowSize = PetLayout.windowSize(
            scale: context.scale,
            taskBubbleCount: context.taskBubbleCount,
            taskBubblesCollapsed: context.taskBubblesCollapsed
        )
        let x: CGFloat
        if model.isDockedToEdge {
            let inset = PetLayout.scaled(PetLayout.edgeContentInset, scale: PetLayout.bubbleScale)
            x = model.dockSide == .left ? inset : windowSize.width - width - inset
        } else {
            x = (windowSize.width - width) / 2
        }
        return NSRect(
            x: x + contentOffsetX,
            y: PetLayout.spriteSize(scale: context.scale).height
                + PetLayout.scaled(PetLayout.baseBubbleSpriteGap, scale: PetLayout.bubbleScale),
            width: width,
            height: height
        )
    }

    private func layoutHostedView() {
        let size = PetLayout.windowSize(
            scale: CGFloat(model.petScale),
            taskBubbleCount: model.activityStore.activity.petOverlayTaskBubbles.count,
            taskBubblesCollapsed: model.areTaskBubblesCollapsed
        )
        hostedView?.frame = NSRect(
            x: contentOffsetX,
            y: 0,
            width: size.width,
            height: size.height
        )
    }

    private func updateHoverState(at point: NSPoint) {
        model.isPointerOverPet = visibleSpriteBounds.contains(point) || resizeHandleBounds.contains(point)
    }

    private func updatePetScale(for screenPoint: NSPoint) {
        guard let window, let resizeSession else { return }
        let currentHandlePoint = NSPoint(
            x: screenPoint.x - resizeSession.pointerOffsetFromHandle.dx,
            y: screenPoint.y - resizeSession.pointerOffsetFromHandle.dy
        )
        let currentVector = CGVector(
            dx: currentHandlePoint.x - resizeSession.anchorScreenPoint.x,
            dy: currentHandlePoint.y - resizeSession.anchorScreenPoint.y
        )
        let startVector = resizeSession.startHandleVector
        let startLengthSquared = max(startVector.dx * startVector.dx + startVector.dy * startVector.dy, 1)
        let projectedRatio = (currentVector.dx * startVector.dx + currentVector.dy * startVector.dy) / startLengthSquared
        model.petScale = resizeSession.startScale * Double(max(projectedRatio, 0.01))

        let scale = CGFloat(model.petScale)
        let contentOffset = hostedContentOffset(scale: scale)
        contentOffsetX = contentOffset

        let anchorLocalPoint = resizeSession.anchorCorner.point(in: visibleSpriteBounds(scale: scale, contentOffsetX: contentOffset))
        let frameSize = windowFrameSize(scale: scale)
        let frame = NSRect(
            x: resizeSession.anchorScreenPoint.x - anchorLocalPoint.x,
            y: resizeSession.anchorScreenPoint.y - anchorLocalPoint.y,
            width: frameSize.width,
            height: frameSize.height
        )
        window.setFrame(frame, display: true)
    }

    private var resizeHandleCorner: ResizeCorner {
        if model.isDockedToEdge, model.dockSide == .right {
            return .bottomLeading
        }
        return .bottomTrailing
    }

    private func screenPointForLocalPoint(_ localPoint: NSPoint, in window: NSWindow) -> NSPoint {
        NSPoint(
            x: window.frame.minX + localPoint.x,
            y: window.frame.minY + localPoint.y
        )
    }

    private func hostedContentOffset(scale: CGFloat) -> CGFloat {
        guard model.isDockedToEdge, !model.isDragging else { return 0 }
        let context = layoutContext(scale: scale)
        return PetLayout.edgeHostedContentOffset(
            for: model.dockSide,
            scale: context.scale,
            taskBubbleCount: context.taskBubbleCount,
            taskBubblesCollapsed: context.taskBubblesCollapsed
        )
    }

    private func windowFrameSize(scale: CGFloat) -> NSSize {
        let context = layoutContext(scale: scale)
        let layoutSize = PetLayout.windowSize(
            scale: context.scale,
            taskBubbleCount: context.taskBubbleCount,
            taskBubblesCollapsed: context.taskBubblesCollapsed
        )
        guard model.isDockedToEdge, !model.isDragging else { return layoutSize }
        return NSSize(
            width: PetLayout.edgeVisibleWidth(
                scale: context.scale,
                taskBubbleCount: context.taskBubbleCount,
                taskBubblesCollapsed: context.taskBubblesCollapsed
            ),
            height: layoutSize.height
        )
    }

    private func clampedOrigin(for frame: NSRect, in visible: NSRect) -> NSPoint {
        let minX = visible.minX
        let maxX = max(visible.minX, visible.maxX - frame.width)
        return NSPoint(
            x: min(max(frame.origin.x, minX), maxX),
            y: PetLayout.clampedWindowY(frame.origin.y, height: frame.height, visibleFrame: visible)
        )
    }
}

struct PetLayoutContext {
    var scale: CGFloat
    var taskBubbleCount: Int
    var taskBubblesCollapsed: Bool
}

private struct PetTaskBubbleLayoutKey: Equatable {
    var taskBubbleCount: Int
}

private struct ResizeSession {
    let startScale: Double
    let anchorCorner: ResizeCorner
    let anchorScreenPoint: NSPoint
    let startHandleVector: CGVector
    let pointerOffsetFromHandle: CGVector
}

private enum ResizeCorner {
    case topLeading
    case topTrailing
    case bottomLeading
    case bottomTrailing

    var opposite: ResizeCorner {
        switch self {
        case .topLeading:
            return .bottomTrailing
        case .topTrailing:
            return .bottomLeading
        case .bottomLeading:
            return .topTrailing
        case .bottomTrailing:
            return .topLeading
        }
    }

    func point(in rect: NSRect) -> NSPoint {
        switch self {
        case .topLeading:
            return NSPoint(x: rect.minX, y: rect.maxY)
        case .topTrailing:
            return NSPoint(x: rect.maxX, y: rect.maxY)
        case .bottomLeading:
            return NSPoint(x: rect.minX, y: rect.minY)
        case .bottomTrailing:
            return NSPoint(x: rect.maxX, y: rect.minY)
        }
    }
}

enum PetLayout {
    static let windowLevel = NSWindow.Level.floating
    static let baseWindowSize = NSSize(width: 360, height: 360)
    static let baseSpriteSize = CGSize(width: 256, height: 256)

    // Edge docking standard: one visible strip, one hidden canvas offset, shared by AppKit hit tests and SwiftUI layout.
    static let edgeContentInset: CGFloat = 18
    static let edgeHitInset: CGFloat = 18
    static let edgeVerticalInset: CGFloat = 24
    static let edgeCompactVisibleWidth: CGFloat = baseSpriteSize.width
    static let baseTaskBubbleWidth: CGFloat = 260
    static let baseCollapsedTaskBubbleWidth: CGFloat = 32
    static let baseTaskBubbleHeight: CGFloat = 74
    static let baseCollapsedTaskBubbleHeight: CGFloat = 32
    static let baseTaskBubbleSpacing: CGFloat = 8
    static let baseSpeechBubbleWidth: CGFloat = 236
    static let baseSpeechBubbleHeight: CGFloat = 92
    static let baseBubbleTopPadding: CGFloat = 12
    static let baseBubbleSpriteGap: CGFloat = 8
    static let baseResizeHandleSize: CGFloat = 28
    static let bubbleScale: CGFloat = 1
    static let edgeSpriteRevealDistance: CGFloat = 60
    static let edgeDockTriggerDistance: CGFloat = 48
    static let collectionBehavior: NSWindow.CollectionBehavior = [
        .canJoinAllApplications,
        .canJoinAllSpaces,
        .fullScreenAuxiliary,
        .transient,
        .ignoresCycle
    ]

    static func scaled(_ value: CGFloat, scale: CGFloat) -> CGFloat {
        value * scale
    }

    static func windowSize(scale: CGFloat, taskBubbleCount: Int = 0, taskBubblesCollapsed: Bool = false) -> NSSize {
        let sprite = spriteSize(scale: scale)
        let baseWidth = max(baseWindowSize.width, sprite.width)
        let baseHeight = max(
            baseWindowSize.height,
            scaled(baseBubbleTopPadding + baseSpeechBubbleHeight + baseBubbleSpriteGap, scale: bubbleScale) + sprite.height
        )
        guard taskBubbleCount > 0 else {
            return NSSize(width: baseWidth, height: baseHeight)
        }

        let requiredWidth = taskBubbleWidth(scale: bubbleScale, collapsed: false)
            + scaled(edgeContentInset * 2, scale: bubbleScale)
        let requiredHeight = scaled(baseBubbleTopPadding + baseBubbleSpriteGap, scale: bubbleScale)
            + taskBubbleStackHeight(taskBubbleCount: taskBubbleCount, collapsed: false, scale: bubbleScale)
            + sprite.height
        return NSSize(width: max(baseWidth, requiredWidth), height: max(baseHeight, requiredHeight))
    }

    static func spriteSize(scale: CGFloat) -> CGSize {
        CGSize(width: scaled(baseSpriteSize.width, scale: scale), height: scaled(baseSpriteSize.height, scale: scale))
    }

    static func taskBubbleWidth(scale _: CGFloat, collapsed: Bool) -> CGFloat {
        scaled(collapsed ? baseCollapsedTaskBubbleWidth : baseTaskBubbleWidth, scale: bubbleScale)
    }

    static func taskBubbleStackHeight(taskBubbleCount: Int, collapsed: Bool, scale _: CGFloat) -> CGFloat {
        guard taskBubbleCount > 0 else { return 0 }
        if collapsed {
            return scaled(baseCollapsedTaskBubbleHeight, scale: bubbleScale)
        }
        let count = CGFloat(taskBubbleCount)
        return scaled(baseTaskBubbleHeight, scale: bubbleScale) * count
            + scaled(baseTaskBubbleSpacing, scale: bubbleScale) * max(count - 1, 0)
    }

    static func resizeHandleSize(scale: CGFloat) -> CGFloat {
        scaled(baseResizeHandleSize, scale: scale)
    }

    static func speechBubbleWidth(scale _: CGFloat) -> CGFloat {
        scaled(baseSpeechBubbleWidth, scale: bubbleScale)
    }

    static func speechBubbleHeight(scale _: CGFloat) -> CGFloat {
        scaled(baseSpeechBubbleHeight, scale: bubbleScale)
    }

    static func edgeVisibleWidth(scale: CGFloat, taskBubbleCount: Int, taskBubblesCollapsed: Bool) -> CGFloat {
        let windowWidth = windowSize(scale: scale, taskBubbleCount: taskBubbleCount, taskBubblesCollapsed: taskBubblesCollapsed).width
        let compactWidth = scaled(edgeCompactVisibleWidth, scale: scale)
        if taskBubbleCount > 0 {
            return min(
                windowWidth,
                max(
                    compactWidth,
                    taskBubbleWidth(scale: bubbleScale, collapsed: false) + scaled(edgeContentInset * 2, scale: bubbleScale)
                )
            )
        }
        return compactWidth
    }

    static func edgeHiddenWidth(scale: CGFloat, taskBubbleCount: Int, taskBubblesCollapsed: Bool) -> CGFloat {
        windowSize(scale: scale, taskBubbleCount: taskBubbleCount, taskBubblesCollapsed: taskBubblesCollapsed).width
            - edgeVisibleWidth(scale: scale, taskBubbleCount: taskBubbleCount, taskBubblesCollapsed: taskBubblesCollapsed)
    }

    static func edgeWindowFrame(
        for side: DockSide,
        currentFrame: NSRect,
        visibleFrame: NSRect,
        scale: CGFloat,
        taskBubbleCount: Int = 0,
        taskBubblesCollapsed: Bool = false,
        preserveBottomEdge: Bool = false
    ) -> NSRect {
        let size = windowSize(scale: scale, taskBubbleCount: taskBubbleCount, taskBubblesCollapsed: taskBubblesCollapsed)
        let proposedY = preserveBottomEdge ? currentFrame.maxY - size.height : currentFrame.origin.y
        let y = clampedWindowY(proposedY, height: size.height, visibleFrame: visibleFrame)
        let width = edgeVisibleWidth(scale: scale, taskBubbleCount: taskBubbleCount, taskBubblesCollapsed: taskBubblesCollapsed)
        let x = side == .left
            ? visibleFrame.minX
            : visibleFrame.maxX - width
        return NSRect(x: x, y: y, width: width, height: size.height)
    }

    static func edgeSpriteOffset(
        for side: DockSide,
        state: PetAnimationState? = nil,
        scale: CGFloat,
        taskBubbleCount: Int = 0,
        taskBubblesCollapsed: Bool = false
    ) -> CGFloat {
        let distance = edgeSpriteRevealDistance(for: state)
        return side == .left ? -scaled(distance, scale: scale) : scaled(distance, scale: scale)
    }

    private static func edgeSpriteRevealDistance(for state: PetAnimationState?) -> CGFloat {
        switch state {
        case .edgePeekLeft?, .edgePeekRight?,
             .edgeIdleReadLeft?, .edgeIdleReadRight?,
             .edgeIdleNormalLeft?, .edgeIdleNormalRight?,
             .edgeIdleSleepLeft?, .edgeIdleSleepRight?,
             .edgeCodingLeft?, .edgeCodingRight?,
             .edgeCheckingLeft?, .edgeCheckingRight?,
             .edgeAwaitingLeft?, .edgeAwaitingRight?,
             .edgeRejectedLeft?, .edgeRejectedRight?,
             .edgeSuccessLeft?, .edgeSuccessRight?,
             .edgePinchedLeft?, .edgePinchedRight?:
            return 0
        default:
            return edgeSpriteRevealDistance
        }
    }

    static func edgeHostedContentOffset(
        for side: DockSide,
        scale: CGFloat,
        taskBubbleCount: Int = 0,
        taskBubblesCollapsed: Bool = false
    ) -> CGFloat {
        side == .right ? -edgeHiddenWidth(scale: scale, taskBubbleCount: taskBubbleCount, taskBubblesCollapsed: taskBubblesCollapsed) : 0
    }

    static func contentBaseX(
        width: CGFloat,
        side: DockSide,
        isDocked: Bool,
        scale: CGFloat,
        taskBubbleCount: Int = 0,
        taskBubblesCollapsed: Bool = false
    ) -> CGFloat {
        let windowWidth = windowSize(scale: scale, taskBubbleCount: taskBubbleCount, taskBubblesCollapsed: taskBubblesCollapsed).width
        guard isDocked else {
            return (windowWidth - width) / 2
        }
        return side == .left ? 0 : windowWidth - width
    }

    static func visibleFrame(containing screenPoint: NSPoint) -> NSRect {
        if let screen = NSScreen.screens.first(where: { $0.frame.contains(screenPoint) }) {
            return screen.visibleFrame
        }
        let nearest = NSScreen.screens.min { lhs, rhs in
            distanceSquared(from: screenPoint, to: lhs.frame) < distanceSquared(from: screenPoint, to: rhs.frame)
        }
        return nearest?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1280, height: 800)
    }

    static func edgeDockSide(for screenPoint: NSPoint, visibleFrame: NSRect) -> DockSide? {
        let leftDistance = screenPoint.x - visibleFrame.minX
        let rightDistance = visibleFrame.maxX - screenPoint.x
        let isNearLeftEdge = leftDistance <= edgeDockTriggerDistance
        let isNearRightEdge = rightDistance <= edgeDockTriggerDistance
        guard isNearLeftEdge || isNearRightEdge else { return nil }
        return leftDistance <= rightDistance ? .left : .right
    }

    static func clampedWindowY(_ y: CGFloat, height: CGFloat, visibleFrame: NSRect) -> CGFloat {
        let minY = visibleFrame.minY + edgeVerticalInset
        let maxY = max(minY, visibleFrame.maxY - height - edgeVerticalInset)
        return min(max(y, minY), maxY)
    }

    private static func distanceSquared(from point: NSPoint, to rect: NSRect) -> CGFloat {
        let dx: CGFloat
        if point.x < rect.minX {
            dx = rect.minX - point.x
        } else if point.x > rect.maxX {
            dx = point.x - rect.maxX
        } else {
            dx = 0
        }

        let dy: CGFloat
        if point.y < rect.minY {
            dy = rect.minY - point.y
        } else if point.y > rect.maxY {
            dy = point.y - rect.maxY
        } else {
            dy = 0
        }
        return dx * dx + dy * dy
    }
}
