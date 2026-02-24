import SwiftUI

struct CustomListDetailView: View {
    let listId: String

    @EnvironmentObject var userState: UserState
    @State private var selectedMovie: Movie?

    private var currentList: CustomMovieList? {
        userState.customLists.first(where: { $0.id == listId })
    }

    var body: some View {
        List {
            if let list = currentList {
                if list.movies.isEmpty {
                    ContentUnavailableView(
                        "No Movies Yet",
                        systemImage: "film.stack",
                        description: Text("Add movies from the movie detail sheet.")
                    )
                } else {
                    ForEach(list.movies) { movie in
                        Button {
                            selectedMovie = movie
                        } label: {
                            HStack(spacing: 12) {
                                AsyncImage(url: URL(string: movie.imageName)) { phase in
                                    switch phase {
                                    case .success(let image):
                                        image.resizable().scaledToFill()
                                    case .failure:
                                        Color.gray.opacity(0.3)
                                    case .empty:
                                        Color.gray.opacity(0.2)
                                    @unknown default:
                                        Color.gray.opacity(0.2)
                                    }
                                }
                                .frame(width: 72, height: 48)
                                .clipShape(RoundedRectangle(cornerRadius: 8))

                                VStack(alignment: .leading, spacing: 4) {
                                    Text(movie.title)
                                        .font(.headline)
                                        .lineLimit(2)
                                    Text(movie.subtitle)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                        .lineLimit(1)
                                }
                                Spacer()
                            }
                        }
                        .buttonStyle(.plain)
                        .swipeActions(edge: .trailing) {
                            Button(role: .destructive) {
                                Task { await userState.removeMovie(movie, fromCustomList: listId) }
                            } label: {
                                Label("Remove", systemImage: "trash")
                            }
                        }
                    }
                }
            } else {
                ProgressView("Loading list...")
                    .frame(maxWidth: .infinity, alignment: .center)
            }
        }
        .navigationTitle(currentList?.name ?? "List")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await userState.fetchCustomListDetail(listId: listId)
        }
        .refreshable {
            await userState.fetchCustomListDetail(listId: listId)
        }
        .sheet(item: $selectedMovie) { movie in
            MovieDetailView(
                movie: movie,
                title: movie.title,
                subtitle: movie.subtitle,
                imageName: movie.imageName,
                friendInitials: movie.friendInitials
            )
            .environmentObject(userState)
            .presentationDetents([.large, .large])
            .presentationDragIndicator(.visible)
        }
    }
}

#Preview {
    NavigationStack {
        CustomListDetailView(listId: "preview")
            .environmentObject(UserState())
    }
}
