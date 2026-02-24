import SwiftUI
import UIKit
import CoreGraphics

struct MovieDetailView: View {
    let movie: Movie? = nil
    let title: String
    let subtitle: String
    let imageName: String
    let friendInitials: [String]

    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var userState: UserState
    @State private var appearSpin = true
    @State private var showAddToListDialog = false
    @State private var showCreateListAlert = false
    @State private var newListName = ""

    // Cache the gradient so it doesn’t recompute often
    @State private var backgroundGradient: LinearGradient?
    
    // Cache primary colors for other uses
    @State private var backgroundColors: [UIColor] = []
    
    // Holds the image for both display and analysis
    @State private var loadedImage: UIImage?

    // A sensible maximum content width to avoid overly wide layouts on larger devices
    private let maxContentWidth: CGFloat = 700

    var body: some View {
        GeometryReader { proxy in
            let deviceWidth = proxy.size.width
            let contentWidth = min(deviceWidth, maxContentWidth)

            ZStack {
                // Background: gradient derived from the movie image colors
                Group {
                    if let gradient = backgroundGradient {
                        gradient
                            .ignoresSafeArea()
                    } else {
                        Color(.systemBackground).ignoresSafeArea()
                    }
                }

                ScrollView {
                    VStack {
                        // Constrain the entire card to contentWidth and center it
                        VStack(alignment: .leading, spacing: 16) {
                            if !imageName.isEmpty {
                                // Constrain the image to contentWidth and crop as needed
                                Group {
                                    if let uiImage = loadedImage {
                                        Image(uiImage: uiImage)
                                            .resizable()
                                            .scaledToFill()
                                            .frame(width: contentWidth - 32, height: 240)
                                            .clipped()
                                            .cornerRadius(16)
                                    } else {
                                        Color.gray.opacity(0.3)
                                            .frame(width: contentWidth - 32, height: 240)
                                            .cornerRadius(16)
                                            .overlay(ProgressView())
                                    }
                                }
                            }

                            Section {
                                // Card content
                                VStack(alignment: .leading, spacing: 16) {

                                    HStack {
                                        VStack(alignment: .leading, spacing: 6) {
                                            Text(title)
                                                .font(.title2).bold()
                                                .foregroundStyle(.primary)
                                            Text(subtitle)
                                                .font(.subheadline)
                                                .foregroundStyle(.secondary)
                                        }
                                        Spacer()
                                        Button {
                                            withAnimation(.snappy(duration: 0.3, extraBounce: 0.05)) {
                                                appearSpin = true
                                            }
                                            dismiss()
                                        } label: {
                                            Image(systemName: "xmark.circle.fill")
                                                .font(.system(size: 22, weight: .semibold))
                                                .foregroundStyle(.secondary)
                                        }
                                        .buttonStyle(.plain)
                                        .accessibilityLabel("Close")
                                    }

                                    VStack(alignment: .leading, spacing: 8) {
                                        Text("Ratings")
                                            .font(.headline)
                                        HStack(spacing: 12) {
                                            ratingBadge(title: "Critics", value: "92")
                                                .glassEffect(.regular.tint(Color(uiColor: backgroundColors[safe: 0] ?? .gray).opacity(0.6)))
                                            ratingBadge(title: "Audience", value: "89")
                                                .glassEffect(.regular.tint(Color(uiColor: backgroundColors[safe: 0] ?? .gray).opacity(0.6)))
                                            // ratingBadge(title: "Your Friends", value: "91")
                                            //    .glassEffect(.regular.tint(Color(uiColor: backgroundColors[safe: 0] ?? .gray).opacity(0.6)))
                                        }
                                    }

                                    VStack(alignment: .leading, spacing: 8) {
                                        Text("Why you’ll like this")
                                            .font(.headline)
                                        Text("Because you enjoyed mind-bending sci-fi with heartfelt characters and striking visuals. This pick matches your recent interest in ambitious, genre-mixing stories.")
                                            .font(.body)
                                            .foregroundStyle(.secondary)
                                    }

                                    if movie != nil {
                                        VStack(alignment: .leading, spacing: 10) {
                                            Text("Save")
                                                .font(.headline)
                                            Button {
                                                showAddToListDialog = true
                                            } label: {
                                                Label("Add to Custom List", systemImage: "list.bullet.badge.plus")
                                                    .frame(maxWidth: .infinity, alignment: .leading)
                                            }
                                            .buttonStyle(.borderedProminent)
                                        }
                                    }

                                    // VStack(alignment: .leading, spacing: 8) {
                                    //    Text("Friends")
                                    //        .font(.headline)
                                    //    ForEach(friendInitials, id: \.self) { initials in
                                    //        HStack(spacing: 12) {
                                    //            ZStack {
                                    //                Circle()
                                    //                    .frame(width: 32, height: 32)
                                    //                    .glassEffect()
                                    //                Text(initials)
                                    //                    .font(.caption2).bold()
                                    //            }
                                    //            Text("\(initials) rated it \(Int.random(in: 7...10))/10")
                                    //                .font(.subheadline)
                                    //        }
                                    //    }
                                    // }
                                }
                                .padding(20)
                            }
                            .glassEffect(.regular, in: RoundedRectangle(cornerRadius: 24))
                        }
                        // The internal padding around the card
                        .padding(16)
                        // Constrain and center the content
                        .frame(width: contentWidth, alignment: .center)
                    }
                    // Make the ScrollView take full width but center its content
                    .frame(maxWidth: .infinity)
                }
                // Spin-in effect for the presented view to simulate spinning from the card
                .rotation3DEffect(.degrees(appearSpin ? 90 : 0), axis: (x: 0, y: 1, z: 0), anchor: .center)
                .scaleEffect(appearSpin ? 0.9 : 1.0)
                .opacity(appearSpin ? 0.0 : 1.0)
                .onAppear {
                    withAnimation(.snappy(duration: 0.35, extraBounce: 0.05)) {
                        appearSpin = false
                    }
                    loadImageAndAnalyze()
                    if movie != nil, userState.customLists.isEmpty {
                        Task { await userState.fetchCustomLists() }
                    }
                }
                // If imageName can change while presented, recompute
                .onChange(of: imageName) { _ in
                    loadedImage = nil
                    backgroundColors.removeAll()
                    backgroundGradient = nil
                    loadImageAndAnalyze()
                }
                .confirmationDialog("Add to List", isPresented: $showAddToListDialog) {
                    if userState.customLists.isEmpty {
                        Button("Create New List") {
                            showCreateListAlert = true
                        }
                    } else {
                        ForEach(userState.customLists) { list in
                            Button(list.name) {
                                guard let movie else { return }
                                Task { await userState.addMovie(movie, toCustomList: list.id) }
                            }
                        }
                        Button("Create New List") {
                            showCreateListAlert = true
                        }
                    }
                    Button("Cancel", role: .cancel) {}
                } message: {
                    Text("Choose a list for this movie.")
                }
                .alert("Create New List", isPresented: $showCreateListAlert) {
                    TextField("List name", text: $newListName)
                    Button("Create") {
                        let trimmed = newListName.trimmingCharacters(in: .whitespacesAndNewlines)
                        guard !trimmed.isEmpty, let movie else { return }
                        Task {
                            if let newList = await userState.createCustomList(name: trimmed) {
                                await userState.addMovie(movie, toCustomList: newList.id)
                            }
                        }
                    }
                    Button("Cancel", role: .cancel) {}
                } message: {
                    Text("Create a private custom list and add this movie.")
                }
            }
        }
    }

