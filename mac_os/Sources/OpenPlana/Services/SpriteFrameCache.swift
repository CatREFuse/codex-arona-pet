import AppKit
import Foundation
import ImageIO

final class SpriteFrameCache {
    private var sheets: [URL: CGImage] = [:]
    private var frames: [String: NSImage] = [:]
    private var visibleUnitBounds: [String: CGRect] = [:]

    func image(for character: PetCharacter, state requestedState: PetAnimationState, tick: Int) -> NSImage? {
        if let extra = character.extraStates[requestedState], !extra.framePaths.isEmpty {
            let index = abs(tick) % extra.framePaths.count
            let url = character.directoryURL.appendingPathComponent(extra.framePaths[index])
            return loadImage(url: url, cacheKey: "extra:\(character.id):\(requestedState.rawValue):\(index)")
        }

        let state: PetAnimationState
        switch requestedState {
        case .carried:
            state = .jumping
        case .idleRead, .idleNormal, .idleSleep,
             .edgePeekLeft, .edgePeekRight,
             .edgeIdleReadLeft, .edgeIdleReadRight,
             .edgeIdleNormalLeft, .edgeIdleNormalRight,
             .edgeIdleSleepLeft, .edgeIdleSleepRight,
             .pinched, .edgePinchedLeft, .edgePinchedRight:
            state = .idle
        case .coding, .edgeCodingLeft, .edgeCodingRight:
            state = .running
        case .checking, .edgeCheckingLeft, .edgeCheckingRight:
            state = .review
        case .awaiting, .edgeAwaitingLeft, .edgeAwaitingRight:
            state = .waiting
        case .rejected, .edgeRejectedLeft, .edgeRejectedRight:
            state = .failed
        case .success, .edgeSuccessLeft, .edgeSuccessRight:
            state = .failed
        default:
            state = requestedState
        }
        guard let row = SpriteRow.codexRows[state] else { return nil }
        let index = abs(tick) % row.frames
        let key = "sheet:\(character.id):\(state.rawValue):\(index)"

        if let cached = frames[key] {
            return cached
        }

        guard let sheet = loadSheet(url: character.spritesheetURL) else {
            return nil
        }

        let rect = CGRect(
            x: index * SpriteRow.cellWidth,
            y: row.row * SpriteRow.cellHeight,
            width: SpriteRow.cellWidth,
            height: SpriteRow.cellHeight
        )

        guard let cropped = sheet.cropping(to: rect) else {
            return nil
        }

        let image = NSImage(cgImage: cropped, size: NSSize(width: SpriteRow.cellWidth, height: SpriteRow.cellHeight))
        frames[key] = image
        return image
    }

    func visibleUnitBounds(for character: PetCharacter, state: PetAnimationState, frameCount: Int) -> CGRect {
        let key = "visible:\(character.id):\(state.rawValue):\(frameCount)"
        if let cached = visibleUnitBounds[key] {
            return cached
        }

        var unionBounds: CGRect?
        for tick in 0..<max(frameCount, 1) {
            guard let image = image(for: character, state: state, tick: tick),
                  let bounds = alphaUnitBounds(for: image) else {
                continue
            }
            unionBounds = unionBounds.map { $0.union(bounds) } ?? bounds
        }

        let resolved = unionBounds ?? CGRect(x: 0, y: 0, width: 1, height: 1)
        visibleUnitBounds[key] = resolved
        return resolved
    }

    private func loadImage(url: URL, cacheKey: String) -> NSImage? {
        let resolvedCacheKey = "\(cacheKey):\(fileVersionKey(for: url))"
        if let cached = frames[resolvedCacheKey] {
            return cached
        }
        guard let data = try? Data(contentsOf: url),
              let image = NSImage(data: data) else {
            return nil
        }
        frames[resolvedCacheKey] = image
        return image
    }

    private func fileVersionKey(for url: URL) -> String {
        guard let values = try? url.resourceValues(forKeys: [.contentModificationDateKey, .fileSizeKey]) else {
            return "unknown"
        }
        let modifiedAt = values.contentModificationDate?.timeIntervalSince1970 ?? 0
        let fileSize = values.fileSize ?? 0
        return "\(modifiedAt):\(fileSize)"
    }

    private func loadSheet(url: URL) -> CGImage? {
        if let sheet = sheets[url] {
            return sheet
        }

        guard let data = try? Data(contentsOf: url),
              let source = CGImageSourceCreateWithData(data as CFData, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
            return nil
        }

        sheets[url] = image
        return image
    }

    private func alphaUnitBounds(for image: NSImage) -> CGRect? {
        var proposed = NSRect(origin: .zero, size: image.size)
        guard let cgImage = image.cgImage(forProposedRect: &proposed, context: nil, hints: nil) else {
            return nil
        }

        let width = cgImage.width
        let height = cgImage.height
        guard width > 0, height > 0 else { return nil }

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
            return nil
        }

        context.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))

        var minX = width
        var minY = height
        var maxX = -1
        var maxY = -1
        let alphaThreshold: UInt8 = 16

        for y in 0..<height {
            let row = y * bytesPerRow
            for x in 0..<width {
                let alpha = pixels[row + x * bytesPerPixel + 3]
                guard alpha > alphaThreshold else { continue }
                minX = min(minX, x)
                minY = min(minY, y)
                maxX = max(maxX, x)
                maxY = max(maxY, y)
            }
        }

        guard maxX >= minX, maxY >= minY else { return nil }
        return CGRect(
            x: CGFloat(minX) / CGFloat(width),
            y: CGFloat(minY) / CGFloat(height),
            width: CGFloat(maxX - minX + 1) / CGFloat(width),
            height: CGFloat(maxY - minY + 1) / CGFloat(height)
        )
    }
}
