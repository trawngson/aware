import Foundation

/// Where the community backend lives: a Supabase project URL and its public
/// anon (publishable) key, read from `BackendConfig.plist` in the app bundle.
///
/// Empty values mean there is no backend, and the app runs on its own exactly
/// as it did before the backend existed: nothing is signed in, synced or
/// fetched. The anon key is public by design; the service-role key must never
/// be put here.
struct BackendConfig: Equatable, Sendable {
    static let fileName = "BackendConfig"
    /// Launch argument (`-AWAREBackendDisabled YES`) that ignores the file,
    /// so UI tests never talk to a real project.
    static let disabledArgument = "AWAREBackendDisabled"

    let url: URL
    let anonKey: String

    init?(urlString: String?, anonKey: String?) {
        let urlString = urlString?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let anonKey = anonKey?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        guard !urlString.isEmpty, !anonKey.isEmpty,
              let url = URL(string: urlString),
              let scheme = url.scheme?.lowercased(), scheme == "https" || scheme == "http",
              url.host != nil else { return nil }
        self.url = url
        self.anonKey = anonKey
    }

    /// The bundle's configuration, or nil when there is none.
    static func load(from bundle: Bundle = .main, defaults: UserDefaults = .standard) -> BackendConfig? {
        if defaults.bool(forKey: disabledArgument) { return nil }
        guard let fileURL = bundle.url(forResource: fileName, withExtension: "plist"),
              let data = try? Data(contentsOf: fileURL) else { return nil }
        return parse(plist: data)
    }

    static func parse(plist data: Data) -> BackendConfig? {
        guard let values = try? PropertyListDecoder().decode([String: String].self, from: data) else { return nil }
        return BackendConfig(urlString: values["SupabaseURL"], anonKey: values["SupabaseAnonKey"])
    }
}
