import SwiftUI

struct MovieCardView: View {
    let title: String
    let subtitle: String
    let imageName: String
    let friendInitials: [String]
    let dateAdded: Date
    var disableDetail: Bool = false

    @State private var showDetail = false
    @State private var tapSpin = false

    var body: some View {
        Button {
            guard !disableDetail else { return }
            withAnimation(.snappy(duration: 0.25, extraBounce: 0.05)) {
                tapSpin = true
            }
            // Present after a short delay to let the tap spin play
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.18) {
                showDetail = true
                tapSpin = false
            }
        } label: {
            ZStack(alignment: .bottomLeading) {
                // Card image with bounded overlays
                Group {
                    if imageName.hasPrefix("http"), let url = URL(string: imageName) {
                        AsyncImage(url: url) { phase in
                            switch phase {
                            case .empty:
                                Color.gray.opacity(0.3)
                            case .success(let image):
                                image
                                    .resizable()
                                    .scaledToFill()
                            case .failure:
                                Color.gray
                            @unknown default:
                                Color.gray
                            }
                        }
                    } else {
                        Image(imageName)
                            .resizable()
                            .scaledToFill()
                    }
                }
                .aspectRatio(16.0 / 9.0, contentMode: .fit)
                .clipped()
                .cornerRadius(20)
                .shadow(radius: 10)
                // Place the date relative to the card/image bounds
                .overlay(alignment: .topTrailing) {
                    Text(formattedDate)
                        .font(.subheadline).bold()
                        .foregroundColor(.white)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .glassEffect()
                        .padding(10) // inset from the card’s corner
                }
                // Readability gradient
                .overlay(
                    LinearGradient(
                        gradient: Gradient(colors: [.black.opacity(0.6), .clear]),
                        startPoint: .bottom,
                        endPoint: .center
                    )
                    .cornerRadius(20)
                )

                // Bottom-left: title and subtitle within the card
                Section {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(title)
                            .font(.title)
                            .fontWeight(.bold)
                            .foregroundColor(.white)
                            .lineLimit(2)
                    }
                    .padding()
                }
            }
            .scaleEffect(tapSpin ? 0.98 : 1.0)
        }
        .buttonStyle(.plain)
        .sheet(isPresented: $showDetail) {
            MovieDetailView(
                movie: nil,
                title: title,
                subtitle: subtitle,
                imageName: imageName,
                friendInitials: friendInitials
            )
            .presentationDetents([.large, .large])
            .presentationDragIndicator(.visible)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title), \(subtitle)")
    }
}

private extension MovieCardView {
    var formattedDate: String {
        DateHelpers.formatDate(dateAdded)
    }
}

#Preview {
    MovieCardView(
        title: "Everything Everywhere All at Once",
        subtitle: "Action · Comedy · Sci‑Fi",
        imageName: "everything.jpg",
        friendInitials: ["SK", "FG"],
        dateAdded: Date()
    )
    .padding()
    .background(Color.black)
}