    private func ratingBadge(title: String, value: String) -> some View {
        HStack(spacing: 6) {
            Text(value)
                .font(.headline).bold()
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(.ultraThinMaterial)
            .glassEffect()
        )
    }
}

// MARK: - Helpers

private extension MovieDetailView {
    func loadImageAndAnalyze() {
        if imageName.hasPrefix("http"), let url = URL(string: imageName) {
            Task {
                do {
                    let (data, _) = try await URLSession.shared.data(from: url)
                    if let image = UIImage(data: data) {
                        await MainActor.run {
                            self.loadedImage = image
                            analyzeColors(from: image)
                        }
                    }
                } catch {
                    print("Failed to load remote image: \(error)")
                }
            }
        } else {
            // Local image
            if let image = UIImage(named: imageName) {
                self.loadedImage = image
                analyzeColors(from: image)
            }
        }
    }

    func analyzeColors(from image: UIImage) {
        if backgroundColors.isEmpty {
            backgroundColors = AppStyle.dominantColors(from: image, sampleGrid: 4) ?? []
        }
        if backgroundGradient == nil, !backgroundColors.isEmpty {
            withAnimation {
                backgroundGradient = AppStyle.gradient(from: backgroundColors)
            }
        }
    }
}

// MARK: - Helpers

private extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}

#Preview {
    MovieDetailView(
        movie: nil,
        title: "Everything Everywhere All At Once",
        subtitle: "Action · Comedy · Sci‑Fi",
        imageName: "spiderverse.jpg",
        friendInitials: ["SK", "AB", "JK"]
    )
    .environmentObject(UserState())
}
