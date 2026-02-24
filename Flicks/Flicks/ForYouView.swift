import SwiftUI

struct ForYouView: View {
    @EnvironmentObject var userState: UserState
    
    private var movies: [Movie] {
        if !userState.recommendations.isEmpty {
            return userState.recommendations
        }
        return sampleMovies
    }

    // bind scroll position to a Movie.ID
    @State private var scrollPosition: Movie.ID?
    @State private var isSearching = false
    @State private var query = ""
    @State private var selectedVibes: Set<String> = []
    @State private var selectedMovie: Movie?   // controls detail presentation
    @State private var showRateMenu = false
    @State private var interactingMovie: Movie?

    private let vibes = ["Cozy", "Sci-Fi", "Epic", "Feel-good", "Dark", "Romantic", "Nostalgic"] // dynamic based on user history

    var body: some View {
        NavigationStack {
            ZStack(alignment: .top) {
                ScrollView(.vertical) {
                    LazyVStack(spacing: 0) {
                        ForEach(Array(movies.enumerated()), id: \.element.id) { index, movie in
                            let prevMovie = movies.indices.contains(index - 1) ? movies[index - 1] : nil
                            let nextMovie = movies.indices.contains(index + 1) ? movies[index + 1] : nil
                            
                            movieCard(for: movie, prevImage: prevMovie?.imageName, nextImage: nextMovie?.imageName)
                                .containerRelativeFrame([.horizontal, .vertical])
                                .onTapGesture {
                                    selectedMovie = movie
                                }
                                .onAppear {
                                    userState.markAsShown(movie)
                                    if movie.id == movies.last?.id {
                                        userState.loadMoreMovies()
                                    }
                                }
                        }
                    }
                    .scrollTargetLayout()
                }
                .scrollPosition(id: $scrollPosition)
                .scrollTargetBehavior(.paging)
                .scrollIndicators(.hidden)
                .ignoresSafeArea()
                .background(.black)
                .onAppear {
                    if scrollPosition == nil, let first = movies.first {
                        scrollPosition = first.id
                    }
                    if userState.recommendations.isEmpty {
                        Task {
                            await userState.fetchRecommendations()
                        }
                    }
                }
                
                // Watchlist Add Button & Rate Button
                if !showRateMenu, let currentId = scrollPosition ?? movies.first?.id, let currentMovie = movies.first(where: { $0.id == currentId }) {
                    VStack {
                        Spacer()
                        HStack {
                            RateTriggerButton(
                                rating: {
                                    if userState.likedMovies.contains(where: { $0.id == currentMovie.id }) { return .like }
                                    if userState.neutralMovies.contains(where: { $0.id == currentMovie.id }) { return .neutral }
                                    if userState.dislikedMovies.contains(where: { $0.id == currentMovie.id }) { return .dislike }
                                    return nil
                                }(),
                                action: {
                                    interactingMovie = currentMovie
                                    withAnimation(.spring()) {
                                        showRateMenu = true
                                    }
                                }
                            )
                            Spacer()
                            WatchlistButton(
                                isAdded: Binding(
                                    get: { userState.watchlist.contains(where: { $0.id == currentMovie.id }) },
                                    set: { added in
                                        if added {
                                            userState.addToWatchlist(currentMovie)
                                        } else {
                                            userState.removeFromWatchlist(currentMovie)
                                        }
                                    }
                                ),
                                action: {
                                    // Action handled in binding setter or here if specific trigger needed
                                }
                            )
                        }
                        .padding(.horizontal, 40)
                        .padding(.bottom, 14)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottom)
                    .transition(.opacity)
                    .zIndex(50)
                }
                
                // Rate Menu Overlay
                if showRateMenu {
                    RateMenu(
                        initialRating: {
                            guard let movie = interactingMovie else { return nil }
                            if userState.likedMovies.contains(where: { $0.id == movie.id }) { return .like }
                            if userState.neutralMovies.contains(where: { $0.id == movie.id }) { return .neutral }
                            if userState.dislikedMovies.contains(where: { $0.id == movie.id }) { return .dislike }
                            return nil
                        }(),
                        onDislike: {
                            if let movie = interactingMovie {
                                Task {
                                    await userState.addToHistory(movie, rating: .dislike)
                                }
                                print("Disliked \(movie.title)")
                            }
                        },
                        onNeutral: {
                            if let movie = interactingMovie {
                                Task {
                                    await userState.addToHistory(movie, rating: .neutral)
                                }
                                print("Neutral \(movie.title)")
                            }
                        },
                        onLike: {
                            if let movie = interactingMovie {
                                Task {
                                    await userState.addToHistory(movie, rating: .like)
                                }
                                print("Liked \(movie.title)")
                            }
                        },
                        onRemove: {
                            if let movie = interactingMovie {
                                userState.removeFromHistory(movie)
                                print("Removed rating for \(movie.title)")
                            }
                        },
                        onDismiss: {
                            withAnimation {
                                showRateMenu = false
                            }
                        }
                    )
                    .transition(.opacity)
                    .zIndex(100)
                }
                
                if !showRateMenu {
                    MenuButton(currentTitle: "For You")
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottom)
                        .padding(.bottom, 10)
                        .transition(.scale(scale: 0.8).combined(with: .opacity))
                }

                
                // "For You" Menu Button
                
                
//                SearchOverlay(
//                    isSearching: $isSearching,
//                    query: $query,
//                    selectedVibes: $selectedVibes,
//                    vibes: vibes
//                ) {
//                    // Handle search submit if needed
//                }
            }
        }
        .sheet(item: $selectedMovie) { movie in
            MovieDetailView(
                movie: movie,
                title: movie.title,
                subtitle: movie.subtitle,
                imageName: movie.imageName,
                friendInitials: movie.friendInitials
            )
            .presentationDetents([.large, .large])
            .presentationDragIndicator(.visible)
        }
    }

    @ViewBuilder
    private func movieCard(for movie: Movie, prevImage: String?, nextImage: String?) -> some View {
        GeometryReader { proxy in
            VerticalMovieCardView(
                title: movie.title,
                subtitle: movie.subtitle,
                imageName: movie.imageName,
                prevImageName: prevImage,
                nextImageName: nextImage,
                friendInitials: ["SK", "GJ", "CB"],
                disableDetail: false,
                dynamicFeathering: true,
                cardWidth: proxy.size.width,
                cardHeight: proxy.size.height,
                enableSwipe: false,
                cornerRadius: 0
            )
        }
        .id(movie.id)
    }
}

#Preview {
    ForYouView()
        .environmentObject(UserState())
}
