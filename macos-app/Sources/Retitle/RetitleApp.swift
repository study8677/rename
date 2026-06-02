import SwiftUI

@main
struct RetitleApp: App {
    @StateObject private var state = AppState()
    @StateObject private var toasts = ToastCenter()

    var body: some Scene {
        // Menu bar entry — visible icon + label for discoverability.
        MenuBarExtra {
            MenuBarView()
                .environmentObject(state)
                .environmentObject(toasts)
                .sheet(isPresented: $state.showFDAOnboarding) {
                    OnboardingView().environmentObject(state)
                }
                .onAppear { state.startBackgroundStatusPolling() }
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
