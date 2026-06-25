import SwiftUI

enum SettingsSection: String, CaseIterable, Hashable, Identifiable {
    case status
    case characters
    case hooks

    var id: String { rawValue }

    var title: String {
        switch self {
        case .status: "状态"
        case .characters: "角色"
        case .hooks: "Hooks"
        }
    }

    var icon: String {
        switch self {
        case .status: "waveform.path.ecg"
        case .characters: "person.crop.square"
        case .hooks: "link"
        }
    }
}

struct SettingsRootView: View {
    @ObservedObject var model: AppModel
    @State private var selection: SettingsSection = .status

    private var selectedSection: SettingsSection {
        selection
    }

    var body: some View {
        HStack(spacing: 0) {
            SettingsSidebar(selection: $selection)
                .frame(width: 220)
                .background(.bar)

            Divider()

            VStack(alignment: .leading, spacing: 0) {
                Text(selectedSection.title)
                    .font(.system(size: 24, weight: .bold))
                    .padding(.horizontal, 32)
                    .padding(.top, 28)
                    .padding(.bottom, 8)

                switch selectedSection {
                case .status:
                    StatusSettingsView(model: model)
                case .characters:
                    CharacterSettingsView(store: model.characterStore)
                case .hooks:
                    HookSettingsView(installer: model.hookInstaller)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        }
        .frame(minWidth: 760, minHeight: 520)
    }
}

private struct SettingsSidebar: View {
    @Binding var selection: SettingsSection

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Spacer()
                .frame(height: 58)

            ForEach(SettingsSection.allCases) { section in
                SettingsSidebarButton(
                    section: section,
                    isSelected: selection == section
                ) {
                    selection = section
                }
            }

            Spacer(minLength: 0)
        }
        .padding(.horizontal, 16)
        .padding(.bottom, 16)
    }
}

private struct SettingsSidebarButton: View {
    let section: SettingsSection
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Label {
                Text(section.title)
                    .font(.system(size: 14, weight: .medium))
            } icon: {
                Image(systemName: section.icon)
                    .symbolRenderingMode(.hierarchical)
                    .frame(width: 18)
            }
            .frame(maxWidth: .infinity, minHeight: 30, alignment: .leading)
            .padding(.horizontal, 8)
            .padding(.vertical, 2)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .foregroundStyle(isSelected ? Color.white : Color.primary)
        .background(
            isSelected ? Color.accentColor : Color.clear,
            in: RoundedRectangle(cornerRadius: 7, style: .continuous)
        )
    }
}

struct SettingsForm<Content: View>: View {
    private let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        Form {
            content
        }
        .formStyle(.grouped)
        .scrollContentBackground(.hidden)
        .padding(.horizontal, 12)
        .padding(.top, 8)
    }
}

struct SettingsDetailText: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.system(size: 13))
            .foregroundStyle(.secondary)
            .textSelection(.enabled)
    }
}

struct SettingsActionRow<Content: View>: View {
    private let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        HStack(spacing: 8) {
            content
            Spacer(minLength: 0)
        }
        .buttonStyle(.bordered)
        .controlSize(.regular)
    }
}

struct SettingsPathRow: View {
    let title: String
    let url: URL
    let actionTitle: String
    let action: () -> Void

    var body: some View {
        LabeledContent(title) {
            HStack(spacing: 8) {
                Text(url.path)
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
                    .textSelection(.enabled)

                Button(actionTitle, action: action)
            }
        }
    }
}
