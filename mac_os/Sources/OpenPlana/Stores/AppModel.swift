import AppKit
import Combine
import CoreGraphics
import Foundation

enum IdleAnimationVariant: CaseIterable {
    case read
    case sleep

    static func random(excluding current: IdleAnimationVariant? = nil) -> IdleAnimationVariant {
        let candidates = current.map { current in Self.allCases.filter { $0 != current } } ?? []
        let pool = candidates.isEmpty ? Self.allCases : candidates
        return pool.randomElement() ?? .read
    }
}

enum RunningAnimationVariant: CaseIterable {
    case coding
    case read
    case checking

    func next() -> RunningAnimationVariant {
        switch self {
        case .coding: .read
        case .read: .checking
        case .checking: .coding
        }
    }
}

final class AppModel: ObservableObject {
    static let shared = AppModel()

    let activityStore = CodexActivityStore()
    let characterStore = CharacterStore()
    let hookInstaller = HookInstaller()
    let resetPetRequests = PassthroughSubject<Void, Never>()

    @Published var isDragging = false
    @Published var isClicking = false
    @Published var isPointerOverPet = false
    @Published var isResizingPet = false
    @Published var isDockedToEdge = true
    @Published var dockSide: DockSide = .right
    @Published var edgeRevealProgress: Double = 1
    @Published var petScale: Double {
        didSet {
            let clamped = Self.clampedPetScale(petScale)
            if petScale != clamped {
                petScale = clamped
                return
            }
            UserDefaults.standard.set(petScale, forKey: Self.petScaleDefaultsKey)
        }
    }
    @Published var areTaskBubblesCollapsed: Bool {
        didSet {
            UserDefaults.standard.set(areTaskBubblesCollapsed, forKey: Self.taskBubblesCollapsedDefaultsKey)
        }
    }
    @Published private(set) var idleVariant = IdleAnimationVariant.random()
    @Published private(set) var runningVariant: RunningAnimationVariant = .coding

    private static let petScaleDefaultsKey = "petScale"
    private static let taskBubblesCollapsedDefaultsKey = "taskBubblesCollapsed"
    private var cancellables: Set<AnyCancellable> = []
    private var hasStarted = false
    private var revealTimer: Timer?
    private var clickTimer: Timer?
    private var idleTimer: Timer?
    private var runningTimer: Timer?

    private init() {
        let storedScale = UserDefaults.standard.double(forKey: Self.petScaleDefaultsKey)
        petScale = Self.clampedPetScale(storedScale == 0 ? 1 : storedScale)
        areTaskBubblesCollapsed = UserDefaults.standard.bool(forKey: Self.taskBubblesCollapsedDefaultsKey)

        activityStore.objectWillChange
            .sink { [weak self] _ in self?.objectWillChange.send() }
            .store(in: &cancellables)

        characterStore.objectWillChange
            .sink { [weak self] _ in self?.objectWillChange.send() }
            .store(in: &cancellables)

        hookInstaller.objectWillChange
            .sink { [weak self] _ in self?.objectWillChange.send() }
            .store(in: &cancellables)
    }

    var currentAnimation: PetAnimationState {
        if isDragging {
            return .carried
        }
        if isClicking {
            return sideAware(normal: .pinched, left: .edgePinchedLeft, right: .edgePinchedRight)
        }
        if edgeRevealProgress < 1 {
            return dockSide == .left ? .edgePeekLeft : .edgePeekRight
        }
        let activity = activityStore.activity
        guard activity.hasActiveSession else {
            return sleepAnimation()
        }
        switch activity.status {
        case .idle:
            return idleAnimation()
        case .running:
            return runningAnimation()
        case .waiting:
            return sideAware(normal: .awaiting, left: .edgeAwaitingLeft, right: .edgeAwaitingRight)
        case .review:
            return sideAware(normal: .checking, left: .edgeCheckingLeft, right: .edgeCheckingRight)
        case .failed:
            return sideAware(normal: .rejected, left: .edgeRejectedLeft, right: .edgeRejectedRight)
        case .success:
            return sideAware(normal: .success, left: .edgeSuccessLeft, right: .edgeSuccessRight)
        }
    }

