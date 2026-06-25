import SwiftUI

struct HookSettingsView: View {
    @ObservedObject var installer: HookInstaller
    private let refreshTimer = Timer.publish(every: 2, on: .main, in: .common).autoconnect()

    var body: some View {
        SettingsForm {
            Section("连接") {
                LabeledContent("连接", value: installer.status.isInstalled ? "已连接" : "未连接")
                LabeledContent("条目", value: installer.status.hooksJSONInstalled ? "已写入" : "未写入")
                LabeledContent("启用", value: installer.status.configEnabled ? "已启用" : "未启用")
                LabeledContent("状态文件", value: installer.status.stateExists ? "已写入" : "未写入")
            }

            Section("最近活动") {
                LabeledContent("任务节点", value: installer.status.lastPhase?.displayName ?? "无")
                LabeledContent("最近事件", value: installer.status.lastEvent ?? "无")
                LabeledContent("最近状态", value: installer.status.lastStatusText ?? installer.status.lastStatus?.displayName ?? "无")
                LabeledContent("更新时间", value: DateParser.shortTime(installer.status.lastUpdate))
                if let taskTitle = installer.status.lastTaskTitle, !taskTitle.isEmpty {
                    LabeledContent("任务", value: taskTitle)
                }
                if let detail = installer.status.lastDetail, !detail.isEmpty {
                    SettingsDetailText(text: detail)
                }
            }

            Section("操作") {
                SettingsActionRow {
                    Button {
                        installer.refresh()
                    } label: {
                        Label("检查", systemImage: "checkmark.circle")
                    }

                    Button {
                        installer.install()
                    } label: {
                        Label("安装", systemImage: "link.badge.plus")
                    }

                    Button {
                        installer.openStateFolder()
                    } label: {
                        Label("打开", systemImage: "folder")
                    }
                }

                if let message = installer.lastActionMessage {
                    SettingsDetailText(text: message)
                }
            }
        }
        .onAppear {
            DispatchQueue.main.async {
                installer.refresh()
            }
        }
        .onReceive(refreshTimer) { _ in
            installer.refresh()
        }
    }
}
