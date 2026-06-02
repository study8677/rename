import SwiftUI

@main
struct RetitleApp: App {
    @StateObject private var state = AppState()

    var body: some Scene {
        MenuBarExtra("Retitle", systemImage: "text.cursor") {
            MenuBarView()
                .environmentObject(state)
                .onAppear { state.startAutoRefresh() }
        }
        .menuBarExtraStyle(.window)

        WindowGroup("Retitle", id: "dashboard") {
            DashboardView()
                .environmentObject(state)
        }
        .defaultSize(width: 900, height: 600)
    }
}
