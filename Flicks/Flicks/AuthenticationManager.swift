import Foundation
import AuthenticationServices
import Security
import UIKit
import SwiftUI

@MainActor
class AuthenticationManager: NSObject, ObservableObject {
    @Published var isAuthenticated: Bool = false
    @Published var isLoading: Bool = false
    @Published var error: Error?
    
    @AppStorage("authenticatedUserId") private var authenticatedUserId: String?
    
    private let tokenKey = "com.flicks.sessionToken"
    
    override init() {
        super.init()
        self.isAuthenticated = getToken() != nil
    }
    
    func handleSignInWithApple() {
        let appleIDProvider = ASAuthorizationAppleIDProvider()
        let request = appleIDProvider.createRequest()
        request.requestedScopes = [.fullName, .email]
        
        let authorizationController = ASAuthorizationController(authorizationRequests: [request])
        authorizationController.delegate = self
        authorizationController.presentationContextProvider = self
        authorizationController.performRequests()
    }
    
    func handleAuthorization(_ authorization: ASAuthorization) {
        processAuthorization(authorization)
    }
    
    func loginAsDev() {
        guard Configuration.isDevelopmentMode else { return }
        saveToken("dev-session-token")
        authenticatedUserId = Configuration.devUserId
        isAuthenticated = true
    }
    
    func signOut() {
        deleteToken()
        authenticatedUserId = nil
        isAuthenticated = false
    }
    
    private func processAuthorization(_ authorization: ASAuthorization) {
        guard let appleIDCredential = authorization.credential as? ASAuthorizationAppleIDCredential,
              let identityToken = appleIDCredential.identityToken,
              let idTokenString = String(data: identityToken, encoding: .utf8) else {
            return
        }
        
        Task {
            do {
                isLoading = true
                try await sendToBackend(idToken: idTokenString, credential: appleIDCredential)
                isLoading = false
            } catch {
                self.error = error
                isLoading = false
            }
        }
    }
    
    // MARK: - Keychain Helpers
    
    private func saveToken(_ token: String) {
        let data = Data(token.utf8)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: tokenKey,
            kSecValueData as String: data
        ]
        
        SecItemDelete(query as CFDictionary)
        let status = SecItemAdd(query as CFDictionary, nil)
        if status != errSecSuccess {
            print("Keychain save error: \(status)")
        }
    }
    
    func getToken() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: tokenKey,
            kSecValueData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        
        var dataTypeRef: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &dataTypeRef)
        
        if status == errSecSuccess, let data = dataTypeRef as? Data {
            return String(data: data, encoding: .utf8)
        }
        return nil
    }
    
    private func deleteToken() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: tokenKey
        ]
        SecItemDelete(query as CFDictionary)
    }
}

extension AuthenticationManager: ASAuthorizationControllerDelegate {
    func authorizationController(controller: ASAuthorizationController, didCompleteWithAuthorization authorization: ASAuthorization) {
        processAuthorization(authorization)
    }
    
    func authorizationController(controller: ASAuthorizationController, didCompleteWithError error: Error) {
        self.error = error
    }
    
    private func sendToBackend(idToken: String, credential: ASAuthorizationAppleIDCredential) async throws {
        guard let url = URL(string: "\(Configuration.backendURL)/auth/apple") else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        var fullNameDict: [String: String]?
        if let fullName = credential.fullName {
            var nameComponents: [String: String] = [:]
            if let givenName = fullName.givenName {
                nameComponents["givenName"] = givenName
            }
            if let familyName = fullName.familyName {
                nameComponents["familyName"] = familyName
            }
            if !nameComponents.isEmpty {
                fullNameDict = nameComponents
            }
        }
        
        var body: [String: Any] = ["identityToken": idToken]
        
        if let email = credential.email {
            body["email"] = email
        }
        
        if let fullName = fullNameDict {
            body["fullName"] = fullName
        }
        
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw NSError(domain: "Auth", code: 1, userInfo: [NSLocalizedDescriptionKey: "Backend authentication failed"])
        }
        
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let sessionToken = json["token"] as? String {
            saveToken(sessionToken)
            if let userObj = json["user"] as? [String: Any],
               let userId = userObj["id"] as? String {
                authenticatedUserId = userId
            }
            isAuthenticated = true
        }
    }
}

extension AuthenticationManager: ASAuthorizationControllerPresentationContextProviding {
    func presentationAnchor(for controller: ASAuthorizationController) -> ASPresentationAnchor {
        let scenes = UIApplication.shared.connectedScenes
        let windowScene = scenes.first as? UIWindowScene
        return windowScene?.windows.first { $0.isKeyWindow } ?? UIWindow()
    }
}
