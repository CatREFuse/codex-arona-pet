import Foundation

struct PetCharacter: Identifiable, Equatable {
    let id: String
    let displayName: String
    let description: String
    let directoryURL: URL
    let spritesheetURL: URL
    let codexSpritesheetURL: URL?
    let previewURL: URL?
    let extraStates: [PetAnimationState: ExtraAnimation]

    var petJSONURL: URL {
        directoryURL.appendingPathComponent("pet.json")
    }
}

struct ExtraAnimation: Codable, Equatable {
    var framePaths: [String]
    var frameDuration: Double?
    var loop: Bool?
}

struct PetJSON: Codable {
    var id: String
    var displayName: String
    var description: String
    var spritesheetPath: String
}

struct OpenPlanaCharacterManifest: Codable {
    var id: String?
    var displayName: String?
    var description: String?
    var spritesheetPath: String?
    var codexSpritesheetPath: String?
    var previewPath: String?
    var extraStates: [String: ExtraAnimation]?
}
