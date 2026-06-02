import SwiftUI
import AppKit

/// Triggers the Dashboard window from real AppKit lifecycle events instead of
/// SwiftUI `.onAppear` (which doesn't fire on MenuBarExtra `.window` style
/// until the user actually clicks the icon — useless when the icon is hidden
/// in a crowded menu bar).
final class RetitleAppDelegate: NSObject, NSApplicationDelegate {
    static let openDashboardOnLaunch = Notification.Name("retitle.openDashboardOnLaunch")

    func applicationDidFinishLaunching(_ note: Notification) {
        if shouldAutoOpenDashboard() {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
                NotificationCenter.default.post(
                    name: Self.openDashboardOnLaunch, object: nil
                )
            }
        }
    }

    /// Re-open Dashboard when the user double-clicks the app in Finder while
    /// it's already running (common reaction to "I can't find the icon").
    func applicationShouldHandleReopen(
        _ sender: NSApplication, hasVisibleWindows: Bool
    ) -> Bool {
        NotificationCenter.default.post(name: Self.openDashboardOnLaunch, object: nil)
        return true
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
                openWindow(id: "dashboard")
                NSApp.activate(ignoringOtherApps: true)
            }
        }
        .menuBarExtraStyle(.window)

        WindowGroup("Retitle", id: "dashboard") {
            DashboardView()
                .environmentObject(state)
                .environmentObject(toasts)
                .sheet(isPresented: $state.showFDAOnboarding) {
                    OnboardingView().environmentObject(state)
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
