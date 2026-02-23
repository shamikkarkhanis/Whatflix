import Foundation

enum Configuration {
    private static let backendURLOverrideKey = "BACKEND_URL"

    static var isDevelopmentMode: Bool {
        #if DEBUG
        return true
        #else
        return false
        #endif
    }

    static var backendURL: String {
        #if DEBUG
        if let override = Bundle.main.object(forInfoDictionaryKey: backendURLOverrideKey) as? String,
           !override.isEmpty {
            return override
        }
        return "http://localhost:8000"
        #else
        return "https://api.flicks.app"
        #endif
    }

    static var devUserId: String {
        "dev-user"
    }
}
