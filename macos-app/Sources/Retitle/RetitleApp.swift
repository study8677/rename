import SwiftUI
import AppKit

/// Triggers the Dashboard window from real AppKit lifecycle events instead of
/// SwiftUI `.onAppear` (which doesn't fire on MenuBarExtra `.window` style
/// until the user actually clicks the icon — useless when the icon is hidden
/// in a crowded menu bar).
///
/// Also toggles the activation policy between `.accessory` (menu-bar-only,
/// no Dock icon) and `.regular` (Dock icon + can grab focus). LSUIElement
/// apps cannot become frontmost or appear above other windows, so without
/// this toggle the auto-opened Dashboard is created behind every other app
/// and the user can't see it.
final class RetitleAppDelegate: NSObject, NSApplicationDelegate {
    static let openDashboardOnLaunch = Notification.Name("retitle.openDashboardOnLaunch")

    func applicationDidFinishLaunching(_ note: Notification) {
        if shouldAutoOpenDashboard() {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
                // Flip policy BEFORE posting the notification — switching
                // `.accessory → .regular` after a window is already on-screen
                // sometimes leaves the window stranded behind other apps.
                NSApp.setActivationPolicy(.regular)
                NotificationCenter.default.post(
                    name: Self.openDashboardOnLaunch, object: nil
                )
                // Second activate after the window finishes wiring up. Two
                // shots needed: the first one happens before the NSWindow
                // exists (no window to surface), the second after.
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                    NSApp.activate(ignoringOtherApps: true)
                }
            }
        }
    }

    /// Re-open Dashboard when the user double-clicks the app in Finder while
    /// it's already running (common reaction to "I can't find the icon").
    func applicationShouldHandleReopen(
        _ sender: NSApplication, hasVisibleWindows: Bool
    ) -> Bool {
        NSApp.setActivationPolicy(.regular)
        NotificationCenter.default.post(name: Self.openDashboardOnLaunch, object: nil)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
            NSApp.activate(ignoringOtherApps: true)
        }
        return true
    }

    /// Switch from the LSUIElement-imposed `.accessory` policy to `.regular`
    /// just long enough to grab focus; AppKit will keep the policy until we
    /// switch it back when the Dashboard closes.
    static func bringDashboardForward() {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }

    /// Called when the Dashboard window closes — drop back to a pure
    /// menu-bar app so we don't leave a stray Dock icon behind.
    static func restoreMenuBarOnly() {
        NSApp.setActivationPolicy(.accessory)
    }

    private func shouldAutoOpenDashboard() -> Bool {
        if ProcessInfo.processInfo.environment["RETITLE_AUTO_OPEN_DASHBOARD"] == "1" {
            return true
        }
        let defaults = UserDefaults.standard
        if !defaults.bool(forKey: "hasOpenedDashboardOnce") {
            defaults.set(true, forKey: "hasOpenedDashboardOnce")
            return true
        }
        return false
    }
}

@main
struct RetitleApp: App {
    @NSApplicationDelegateAdaptor(RetitleAppDelegate.self) var appDelegate
    @StateObject private var state = AppState()
    @StateObject private var toasts = ToastCenter()
    @Environment(\.openWindow) private var openWindow

    var body: some Scene {
        // Menu bar entry — visible icon + label for discoverability.
        MenuBarExtra {
            MenuBarView()
                .environmentObject(state)
                .environmentObject(toasts)
                .sheet(isPresented: $state.showFDAOnboarding) {
                    OnboardingView().environmentObject(state)
                }
                .onAppear {
                    // Defensive: also kick polling when the popover opens,
                    // in case the label's `.onAppear` somehow didn't run.
                    state.startBackgroundStatusPolling()
                }
        } label: {
            HStack(spacing: 4) {
                Image(systemName: "tag.fill")
                Text("Retitle")
            }
            // The label renders at app launch (the menu-bar icon needs to
            // draw), so this fires once at startup — unlike `.onAppear` on
            // the MenuBarView body, which only fires on icon click. We
            // subscribe to the AppDelegate's reopen notification so
            // launching the app pops the Dashboard into view (otherwise
            // a user with a crowded menu bar has no surface to interact
            // with).
            .onAppear {
                state.startBackgroundStatusPolling()
            }
            .onReceive(
                NotificationCenter.default.publisher(
                    for: RetitleAppDelegate.openDashboardOnLaunch
                )
            ) { _ in
                RetitleAppDelegate.bringDashboardForward()
                openWindow(id: "dashboard")
            }
        }
        .menuBarExtraStyle(.window)

        // Single-window scene: `Window` rather than `WindowGroup` so calling
        // openWindow(id:"dashboard") on an already-open Dashboard surfaces
        // the existing one rather than spawning duplicates.
        Window("Retitle", id: "dashboard") {
            DashboardView()
                .environmentObject(state)
                .environmentObject(toasts)
                .sheet(isPresented: $state.showFDAOnboarding) {
                    OnboardingView().environmentObject(state)
                }
                .onAppear {
                    // Dashboard is on screen — make sure the app can grab
                    // focus and ride above other windows.
                    RetitleAppDelegate.bringDashboardForward()
                }
                .onDisappear {
                    // Dashboard closed — drop the Dock icon so retitle
                    // stays a pure menu-bar app between dashboard sessions.
                    RetitleAppDelegate.restoreMenuBarOnly()
                }
        }
        .defaultSize(width: 920, height: 620)

        Window("settings_window_title", id: "settings") {
            SettingsView()
                .environmentObject(state)
                .toastOverlay(toasts)
        }
        .windowResizability(.contentSize)
    }
}
