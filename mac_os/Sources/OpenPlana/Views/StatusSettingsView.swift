import SwiftUI

struct StatusSettingsView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        SettingsForm {
            Section("Codex") {
                LabeledContent("状态", value: model.activityStore.activity.statusText)
                LabeledContent("节点", value: model.activityStore.activity.phase.displayName)
                LabeledContent("动画", value: model.currentAnimation.displayName)
                LabeledContent("事件", value: model.activityStore.activity.event)
                LabeledContent("更新时间", value: DateParser.shortTime(model.activityStore.activity.updatedAt))
                if !model.activityStore.activity.taskTitle.isEmpty {
                    LabeledContent("任务", value: model.activityStore.activity.taskTitle)
                }
                if !model.activityStore.activity.detail.isEmpty {
                    SettingsDetailText(text: model.activityStore.activity.detail)
                }
            }

            Section("角色") {
                LabeledContent("当前角色", value: model.characterStore.selectedCharacter?.displayName ?? "无")
                LabeledContent("贴边", value: model.dockSide.displayName)
            }

            Section("显示") {
                HStack {
                    Slider(value: $model.petScale, in: 0.7...1.6, step: 0.05) {
                        Text("大小")
                    }
                    Text("\(Int((model.petScale * 100).rounded()))%")
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(.secondary)
                        .frame(width: 48, alignment: .trailing)
                }
            }

            Section("操作") {
                Button {
                    model.resetPet()
                } label: {
                    Label("重置位置", systemImage: "arrow.counterclockwise")
                }
                .buttonStyle(.borderedProminent)
            }
        }
    }
}
