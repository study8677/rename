import SwiftUI

/// In-app toast notifications. Used to surface friendly messages — "5 sessions
/// renamed", "Permission needed", etc. — without dumping raw stderr at the user.
@MainActor
final class ToastCenter: ObservableObject {
    @Published var current: Toast?

    func show(_ toast: Toast) {
        current = toast
        Task { [weak self] in
            try? await Task.sleep(nanoseconds: toast.duration * 1_000_000_000)
            await MainActor.run {
                if self?.current?.id == toast.id { self?.current = nil }
            }
        }
    }

    func info(_ message: String, duration: UInt64 = 3) {
        show(Toast(level: .info, message: message, duration: duration))
    }

    func success(_ message: String, duration: UInt64 = 3) {
        show(Toast(level: .success, message: message, duration: duration))
    }

    func warning(_ message: String, duration: UInt64 = 5) {
        show(Toast(level: .warning, message: message, duration: duration))
    }

    func error(_ message: String, duration: UInt64 = 6) {
        show(Toast(level: .error, message: message, duration: duration))
    }

    func dismiss() { current = nil }
}

struct Toast: Identifiable, Equatable {
    enum Level {
        case info, success, warning, error

        var icon: String {
            switch self {
            case .info:    return "info.circle.fill"
            case .success: return "checkmark.seal.fill"
            case .warning: return "exclamationmark.triangle.fill"
            case .error:   return "xmark.octagon.fill"
            }
        }
        var color: Color {
            switch self {
            case .info:    return .accentColor
            case .success: return .green
            case .warning: return .orange
            case .error:   return .red
            }
        }
    }
    let id = UUID()
    let level: Level
    let message: String
    let duration: UInt64    // seconds
}

struct ToastView: View {
    let toast: Toast
    let onClose: () -> Void

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: toast.level.icon)
                .foregroundStyle(toast.level.color)
            Text(verbatim: toast.message)
                .font(.callout)
                .lineLimit(3)
                .multilineTextAlignment(.leading)
            Spacer(minLength: 8)
            Button(action: onClose) {
                Image(systemName: "xmark").font(.caption)
            }
            .buttonStyle(.plain)
            .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 14).padding(.vertical, 10)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(.regularMaterial)
                .shadow(color: .black.opacity(0.18), radius: 12, x: 0, y: 4)
        )
        .frame(maxWidth: 420)
        .transition(.move(edge: .top).combined(with: .opacity))
    }
}

/// Overlay modifier — attach to the root view of a window.
struct ToastOverlayModifier: ViewModifier {
    @ObservedObject var center: ToastCenter

    func body(content: Content) -> some View {
        ZStack(alignment: .top) {
            content
            if let toast = center.current {
                ToastView(toast: toast) { center.dismiss() }
                    .padding(.top, 12)
                    .zIndex(10)
            }
        }
        .animation(.spring(response: 0.4, dampingFraction: 0.85), value: center.current)
    }
}

extension View {
    func toastOverlay(_ center: ToastCenter) -> some View {
        modifier(ToastOverlayModifier(center: center))
    }
}
