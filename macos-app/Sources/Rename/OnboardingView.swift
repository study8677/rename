import SwiftUI

/// One-time sheet that explains the TCC / Full Disk Access situation: without
/// it, every refresh storms the user with permission dialogs. With it, none.
struct OnboardingView: View {
    @EnvironmentObject var state: AppState
    @State private var rememberChoice = true

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 10) {
                Image(systemName: "lock.shield.fill")
                    .font(.title)
                    .foregroundStyle(.tint)
                Text(LocalizedStringKey("fda_title"))
                    .font(.title2).fontWeight(.semibold)
            }
            Text(LocalizedStringKey("fda_body"))
                .font(.callout)
                .foregroundStyle(.primary)
                .fixedSize(horizontal: false, vertical: true)

            VStack(alignment: .leading, spacing: 6) {
                Label(LocalizedStringKey("fda_step1"), systemImage: "1.circle.fill")
                Label(LocalizedStringKey("fda_step2"), systemImage: "2.circle.fill")
                Label(LocalizedStringKey("fda_step3"), systemImage: "3.circle.fill")
            }
            .padding(.leading, 4)

            if state.hasFullDiskAccess {
                Label(LocalizedStringKey("fda_already_granted"),
                      systemImage: "checkmark.seal.fill")
                    .foregroundStyle(.green)
                    .font(.callout.weight(.medium))
            }

            Toggle(LocalizedStringKey("fda_remember"), isOn: $rememberChoice)
                .toggleStyle(.checkbox)
                .font(.callout)

            HStack {
                Spacer()
                Button {
                    state.dismissFDAOnboarding(remember: rememberChoice)
                } label: {
                    Text(LocalizedStringKey("fda_skip")).frame(minWidth: 80)
                }
                Button {
                    state.openFullDiskAccessSettings()
                } label: {
                    Text(LocalizedStringKey("fda_open_settings"))
                        .frame(minWidth: 140)
                        .fontWeight(.semibold)
                }
                .keyboardShortcut(.defaultAction)
                .buttonStyle(.borderedProminent)
            }
        }
        .padding(24)
        .frame(width: 500)
    }
}
