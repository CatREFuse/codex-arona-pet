import AppKit
import Combine
import Foundation

final class CharacterStore: ObservableObject {
    @Published private(set) var characters: [PetCharacter] = []
    @Published var selectedCharacterId: String {
        didSet {
            UserDefaults.standard.set(selectedCharacterId, forKey: Self.selectedCharacterDefaultsKey)
        }
    }
    @Published private(set) var lastImportResult: String?

    private static let selectedCharacterDefaultsKey = "selectedCharacterId"
    private static let defaultCharacterId = "plana"
    private static let supportedCharacterIds: Set<String> = ["arona", "arona-swimsuit", "kotonoha-neo", "plana", "plana-cat-maid"]
    private static let legacyCharacterIds: [String: String] = [
        "arona-neo": "arona",
        "plana-neo": "plana"
    ]
    private let fileManager = FileManager.default
    private let frameCache = SpriteFrameCache()

    init() {
        let savedCharacterId = UserDefaults.standard.string(forKey: Self.selectedCharacterDefaultsKey) ?? Self.defaultCharacterId
        selectedCharacterId = Self.legacyCharacterIds[savedCharacterId] ?? savedCharacterId
    }

    var selectedCharacter: PetCharacter? {
        characters.first { $0.id == selectedCharacterId } ?? characters.first
    }

    func reload() {
        var loaded: [PetCharacter] = []

        for directory in bundledCharacterDirectories() {
            loaded.append(contentsOf: loadCharacters(from: directory))
        }

        for directory in sharedCharacterDirectories() {
            loaded.append(contentsOf: loadCharacters(from: directory))
        }

        let userDirectory = ProjectPaths.appSupport.appendingPathComponent("Characters", isDirectory: true)
        loaded.append(contentsOf: loadCharacters(from: userDirectory))

        let codexPetsDirectory = ProjectPaths.codexHome.appendingPathComponent("pets", isDirectory: true)
        loaded.append(contentsOf: loadCharacters(from: codexPetsDirectory))

        var seen: Set<String> = []
        characters = loaded.filter { character in
            guard Self.supportedCharacterIds.contains(character.id) else { return false }
            if seen.contains(character.id) { return false }
            seen.insert(character.id)
            return true
        }.sorted { $0.displayName.localizedStandardCompare($1.displayName) == .orderedAscending }

        if selectedCharacter == nil {
            if characters.contains(where: { $0.id == Self.defaultCharacterId }) {
                selectedCharacterId = Self.defaultCharacterId
            } else if let first = characters.first {
                selectedCharacterId = first.id
            }
        }
    }

    func select(_ character: PetCharacter) {
        selectedCharacterId = character.id
    }

    func frameImage(for state: PetAnimationState, tick: Int) -> NSImage? {
        guard let character = selectedCharacter else { return nil }
        return frameCache.image(for: character, state: state, tick: tick)
    }

    func visibleUnitBounds(for state: PetAnimationState) -> CGRect {
        guard let character = selectedCharacter else {
            return CGRect(x: 0, y: 0, width: 1, height: 1)
        }
        return frameCache.visibleUnitBounds(for: character, state: state, frameCount: frameCount(for: state))
    }

    func frameCount(for state: PetAnimationState) -> Int {
        guard let character = selectedCharacter else { return 1 }
        if let extra = character.extraStates[state] {
            return max(extra.framePaths.count, 1)
        }
        let fallback = fallbackState(for: state)
        return SpriteRow.codexRows[fallback]?.frames ?? 1
    }

    func frameDuration(for state: PetAnimationState) -> TimeInterval {
        let defaultFrameDuration: TimeInterval = 1.0 / 6.0
        guard let character = selectedCharacter else { return defaultFrameDuration }
        if let duration = character.extraStates[state]?.frameDuration {
            return max(duration, 0.05)
        }
        return defaultFrameDuration
    }

