import AppKit
import Combine
import SwiftUI

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var petWindowController: PetWindowController?
    private var settingsWindowController: NSWindowController?
    private var cancellables: Set<AnyCancellable> = []
    private var visibilityTimer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        AppModel.shared.start()

        let controller = PetWindowController(model: AppModel.shared)
        controller.show()
        petWindowController = controller
        bindPetRecovery()

        showSettingsWindow()
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        showSettingsWindow()
        DispatchQueue.main.async { [weak self] in
            self?.petWindowController?.recoverVisibility(animated: false, forceReattach: true)
        }
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }

    func applicationDidBecomeActive(_ notification: Notification) {
        updatePetSettingsWindowMode()
    }

    func applicationDidResignActive(_ notification: Notification) {
        petWindowController?.setLoweredForSettings(false)
    }

    func applicationWillTerminate(_ notification: Notification) {
        visibilityTimer?.invalidate()
    }

    @objc private func recoverPetAfterEnvironmentChange(_ notification: Notification) {
        schedulePetRecovery(forceReattach: false)
    }

    @objc private func settingsWindowDidBecomeKey(_ notification: Notification) {
        petWindowController?.setLoweredForSettings(true)
    }

    @objc private func settingsWindowDidResignKey(_ notification: Notification) {
        updatePetSettingsWindowMode()
    }

    @objc private func settingsWindowWillClose(_ notification: Notification) {
        petWindowController?.setLoweredForSettings(false)
    }

    private func updatePetSettingsWindowMode() {
        let shouldLower = NSApp.isActive && (settingsWindowController?.window?.isVisible == true)
        petWindowController?.setLoweredForSettings(shouldLower)
    }

    private func schedulePetRecovery(forceReattach: Bool) {
        let delays: [TimeInterval] = forceReattach ? [0.05, 0.35, 0.9] : [0.15, 0.65]
        for delay in delays {
            DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
                self?.petWindowController?.recoverVisibility(animated: false, forceReattach: forceReattach)
            }
        }
    }

    private func bindPetRecovery() {
        AppModel.shared.resetPetRequests
            .sink { [weak self] in
                self?.petWindowController?.resetPet(animated: true)
            }
            .store(in: &cancellables)

        let notifications: [(Notification.Name, NotificationCenter)] = [
            (NSWorkspace.activeSpaceDidChangeNotification, NSWorkspace.shared.notificationCenter),
            (NSWorkspace.didActivateApplicationNotification, NSWorkspace.shared.notificationCenter),
            (NSApplication.didChangeScreenParametersNotification, NotificationCenter.default),
            (NSApplication.didUnhideNotification, NotificationCenter.default)
        ]

        for item in notifications {
            item.1.addObserver(
                self,
                selector: #selector(recoverPetAfterEnvironmentChange),
                name: item.0,
                object: nil
            )
        }

        visibilityTimer?.invalidate()
        let timer = Timer(timeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.petWindowController?.recoverVisibility(animated: false)
        }
        visibilityTimer = timer
        RunLoop.main.add(timer, forMode: .common)
    }

    private func showSettingsWindow() {
        if settingsWindowController == nil {
            let window = NSWindow(
                contentRect: NSRect(x: 0, y: 0, width: 840, height: 580),
                styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                backing: .buffered,
                defer: false
            )
            window.title = "设置"
            window.titleVisibility = .visible
            window.titlebarAppearsTransparent = true
            window.isMovableByWindowBackground = true
            window.minSize = NSSize(width: 760, height: 520)
            window.center()
            window.isReleasedWhenClosed = false
            window.contentView = NSHostingView(rootView: SettingsRootView(model: AppModel.shared))
            window.layoutIfNeeded()
            settingsWindowController = NSWindowController(window: window)
            NotificationCenter.default.addObserver(
                self,
                selector: #selector(settingsWindowDidBecomeKey),
                name: NSWindow.didBecomeKeyNotification,
                object: window
            )
            NotificationCenter.default.addObserver(
                self,
                selector: #selector(settingsWindowDidResignKey),
                name: NSWindow.didResignKeyNotification,
                object: window
            )
            NotificationCenter.default.addObserver(
                self,
                selector: #selector(settingsWindowWillClose),
                name: NSWindow.willCloseNotification,
                object: window
            )
        }

        petWindowController?.setLoweredForSettings(true)
        settingsWindowController?.window?.layoutIfNeeded()
        settingsWindowController?.showWindow(nil)
        NSApp.activate(ignoringOtherApps: true)
        settingsWindowController?.window?.makeKeyAndOrderFront(nil)
    }
}
