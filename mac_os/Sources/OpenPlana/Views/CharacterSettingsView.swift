import SwiftUI
import UniformTypeIdentifiers

struct CharacterSettingsView: View {
    @ObservedObject var store: CharacterStore
    @State private var isDropTargeted = false
    @State private var isImporterPresented = false
    @State private var taskURL: URL?
    @State private var errorMessage: String?

    var body: some View {
        SettingsForm {
            Section("角色") {
                Picker("当前角色", selection: Binding(
                    get: { store.selectedCharacterId },
                    set: { store.selectedCharacterId = $0 }
                )) {
                    if store.characters.isEmpty {
                        Text("无")
                            .tag(store.selectedCharacterId)
                    } else {
                        ForEach(store.characters) { character in
                            Text(character.displayName)
                                .tag(character.id)
                        }
                    }
                }

                if let selected = store.selectedCharacter {
                    LabeledContent("标识符", value: selected.id)
                    LabeledContent("素材", value: selected.directoryURL.lastPathComponent)

                    Button {
                        NSWorkspace.shared.activateFileViewerSelecting([selected.directoryURL])
                    } label: {
                        Label("在 Finder 中显示", systemImage: "folder")
                    }
                }
            }

            Section("素材") {
                DropTargetView(isTargeted: isDropTargeted)
                    .onDrop(of: [.fileURL], isTargeted: $isDropTargeted) { providers in
                        handleDrop(providers)
                    }

                SettingsActionRow {
                    Button {
                        isImporterPresented = true
                    } label: {
                        Label("导入素材", systemImage: "square.and.arrow.down")
                    }

                    Button {
                        do {
                            taskURL = try store.createGenerationTask()
                            errorMessage = nil
                        } catch {
                            errorMessage = error.localizedDescription
                        }
                    } label: {
                        Label("生成任务", systemImage: "wand.and.stars")
                    }

                    Button {
                        store.reload()
                    } label: {
                        Label("刷新", systemImage: "arrow.clockwise")
                    }
                }
            }

            if store.lastImportResult != nil || taskURL != nil || errorMessage != nil {
                Section("结果") {
                    if let lastImportResult = store.lastImportResult {
                        SettingsDetailText(text: lastImportResult)
                    }

                    if let taskURL {
                        SettingsPathRow(title: "任务", url: taskURL, actionTitle: "打开") {
                            NSWorkspace.shared.activateFileViewerSelecting([taskURL])
                        }
                    }

                    if let errorMessage {
                        Text(errorMessage)
                            .font(.system(size: 13))
                            .foregroundStyle(.red)
                            .textSelection(.enabled)
                    }
                }
            }
        }
        .fileImporter(
            isPresented: $isImporterPresented,
            allowedContentTypes: [.folder, .png, .data],
            allowsMultipleSelection: true
        ) { result in
            do {
                try store.importCharacter(from: try result.get())
                errorMessage = nil
            } catch {
                errorMessage = error.localizedDescription
            }
        }
        .onAppear {
            store.reload()
        }
    }

    private func handleDrop(_ providers: [NSItemProvider]) -> Bool {
        for provider in providers where provider.hasItemConformingToTypeIdentifier(UTType.fileURL.identifier) {
            provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { item, error in
                if let error {
                    DispatchQueue.main.async { errorMessage = error.localizedDescription }
                    return
                }

                let url: URL?
                if let data = item as? Data {
                    url = URL(dataRepresentation: data, relativeTo: nil)
                } else if let value = item as? URL {
                    url = value
                } else {
                    url = nil
                }

                guard let url else { return }
                DispatchQueue.main.async {
                    do {
                        try store.importCharacter(from: [url])
                        errorMessage = nil
                    } catch {
                        errorMessage = error.localizedDescription
                }
            }
        }
    }
        return true
    }
}

struct DropTargetView: View {
    let isTargeted: Bool

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "tray.and.arrow.down")
                .font(.system(size: 18))
            Text("拖入角色素材")
                .font(.system(size: 14, weight: .medium))
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
        .foregroundStyle(isTargeted ? Color.accentColor : Color.primary)
        .contentShape(Rectangle())
    }
}