    func start() {
        guard !hasStarted else { return }
        hasStarted = true
        characterStore.reload()
        activityStore.start()
        hookInstaller.startMonitoring()
        startIdleVariantTimer()
        startRunningVariantTimer()
        startCodexActivationObserver()
    }

    func resetPet() {
        resetPetRequests.send()
    }

    func resetTransientPetState(dockedToEdge: Bool) {
        revealTimer?.invalidate()
        clickTimer?.invalidate()
        revealTimer = nil
        clickTimer = nil
        isDragging = false
        isClicking = false
        isResizingPet = false
        isDockedToEdge = dockedToEdge
        edgeRevealProgress = 1
    }

    func beginDragging() {
        revealTimer?.invalidate()
        clickTimer?.invalidate()
        edgeRevealProgress = 1
        isClicking = false
        isDockedToEdge = false
        isDragging = true
        activityStore.clearSuccessDisplay()
    }

    func triggerClick() {
        clickTimer?.invalidate()
        isClicking = true
        activityStore.clearSuccessDisplay()
        clickTimer = Timer.scheduledTimer(withTimeInterval: 1.4, repeats: false) { [weak self] _ in
            self?.isClicking = false
            self?.clickTimer = nil
        }
    }

    func startEdgeReveal() {
        guard !isDragging else { return }
        revealTimer?.invalidate()
        revealTimer = nil
        isDockedToEdge = true
        edgeRevealProgress = 1
    }

    func toggleTaskBubblesCollapsed() {
        areTaskBubblesCollapsed.toggle()
    }

    private func startIdleVariantTimer() {
        idleTimer?.invalidate()
        idleTimer = Timer.scheduledTimer(withTimeInterval: 14, repeats: true) { [weak self] _ in
            guard let self, activityStore.activity.status == .idle, !isDragging, !isClicking else { return }
            idleVariant = IdleAnimationVariant.random(excluding: idleVariant)
        }
    }

    private func startRunningVariantTimer() {
        runningTimer?.invalidate()
        runningTimer = Timer.scheduledTimer(withTimeInterval: 8, repeats: true) { [weak self] _ in
            guard let self, activityStore.activity.status == .running, !isDragging, !isClicking else { return }
            runningVariant = runningVariant.next()
        }
    }

    private func startCodexActivationObserver() {
        NSWorkspace.shared.notificationCenter.publisher(for: NSWorkspace.didActivateApplicationNotification)
            .sink { [weak self] notification in
                guard let app = notification.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication else {
                    return
                }
                let name = app.localizedName?.lowercased() ?? ""
                let bundleId = app.bundleIdentifier?.lowercased() ?? ""
                guard name.contains("codex") || bundleId.contains("codex") else { return }
                self?.activityStore.clearSuccessDisplay()
            }
            .store(in: &cancellables)
    }

    private func idleAnimation() -> PetAnimationState {
        switch idleVariant {
        case .read:
            return sideAware(normal: .idleRead, left: .edgeIdleReadLeft, right: .edgeIdleReadRight)
        case .sleep:
            return sleepAnimation()
        }
    }

    private func sleepAnimation() -> PetAnimationState {
        sideAware(normal: .idleSleep, left: .edgeIdleSleepLeft, right: .edgeIdleSleepRight)
    }

    private func runningAnimation() -> PetAnimationState {
        switch runningVariant {
        case .coding:
            return sideAware(normal: .coding, left: .edgeCodingLeft, right: .edgeCodingRight)
        case .read:
            return sideAware(normal: .idleRead, left: .edgeIdleReadLeft, right: .edgeIdleReadRight)
        case .checking:
            return sideAware(normal: .checking, left: .edgeCheckingLeft, right: .edgeCheckingRight)
        }
    }

    private func sideAware(normal: PetAnimationState, left: PetAnimationState, right: PetAnimationState) -> PetAnimationState {
        guard isDockedToEdge else { return normal }
        return dockSide == .left ? left : right
    }

    private static func clampedPetScale(_ value: Double) -> Double {
        min(max(value, 0.7), 1.6)
    }
}