    func isLooping(for state: PetAnimationState) -> Bool {
        guard let character = selectedCharacter,
              let extra = character.extraStates[state] else {
            return true
        }
        return extra.loop ?? true
    }

    func importCharacter(from urls: [URL]) throws {
        let destinationRoot = ProjectPaths.appSupport.appendingPathComponent("Characters", isDirectory: true)
        try fileManager.createDirectory(at: destinationRoot, withIntermediateDirectories: true)

        var importedName: String?
        for sourceURL in urls {
            let shouldStop = sourceURL.startAccessingSecurityScopedResource()
            defer {
                if shouldStop { sourceURL.stopAccessingSecurityScopedResource() }
            }

            let values = try sourceURL.resourceValues(forKeys: [.isDirectoryKey])
            if values.isDirectory == true {
                importedName = try importCharacterDirectory(sourceURL, into: destinationRoot)
            } else {
                importedName = try importSpritesheet(sourceURL, into: destinationRoot)
            }
        }

        reload()
        if let importedName {
            lastImportResult = "\(importedName) 已导入"
        }
    }

    func createGenerationTask() throws -> URL {
        let taskDirectory = ProjectPaths.stateDirectory.appendingPathComponent("tasks", isDirectory: true)
        try fileManager.createDirectory(at: taskDirectory, withIntermediateDirectories: true)

        let selected = selectedCharacter
        let name = selected?.displayName ?? "普拉娜"
        let id = selected?.id ?? Self.defaultCharacterId
        let fileURL = taskDirectory.appendingPathComponent("generate-\(id)-character.md")
        let text = """
        为 Open Plana 生成一个 Codex Pet 兼容角色素材包。

        角色：\(name)
        输出：pet.json、spritesheet.webp、extra 状态帧文件
        格式：3072x2304，12 列 9 行，每格 256x256，透明背景
        扩展帧：每帧 256x256，透明背景，源图生成阶段就必须完整位于 1:1 方型框架内
        状态：idle、running-right、running-left、waving、jumping、failed、waiting、running、review
        扩展状态：idle-read、idle-normal、idle-sleep、coding、checking、awaiting、rejected、success、pinched、carried、edge-peek-left、edge-peek-right，以及这些状态的 edge-*-left 和 edge-*-right 贴边版本
        播放：循环动画必须 12 帧、每秒 6 帧、首尾相接；非循环动画每秒 6 帧，帧数不上限
        裁切：普通模组必须保留 8px 四向安全边距；贴边模组只允许屏幕侧黑色边界线贴齐画布，贴边侧不做 8px 内移；贴边模组的上、下和非贴边侧仍需保留 8px 安全边距；半身裁切只允许出现在明确标记为贴边或半身的模组里
        动作：普通态和贴边态必须分别构图，左右贴边态必须分别生成；贴边态必须保持从屏幕边探出、贴边举牌、贴边看书、贴边检查等构图，不能替换成普通完整站姿；贴边侧最外侧 4px 只能是黑色屏幕边界线，不能出现光环、头发、脸、手、手牌、平板或身体色块被生成画布裁切；coding 普通态跪坐敲键盘用电脑，贴边态从屏幕边探出半身用平板；checking 普通态手持放大镜检查，贴边态从边缘探身检查；awaiting 普通态安静等待或看书，贴边态从边缘探身安静等待或看书，不挥手；rejected 普通态举起拒绝标签，贴边态从边缘举牌；success 普通态举起绿色对勾手牌，贴边态从边缘举起绿色对勾手牌；pinched 必须整帧重新绘制捏脸动作，不得叠层；carried 被拎起；edge-peek 从屏幕边钻出
        抠图：源图使用纯色抠图背景；角色光环内部也必须填充同一抠图背景色；帧之间保留足够间距
        贴边：左贴边黑色边界贴齐画布左边，右贴边黑色边界贴齐画布右边；边界外侧只能出现黑色边界线；同一角色的脸宽、头部轮廓、外露比例、头顶光环和手部位置保持一致
        风格：统一为贴边睡觉模组的 3 头身 QQ 人画风，保持角色身份稳定，适合桌面宠物小尺寸显示
        禁止：文字、阴影、拖尾、边框、网格、说明性标注、白底、光环白色内孔、生成源图裁切、贴边边界出现非黑素材像素、脸宽跳变、头部轮廓跳变、相邻帧挤压
        """
        try text.write(to: fileURL, atomically: true, encoding: .utf8)
        return fileURL
    }

