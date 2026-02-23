//
//  LoginView.swift
//  Flicks
//
//  Created by Gemini on 1/24/26.
//

import SwiftUI
import AuthenticationServices

struct LoginView: View {
    @EnvironmentObject var userState: UserState
    @EnvironmentObject var authManager: AuthenticationManager
    
    var body: some View {
        ZStack {
            // Background Image
            Image("interstellar.jpg")
                .resizable()
                .scaledToFill()
                .ignoresSafeArea()
            
            // Gradient Overlay
            LinearGradient(
                colors: [
                    .black.opacity(0.1),
                    .black.opacity(0.6),
                    .black
                ],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()
            
            VStack(spacing: 20) {
                Spacer()
                
                // App Title & Tagline
                VStack(spacing: 8) {
                    Text("Whatflix")
                        .font(.system(size: 48, weight: .black))
                        .foregroundColor(.white)
                    
                    Text("find. watch. share.")
                        .font(.title3)
                        .fontWeight(.medium)
                        .foregroundColor(.white.opacity(0.8))
                }
                .padding(.bottom, 20)
                
                // Sign in with Apple Button
                SignInWithAppleButton(
                    .signIn,
                    onRequest: { request in
                        request.requestedScopes = [.fullName, .email]
                    },
                    onCompletion: { result in
                        switch result {
                        case .success(let authorization):
                            authManager.handleAuthorization(authorization)
                        case .failure(let error):
                            authManager.error = error
                        }
                    }
                )
                .signInWithAppleButtonStyle(.white)
                .frame(maxWidth: 250)
                .frame(height: 50)
                .padding(.horizontal, 40)
                
                // Dev Login Button
                if Configuration.isDevelopmentMode {
                    Button(action: {
                        authManager.loginAsDev()
                    }) {
                        Text("Dev: Login as \(Configuration.devUserId)")
                            .font(.system(size: 16, weight: .medium))
                            .foregroundColor(.white.opacity(0.6))
                            .underline()
                    }
                    .padding(.top, 10)
                }
                
                Spacer()
                    .frame(height: 60)
            }
        }
        .onChange(of: authManager.isAuthenticated) { authenticated in
            if authenticated {
                Task {
                    await userState.fetchUserProfile()
                }
            }
        }
        .alert(item: Binding<ErrorAlert?>(
            get: { authManager.error.map { ErrorAlert(error: $0) } },
            set: { _ in authManager.error = nil }
        )) { alert in
            Alert(
                title: Text("Authentication Error"),
                message: Text(alert.error.localizedDescription),
                dismissButton: .default(Text("OK"))
            )
        }
        .overlay {
            if authManager.isLoading {
                ZStack {
                    Color.black.opacity(0.4)
                        .ignoresSafeArea()
                    ProgressView()
                        .tint(.white)
                        .scaleEffect(1.5)
                }
            }
        }
    }
}

struct ErrorAlert: Identifiable {
    let id = UUID()
    let error: Error
}

#Preview {
    LoginView()
        .environmentObject(UserState())
        .environmentObject(AuthenticationManager())
}
