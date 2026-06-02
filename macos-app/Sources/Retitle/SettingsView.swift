import SwiftUI

/// Visual editor for ``~/.config/retitle/config.toml``. Loads values on open,
/// writes back when the user clicks Save. We do not run any retitle command —
/// the daemon picks up changes on its next pass (poll_seconds default 60s).
struct SettingsView: View {
    @EnvironmentObject var state: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var values: ConfigStore.Values = .default
    @State private var loaded = false
    @State private var saveError: String?
    @State private var saveSuccess = false

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    section(LocalizedStringKey("settings_section_renaming")) {
                        intStepper(
                            label: LocalizedStringKey("settings_idle_seconds"),
                            help: LocalizedStringKey("settings_idle_seconds_help"),
                            value: $values.idleSeconds, range: 0...86400, step: 30,
                            displayFormat: secondsToHumanReadable
                        )
                        intStepper(
                            label: LocalizedStringKey("settings_min_user_messages"),
                            help: LocalizedStringKey("settings_min_user_messages_help"),
                            value: $values.minUserMessages, range: 0...20, step: 1,
                            displayFormat: { "\($0)" }
                        )
                        intStepper(
                            label: LocalizedStringKey("settings_max_age_days"),
                            help: LocalizedStringKey("settings_max_age_days_help"),
                            value: $values.maxAgeDays, range: 1...365, step: 1,
                            displayFormat: daysToHumanReadable
                        )
                    }
                    section(LocalizedStringKey("settings_section_daemon")) {
                        intStepper(
                            label: LocalizedStringKey("settings_poll_seconds"),
                            help: LocalizedStringKey("settings_poll_seconds_help"),
                            value: $values.pollSeconds, range: 5...3600, step: 10,
                            displayFormat: secondsToHumanReadable
                        )
                        intStepper(
                            label: LocalizedStringKey("settings_batch_size"),
                            help: LocalizedStringKey("settings_batch_size_help"),
                            value: $values.batchSize, range: 0...500, step: 5,
                            displayFormat: { $0 == 0 ? "∞" : "\($0)" }
                        )
                        Toggle(
                            LocalizedStringKey("settings_dry_run"),
                            isOn: $values.dryRun
                        )
                        .help(Text(LocalizedStringKey("settings_dry_run_help")))
                    }
                    section(LocalizedStringKey("settings_section_namer")) {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(LocalizedStringKey("settings_namer_help"))
                                .font(.caption).foregroundStyle(.secondary)
                            Picker(LocalizedStringKey("settings_namer"), selection: $values.namer) {
                                ForEach(ConfigStore.Values.allNamers, id: \.self) { n in
                                    Text(n).tag(n)
                                }
                            }
                            .pickerStyle(.segmented)
                            if let resolved = state.status?.namerResolved,
                               resolved != values.namer {
                                Text(
                                    String(
                                        format: NSLocalizedString(
                                            "settings_namer_resolved_%@", comment: ""
                                        ),
                                        resolved
                                    )
                                )
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            }
                        }
                    }
                    section(LocalizedStringKey("settings_section_tools")) {
                        VStack(alignment: .leading, spacing: 6) {
                            ForEach(ConfigStore.Values.allTools, id: \.self) { tool in
                                Toggle(
                                    labelFor(tool: tool),
                                    isOn: Binding(
                                        get: { values.tools.contains(tool) },
                                        set: { isOn in
                                            if isOn {
                                                if !values.tools.contains(tool) {
                                                    values.tools.append(tool)
                                                }
                                            } else {
                                                values.tools.removeAll { $0 == tool }
                                            }
                                        }
                                    )
                                )
                            }
                            Text(LocalizedStringKey("settings_tools_help"))
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
                .padding(24)
            }
            Divider()
            footer
        }
        .frame(width: 540, height: 620)
        .onAppear(perform: load)
    }

    private var footer: some View {
        HStack {
            if let err = saveError {
                Label(err, systemImage: "exclamationmark.triangle.fill")
                    .foregroundStyle(.red).lineLimit(2).font(.callout)
            } else if saveSuccess {
                Label(LocalizedStringKey("settings_saved"),
                      systemImage: "checkmark.seal.fill")
                    .foregroundStyle(.green).font(.callout)
            } else {
                Text(verbatim: ConfigStore.path.path)
                    .font(.caption).foregroundStyle(.secondary)
                    .lineLimit(1).truncationMode(.middle)
            }
            Spacer()
            Button(LocalizedStringKey("settings_revert")) {
                load()
                saveSuccess = false
                saveError = nil
            }
            .disabled(!loaded)
            Button(LocalizedStringKey("settings_save"), action: save)
                .keyboardShortcut(.defaultAction)
                .buttonStyle(.borderedProminent)
                .disabled(!loaded)
        }
        .padding(16)
    }

    // MARK: - actions -------------------------------------------------------

    private func load() {
        if let v = ConfigStore.load() {
            values = v
        } else {
            values = .default
        }
        loaded = true
        saveError = nil
        saveSuccess = false
    }

    private func save() {
        do {
            try ConfigStore.save(values)
            saveSuccess = true
            saveError = nil
            // Surface the new namer / tools in the rest of the UI.
            Task { await state.refreshStatusOnly() }
        } catch {
            saveError = error.localizedDescription
            saveSuccess = false
        }
    }

    // MARK: - building blocks ----------------------------------------------

    @ViewBuilder
    private func section<Content: View>(
        _ title: LocalizedStringKey,
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.headline)
            content()
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 10).fill(.quaternary.opacity(0.5))
        )
    }

    @ViewBuilder
    private func intStepper(
        label: LocalizedStringKey,
        help: LocalizedStringKey,
        value: Binding<Int>,
        range: ClosedRange<Int>,
        step: Int,
        displayFormat: @escaping (Int) -> String
    ) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(label)
                Spacer()
                Stepper(value: value, in: range, step: step) {
                    Text(displayFormat(value.wrappedValue))
                        .monospacedDigit()
                        .frame(minWidth: 70, alignment: .trailing)
                }
                .frame(width: 140)
            }
            Text(help).font(.caption).foregroundStyle(.secondary)
        }
    }

    private func labelFor(tool: String) -> String {
        switch tool {
        case "claude-code": return "Claude Code"
        case "codex":       return "Codex"
        case "cursor":      return "Cursor"
        case "antigravity": return "Antigravity"
        default:            return tool
        }
    }

    private func secondsToHumanReadable(_ n: Int) -> String {
        if n == 0 { return "0s" }
        if n < 60 { return "\(n)s" }
        if n < 3600 { return "\(n / 60)m \(n % 60)s".replacingOccurrences(of: " 0s", with: "") }
        let h = n / 3600
        let m = (n % 3600) / 60
        return m == 0 ? "\(h)h" : "\(h)h \(m)m"
    }

    private func daysToHumanReadable(_ n: Int) -> String {
        n == 1 ? "1 day" : "\(n) days"
    }
}

extension ConfigStore.Values {
    static var `default`: Self {
        .init(
            idleSeconds: 300,
            pollSeconds: 60,
            batchSize: 25,
            maxAgeDays: 7,
            minUserMessages: 1,
            namer: "auto",
            dryRun: false,
            tools: ["claude-code", "codex", "cursor"]
        )
    }
}