    private func bundledCharacterDirectories() -> [URL] {
        guard let resourceURL = Bundle.module.resourceURL else { return [] }
        return [
            resourceURL.appendingPathComponent("Characters", isDirectory: true),
            resourceURL.appendingPathComponent("Resources/Characters", isDirectory: true)
        ]
    }

    private func sharedCharacterDirectories() -> [URL] {
        var roots: [URL] = [
            URL(fileURLWithPath: fileManager.currentDirectoryPath, isDirectory: true)
        ]

        if let executable = CommandLine.arguments.first, !executable.isEmpty {
            roots.append(URL(fileURLWithPath: executable).deletingLastPathComponent())
        }

        if let openPlanaRoot = ProcessInfo.processInfo.environment["OPEN_PLANA_ROOT"], !openPlanaRoot.isEmpty {
            roots.append(URL(fileURLWithPath: openPlanaRoot, isDirectory: true))
        }

        if let resourceURL = Bundle.main.resourceURL {
            roots.append(resourceURL)
        }

        if let resourceURL = Bundle.module.resourceURL {
            roots.append(resourceURL)
        }

        var seen: Set<String> = []
        return roots.flatMap { sharedCharacterCandidates(near: $0) }.filter { url in
            let key = url.standardizedFileURL.path
            guard !seen.contains(key) else { return false }
            seen.insert(key)
            return fileManager.fileExists(atPath: key)
        }
    }

    private func sharedCharacterCandidates(near root: URL) -> [URL] {
        var directories: [URL] = []
        var current = root.standardizedFileURL

        for _ in 0..<8 {
            directories.append(current.appendingPathComponent("shared/Characters", isDirectory: true))
            current.deleteLastPathComponent()
        }

        return directories
    }

    private func fallbackState(for state: PetAnimationState) -> PetAnimationState {
        switch state {
        case .carried:
            return .jumping
        case .idleRead, .idleNormal, .idleSleep,
             .edgePeekLeft, .edgePeekRight,
             .edgeIdleReadLeft, .edgeIdleReadRight,
             .edgeIdleNormalLeft, .edgeIdleNormalRight,
             .edgeIdleSleepLeft, .edgeIdleSleepRight,
             .pinched, .edgePinchedLeft, .edgePinchedRight:
            return .idle
        case .coding, .edgeCodingLeft, .edgeCodingRight:
            return .running
        case .checking, .edgeCheckingLeft, .edgeCheckingRight:
            return .review
        case .awaiting, .edgeAwaitingLeft, .edgeAwaitingRight:
            return .waiting
        case .rejected, .edgeRejectedLeft, .edgeRejectedRight:
            return .failed
        case .success, .edgeSuccessLeft, .edgeSuccessRight:
            return .failed
        default:
            return state
        }
    }

    private func loadCharacters(from directory: URL) -> [PetCharacter] {
        guard let children = try? fileManager.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: [.isDirectoryKey],
            options: [.skipsHiddenFiles]
        ) else {
            return []
        }

        return children.compactMap { child -> PetCharacter? in
            guard (try? child.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true else {
                return nil
            }
            return loadCharacter(from: child)
        }
    }

