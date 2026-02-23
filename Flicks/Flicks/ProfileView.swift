//
//  ProfileView.swift
//  Flicks
//
//  Created by Shamik Karkhanis on 11/24/25.
//

import SwiftUI
import UIKit

struct ProfileView: View {
    @EnvironmentObject var userState: UserState

    // Cache the gradient and colors so we don’t recompute during body updates
    @State private var backgroundGradient: LinearGradient?
    @State private var backgroundColors: [UIColor] = []

    // Centralized image load for downstream tasks
    private var uiImage: UIImage? {
        UIImage(named: "interstellar.jpg")
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Group {
                    if let gradient = backgroundGradient {
                        gradient
                    } else {
                        // Fallback while computing or if image/colors are unavailable
                        AppStyle.brandGradient
                    }
                }
                .ignoresSafeArea()

                ScrollView {
                    VStack(alignment: .leading, spacing: 24) {
                        header
                        genreSection
                        historySection
                    }
                    .padding(20)
                }
            }
            .navigationTitle("Profile")
            .navigationBarTitleDisplayMode(.inline)
            .onAppear {
                populateGradientIfNeeded()
            }
        }
    }

    private var header: some View {
        HStack(alignment: .center, spacing: 16) {
            ZStack {
                Circle()
                    .fill(.ultraThinMaterial)
                    .frame(width: 96, height: 96)
                    .overlay(
                        Circle()
                            .strokeBorder(.quaternary, lineWidth: 1)
                    )
                    .shadow(color: .black.opacity(0.08), radius: 12, x: 0, y: 8)

                // Placeholder profile image
                Image(systemName: "person.crop.circle.fill")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 64, height: 64)
                    .glassEffect()
            }

            VStack(alignment: .leading, spacing: 6) {
                Text(displayName)
                    .font(.system(size: 22, weight: .semibold))
                    .foregroundStyle(.primary)

                Text("Movie lover")
                    .font(.system(size: 15))
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var genreSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Genres")
                .font(.system(size: 18, weight: .semibold))
            
            if userState.genres.isEmpty {
                Text("Genres you like will appear here.")
                    .font(.system(size: 15))
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 8)
                
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 10) {
                    ForEach(userState.genres, id: \.self) { genre in
                        Text(genre)
                            .font(.system(size: 14, weight: .medium))
                            .padding(.horizontal, 16)
                            .padding(.vertical, 8)
                            .glassEffect(in: RoundedRectangle(cornerRadius: 14))
                    }
                }
                .padding(.horizontal, 20)
            }
            .padding(.horizontal, -20)
            .mask(
                LinearGradient(
                    gradient: Gradient(stops: [
                        .init(color: .clear, location: 0),
                        .init(color: .black, location: 0.05),
                        .init(color: .black, location: 0.95),
                        .init(color: .clear, location: 1)
                    ]),
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
        }
    }

    private var historySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("History")
                .font(.system(size: 18, weight: .semibold))

            if userState.history.isEmpty {
                Text("Your history is empty. Rate movies to add them here!")
                    .font(.system(size: 15))
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 8)
            } else {
                VStack(spacing: 10) {
                    ForEach(userState.history) { movie in
                        MovieCardMiniView(
                            title: movie.title,
                            dateWatched: movie.dateWatched ?? movie.dateAdded,
                            imageName: movie.imageName
                        )
                    }
                }
            }
        }
    }

    // MARK: - Helpers

    private var displayName: String {
        let trimmed = userState.profileName.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? "Profile" : trimmed
    }

    private func populateGradientIfNeeded() {
        // Only compute once per appearance unless you want it dynamic
        guard backgroundGradient == nil else { return }
        guard let uiImage else { return }

        if backgroundColors.isEmpty {
            backgroundColors = AppStyle.dominantColors(from: uiImage, sampleGrid: 4) ?? []
        }
        if !backgroundColors.isEmpty {
            backgroundGradient = AppStyle.gradient(from: backgroundColors)
        } else {
            backgroundGradient = AppStyle.brandGradient
        }
    }
}

#Preview {
    ProfileView()
        .environmentObject(UserState())
}
