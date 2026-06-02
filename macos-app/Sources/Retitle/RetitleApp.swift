import SwiftUI

@main
struct RetitleApp: App {
    @StateObject private var state = AppState()
    @StateObject private var toasts = ToastCenter()
    @Environment(\.openWindow) private var openWindow

    /// Set ``RETITLE_AUTO_OPEN_DASHBOARD=1`` to open the Dashboard at launch.
    /// Used by the README-screenshot job; harmless if unset.
    private var autoOpenDashboard: Bool {
        ProcessInfo.processInfo.environment["RETITLE_AUTO_OPEN_DASHBOARD"] == "1"
    }

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
                    state.startBackgroundStatusPolling()
                    if autoOpenDashboard {
                        // Slight delay so SwiftUI finishes wiring the
                        // window group before we ask it to open.
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                            openWindow(id: "dashboard")
                            NSApp.activate(ignoringOtherApps: true)
                        }
                    }
                }
        } label: {
            HStack(spacing: 4) {
                Image(systemName: "tag.fill")
                Text("Retitle")
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