    private func loadCharacter(from directory: URL) -> PetCharacter? {
        let petURL = directory.appendingPathComponent("pet.json")
        guard let petData = try? Data(contentsOf: petURL),
              let pet = try? JSONDecoder().decode(PetJSON.self, from: petData) else {
            return nil
        }

        let manifestURL = directory.appendingPathComponent("openplana-character.json")
        let manifest = (try? Data(contentsOf: manifestURL))
            .flatMap { try? JSONDecoder().decode(OpenPlanaCharacterManifest.self, from: $0) }

        let spritesheetPath = manifest?.spritesheetPath ?? pet.spritesheetPath
        let spritesheetURL = directory.appendingPathComponent(spritesheetPath)
        guard fileManager.fileExists(atPath: spritesheetURL.path) else {
            return nil
        }

        let codexURL = (manifest?.codexSpritesheetPath).map { directory.appendingPathComponent($0) }
        let previewURL = (manifest?.previewPath).map { directory.appendingPathComponent($0) }
        let extraStates = (manifest?.extraStates ?? [:]).reduce(into: [PetAnimationState: ExtraAnimation]()) { result, pair in
            guard let state = PetAnimationState(rawValue: pair.key) else { return }
            result[state] = pair.value
        }

        return PetCharacter(
            id: manifest?.id ?? pet.id,
            displayName: manifest?.displayName ?? pet.displayName,
            description: manifest?.description ?? pet.description,
            directoryURL: directory,
            spritesheetURL: spritesheetURL,
            codexSpritesheetURL: codexURL,
            previewURL: previewURL,
            extraStates: extraStates
        )
    }

    private func importCharacterDirectory(_ sourceURL: URL, into destinationRoot: URL) throws -> String {
        guard let character = loadCharacter(from: sourceURL) else {
            throw CharacterImportError.unsupported
        }

        let destination = uniqueDirectory(destinationRoot.appendingPathComponent(character.id, isDirectory: true))
        try fileManager.copyItem(at: sourceURL, to: destination)
        return character.displayName
    }

    private func importSpritesheet(_ sourceURL: URL, into destinationRoot: URL) throws -> String {
        let ext = sourceURL.pathExtension.lowercased()
        guard ["png", "webp"].contains(ext) else {
            throw CharacterImportError.unsupported
        }

        let id = sanitizedIdentifier(sourceURL.deletingPathExtension().lastPathComponent)
        let destination = uniqueDirectory(destinationRoot.appendingPathComponent(id, isDirectory: true))
        try fileManager.createDirectory(at: destination, withIntermediateDirectories: true)

        let spriteName = "spritesheet.\(ext)"
        try fileManager.copyItem(at: sourceURL, to: destination.appendingPathComponent(spriteName))

        let pet = PetJSON(
            id: destination.lastPathComponent,
            displayName: sourceURL.deletingPathExtension().lastPathComponent,
            description: "桌面宠物角色。",
            spritesheetPath: spriteName
        )
        let petData = try JSONEncoder.pretty.encode(pet)
        try petData.write(to: destination.appendingPathComponent("pet.json"), options: .atomic)

        return pet.displayName
    }

    private func uniqueDirectory(_ base: URL) -> URL {
        var candidate = base
        var index = 2
        while fileManager.fileExists(atPath: candidate.path) {
            candidate = base.deletingLastPathComponent()
                .appendingPathComponent("\(base.lastPathComponent)-\(index)", isDirectory: true)
            index += 1
        }
        return candidate
    }

    private func sanitizedIdentifier(_ value: String) -> String {
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-_"))
        let scalars = value.lowercased().unicodeScalars.map { scalar in
            allowed.contains(scalar) ? Character(scalar) : "-"
        }
        let result = String(scalars).trimmingCharacters(in: CharacterSet(charactersIn: "-_"))
        return result.isEmpty ? "character" : result
    }
}

enum CharacterImportError: LocalizedError {
    case unsupported

    var errorDescription: String? {
        switch self {
        case .unsupported: "无法导入该素材"
        }
    }
}
