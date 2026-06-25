import AppKit
import Darwin
import Foundation
import SwiftUI

@main
struct OpenPlanaApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var model = AppModel.shared

    init() {
        let arguments = CommandLine.arguments
        if arguments.contains("--list-characters") {
            let store = CharacterStore()
            store.reload()
            for character in store.characters {
                print("\(character.id)\t\(character.displayName)\t\(character.directoryURL.path)")
            }
            fflush(stdout)
            exit(0)
        }

        if let index = arguments.firstIndex(of: "--verify-animations") {
            let characterIds = Array(arguments.dropFirst(index + 1)).filter { !$0.hasPrefix("--") }
            let exitCode = Self.verifyAnimations(characterIds: characterIds.isEmpty ? ["plana", "arona", "kotonoha-neo"] : characterIds)
            fflush(stdout)
            fflush(stderr)
            exit(exitCode)
        }
    }

    var body: some Scene {
        Settings {
            SettingsRootView(model: model)
                .frame(minWidth: 760, minHeight: 520)
        }
    }

    private static func verifyAnimations(characterIds: [String]) -> Int32 {
        let store = CharacterStore()
        store.reload()
        let cache = SpriteFrameCache()
        var failures: [String] = []

        for characterId in characterIds {
            guard let character = store.characters.first(where: { $0.id == characterId }) else {
                failures.append("\(characterId): character not found")
                continue
            }

            for state in PetAnimationState.allCases {
                let frameCount = frameCount(for: character, state: state)
                let duration = character.extraStates[state]?.frameDuration ?? (1 / 6)
                let loop = character.extraStates[state]?.loop ?? true
                var visibleFrames = 0

                for tick in 0..<frameCount {
                    guard let image = cache.image(for: character, state: state, tick: tick) else {
                        failures.append("\(character.id) \(state.rawValue) frame \(tick): missing runtime image")
                        continue
                    }
                    if hasVisibleAlpha(image) {
                        visibleFrames += 1
                    } else {
                        failures.append("\(character.id) \(state.rawValue) frame \(tick): blank runtime image")
                    }
                }

                print("\(character.id)\t\(state.rawValue)\tframes=\(frameCount)\tduration=\(String(format: "%.6f", duration))\tloop=\(loop)\tvisible=\(visibleFrames)")
            }
        }

        if failures.isEmpty {
            print("animation verify ok")
            return 0
        }

        for failure in failures {
            fputs("\(failure)\n", stderr)
        }
        return 1
    }

    private static func frameCount(for character: PetCharacter, state: PetAnimationState) -> Int {
        if let extra = character.extraStates[state] {
            return max(extra.framePaths.count, 1)
        }
        if let row = SpriteRow.codexRows[state] {
            return row.frames
        }
        return 1
    }

    private static func hasVisibleAlpha(_ image: NSImage) -> Bool {
        var proposed = NSRect(origin: .zero, size: image.size)
        guard let cgImage = image.cgImage(forProposedRect: &proposed, context: nil, hints: nil) else {
            return false
        }

        let width = cgImage.width
        let height = cgImage.height
        guard width > 0, height > 0 else { return false }

        let bytesPerPixel = 4
        let bytesPerRow = width * bytesPerPixel
        var pixels = [UInt8](repeating: 0, count: height * bytesPerRow)
        guard let context = CGContext(
            data: &pixels,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: bytesPerRow,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        ) else {
            return false
        }

        context.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))
        return stride(from: 3, to: pixels.count, by: bytesPerPixel).contains { pixels[$0] > 16 }
    }
}
