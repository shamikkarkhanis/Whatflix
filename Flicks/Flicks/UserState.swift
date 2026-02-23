import SwiftUI

@MainActor
class UserState: ObservableObject {
    @Published var profileName: String = ""
    @Published var history: [Movie] = []
    @Published var watchlist: [Movie] = []
    @Published var genres: [String] = []
    @Published var recommendations: [Movie] = []
    @Published var personas: [OnboardingView.Persona] = []
    
    @Published var likedMovies: [Movie] = []
    @Published var neutralMovies: [Movie] = []
    @Published var dislikedMovies: [Movie] = []
    
    // Computed properties for queue visualization
    var queueCount: Int {
        recommendations.count
    }
    
    var bufferCount: Int {
        max(0, allFetchedMovies.count - recommendations.count)
    }
    
    var shownCount: Int = 0 // Tracks how many movies the user has scrolled past in this session
    
    private var allFetchedMovies: [Movie] = []
    @AppStorage("authenticatedUserId") private var currentUserId: String = ""
    private var ratingSessionCount = 0
    private var shownMovieIds: Set<Int> = []
    
    private var isLoading = false
    private var isProcessingQueue = false
    
    // Retry Queue Definitions
    enum PendingAction {
        case rate(movieId: Int, rating: String, movieTitle: String)
        case watchlistAdd(movieId: Int, movieTitle: String)
        case watchlistRemove(movieId: Int, movieTitle: String)
        case syncShown(movieIds: [Int])
    }
    
    private let pendingActions = PendingActionsQueue()

    private var activeUserId: String? {
        let trimmed = currentUserId.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    init() {
        Task {
            await fetchUserProfile()
            await fetchPersonas()
        }
    }
    
    private func processPendingActions() {
        guard !isProcessingQueue else { return }
        
        Task {
            guard let userId = activeUserId else { return }
            guard await !pendingActions.isEmpty else { return }
            isProcessingQueue = true
            
            print("[RetryQueue] Processing pending actions...")
            
            while await !pendingActions.isEmpty {
                guard let action = await pendingActions.peek() else { break }
                
                do {
                    switch action {
                    case .rate(let movieId, let rating, let title):
                        print("[RetryQueue] Retrying rating for '\(title)'...")
                        try await APIService.shared.rateMovie(userId: userId, movieId: movieId, rating: rating)
                        ratingSessionCount += 1
                        if ratingSessionCount % 3 == 0 {
                            print("[RetryQueue] Triggering refill fetch from queued rating...")
                            await fetchRecommendations(isLiveRefill: true)
                        }
                        
                    case .watchlistAdd(let movieId, let title):
                        print("[RetryQueue] Retrying watchlist add for '\(title)'...")
                        try await APIService.shared.addToWatchlist(userId: userId, movieId: movieId)
                        
                    case .watchlistRemove(let movieId, let title):
                        print("[RetryQueue] Retrying watchlist remove for '\(title)'...")
                        try await APIService.shared.removeFromWatchlist(userId: userId, movieId: movieId)
                        
                    case .syncShown(let movieIds):
                        print("[RetryQueue] Retrying sync for \(movieIds.count) shown movies...")
                        try await APIService.shared.syncShownMovies(userId: userId, movieIds: movieIds)
                    }
                    
                    print("[RetryQueue] Action successful. Removing from queue.")
                    await pendingActions.removeFirst()
                    
                } catch {
                    print("[RetryQueue] Action failed: \(error). Pausing queue.")
                    isProcessingQueue = false
                    return
                }
            }
            
            print("[RetryQueue] Queue emptied.")
            isProcessingQueue = false
        }
    }
    
    @Published var hasCompletedOnboarding: Bool = false
    
    func fetchUserProfile() async -> Bool {
        guard let userId = activeUserId else { return false }
        do {
            let profile = try await APIService.shared.fetchUserProfile(for: userId)
            
            print("Profile fetched: \(profile.name)")
            self.profileName = profile.name
            
            // Check if user has completed onboarding (has personas)
            let hasPersonas = !(profile.personas?.isEmpty ?? true)
            self.hasCompletedOnboarding = hasPersonas
            
            // 1. Collect all IDs that need hydration
            var allIds: Set<Int> = []
            allIds.formUnion(profile.data.watchlist)
            allIds.formUnion(profile.data.history)
            allIds.formUnion(profile.data.liked)
            allIds.formUnion(profile.data.disliked)
            allIds.formUnion(profile.data.neutral)
            
            // 2. Fetch full movie details if we have any IDs
            if !allIds.isEmpty {
                do {
                    let movieDTOs = try await APIService.shared.fetchMovies(ids: Array(allIds))
                    
                    // Map DTOs to Domain Objects
                    let movieMap = Dictionary(uniqueKeysWithValues: movieDTOs.compactMap { dto -> (Int, Movie)? in
                        guard let backdrop = dto.backdrop_path, !backdrop.isEmpty else { return nil }
                        let id = Int(dto.movie_id) ?? 0
                        let movie = Movie(
                            tmdbId: id,
                            title: dto.title,
                            subtitle: dto.genres?.joined(separator: " · ") ?? "Movie",
                            imageName: "https://image.tmdb.org/t/p/original\(backdrop)",
                            friendInitials: [],
                            dateAdded: Date(),
                            dateWatched: Date()
                        )
                        return (id, movie)
                    })
                    
                    // 3. Hydrate Lists
                    self.watchlist = profile.data.watchlist.compactMap { movieMap[$0] }
                    self.history = profile.data.history.compactMap { movieMap[$0] }
                    self.likedMovies = profile.data.liked.compactMap { movieMap[$0] }
                    self.dislikedMovies = profile.data.disliked.compactMap { movieMap[$0] }
                    self.neutralMovies = profile.data.neutral.compactMap { movieMap[$0] }
                    
                    self.rebuildGenres()
                    print("Profile hydrated: \(self.watchlist.count) watchlist, \(self.history.count) history")
                } catch {
                    print("Failed to hydrate movie details: \(error)")
                }
            }
            
            // For now, we assume we want to fetch recommendations immediately after profile load
            // if the list is empty
            if recommendations.isEmpty {
                await fetchRecommendations()
            }
            return true
        } catch {
            print("Failed to fetch user profile: \(error)")
            if profileName.isEmpty {
                profileName = userId
            }
            // Fallback: fetch recommendations anyway
            if recommendations.isEmpty {
                 await fetchRecommendations()
            }
            return false
        }
    }
    
    func fetchPersonas() async {
        do {
            let dtos = try await APIService.shared.fetchPersonas()
            self.personas = dtos.map { dto in
                OnboardingView.Persona(
                    title: dto.title,
                    description: dto.description,
                    color: self.mapColor(dto.color),
                    icon: dto.icon,
                    image: dto.image
                )
            }
        } catch {
            print("Failed to fetch personas: \(error)")
        }
    }

    private func mapColor(_ name: String) -> Color {
        switch name {
        case "red": return .red
        case "purple": return .purple
        case "blue": return .blue
        case "pink": return .pink
        case "orange": return .orange
        case "green": return .green
        case "yellow": return .yellow
        default: return .gray
        }
    }
    
    // MARK: - Watchlist Management
    
    func addToWatchlist(_ movie: Movie) {
        // Optimistic UI Update
        if !watchlist.contains(where: { $0.id == movie.id }) {
            var newMovie = movie
            newMovie.dateAdded = Date()
            watchlist.append(newMovie)
        }
        
        // Queue Action
        Task {
            await pendingActions.enqueue(.watchlistAdd(movieId: movie.tmdbId, movieTitle: movie.title))
            processPendingActions()
        }
    }

    func removeFromWatchlist(_ movie: Movie) {
        // Optimistic UI Update
        watchlist.removeAll { $0.id == movie.id }
        
        // Queue Action
        Task {
            await pendingActions.enqueue(.watchlistRemove(movieId: movie.tmdbId, movieTitle: movie.title))
            processPendingActions()
        }
    }
    
    // MARK: - Rating & History
    
    enum UserRating {
        case like, neutral, dislike
        
        var apiString: String {
            switch self {
            case .like: return "like"
            case .neutral: return "neutral"
            case .dislike: return "dislike"
            }
        }
    }

    func addToHistory(_ movie: Movie, rating: UserRating) async {
        // 1. Optimistic UI Updates
        if !history.contains(where: { $0.id == movie.id }) {
            var newMovie = movie
            newMovie.dateWatched = Date()
            history.append(newMovie)
        }
        
        likedMovies.removeAll { $0.id == movie.id }
        neutralMovies.removeAll { $0.id == movie.id }
        dislikedMovies.removeAll { $0.id == movie.id }
        
        switch rating {
        case .like:
            likedMovies.append(movie)
        case .neutral:
            neutralMovies.append(movie)
        case .dislike:
            dislikedMovies.append(movie)
        }
        
        rebuildGenres()
        
        // 2. Queue Action & Process
        print("[LiveRecs] Queuing rating for '\(movie.title)' as \(rating.apiString)...")
        await pendingActions.enqueue(.rate(movieId: movie.tmdbId, rating: rating.apiString, movieTitle: movie.title))
        processPendingActions()
    }
    
    func removeFromHistory(_ movie: Movie) {
        history.removeAll { $0.id == movie.id }
        likedMovies.removeAll { $0.id == movie.id }
        neutralMovies.removeAll { $0.id == movie.id }
        dislikedMovies.removeAll { $0.id == movie.id }
        
        rebuildGenres()
    }

    private func rebuildGenres() {
        var newGenres: Set<String> = []
        for movie in likedMovies {
            let list = movie.subtitle.components(separatedBy: " · ")
            for genre in list {
                let trimmed = genre.trimmingCharacters(in: .whitespaces)
                if !trimmed.isEmpty {
                    newGenres.insert(trimmed)
                }
            }
        }
        self.genres = Array(newGenres).sorted()
    }

    // MARK: - Profile Sync & Recommendations

    func syncUserProfile(personas: [String] = []) async {
        guard let userId = activeUserId else { return }
        do {
            print("[LiveRecs] Performing bulk profile sync...")
            // 1. Upload the entire local state to create/reset the profile on the backend
            try await APIService.shared.createProfile(name: userId, genres: genres, movies: history, personas: personas)
            print("[LiveRecs] Profile bulk sync successful.")
            
            // 2. Fetch fresh recommendations based on the new profile
            await fetchRecommendations()
        } catch {
            print("[LiveRecs] Failed to sync user profile: \(error)")
        }
    }
    
    func fetchRecommendations(isLiveRefill: Bool = false) async {
        guard let userId = activeUserId else { return }
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }
        
        print("[LiveRecs] Fetching recommendations (Live Refill: \(isLiveRefill))...")
        do {
            let fetchedMovies = try await APIService.shared.getRecommendations(for: userId)
            
            if isLiveRefill {
                print("[LiveRecs] Received \(fetchedMovies.count) candidates.")
                // Smart Deduplication:
                // 1. Filter out movies the user has already seen/rated/watchlisted locally
                // 2. Filter out movies already in the current recommendations list
                var existingIds: Set<Int> = []
                existingIds.formUnion(history.map { $0.tmdbId })
                existingIds.formUnion(watchlist.map { $0.tmdbId })
                existingIds.formUnion(recommendations.map { $0.tmdbId })
                existingIds.formUnion(shownMovieIds)
                
                let newUniqueMovies = fetchedMovies.filter { !existingIds.contains($0.tmdbId) }
                let duplicateCount = fetchedMovies.count - newUniqueMovies.count
                print("[LiveRecs] Deduped \(duplicateCount) movies (already seen/listed).")
                
                if !newUniqueMovies.isEmpty {
                    print("[LiveRecs] Added \(newUniqueMovies.count) new unique movies to buffer.")
                    // Append to the buffer (allFetchedMovies), NOT directly to recommendations.
                    // loadMoreMovies() will handle moving them to the active view if needed.
                    self.allFetchedMovies.append(contentsOf: newUniqueMovies)
                    
                    // Trigger loadMoreMovies to update the UI if the user was waiting at the bottom
                    // or to just log the new status.
                    self.loadMoreMovies()
                } else {
                    print("[LiveRecs] No new unique movies found to add.")
                }
                
            } else {
                // Fresh Load (Replace)
                // Ensure we don't accidentally replace with empty if there's an error, 
                // but here we are in success path.
                print("[LiveRecs] Fresh load complete. Replaced list with \(fetchedMovies.count) movies.")
                self.allFetchedMovies = fetchedMovies
                
                // Initial page size
                self.recommendations = Array(fetchedMovies.prefix(10))
                self.printQueueStatus()
            }
        } catch {
            print("[LiveRecs] Failed to fetch recommendations: \(error)")
        }
    }
    
    func markAsShown(_ movie: Movie) {
        // Only track if not already tracked
        if !shownMovieIds.contains(movie.tmdbId) {
            shownMovieIds.insert(movie.tmdbId)
            shownCount += 1 // Increment session counter
            // print("[LiveRecs] Marked '\(movie.title)' as shown. Total shown: \(shownCount)")
            
            // Sync if we have accumulated enough shown movies (e.g., 3)
            if shownMovieIds.count >= 3 {
                flushShownMovies()
            }
        }
    }

    private func flushShownMovies() {
        let idsToSync = Array(shownMovieIds)
        guard !idsToSync.isEmpty else { return }
        
        shownMovieIds.removeAll()
        
        print("[LiveRecs] Queuing sync for \(idsToSync.count) shown IDs...")
        Task {
            await pendingActions.enqueue(.syncShown(movieIds: idsToSync))
            processPendingActions()
        }
    }
    
    private func printQueueStatus() {
        let unseenInList = max(0, queueCount - shownCount)
        let totalMoviesLeft = unseenInList + bufferCount
        
        print("====== QUEUE STATUS ======")
        print("Total List Size (UI):   \(queueCount)")
        print("Movies Seen (Session):  \(shownCount)")
        print("--------------------------")
        print("Unseen in UI (approx):  \(unseenInList)")
        print("Buffer (Memory Only):   \(bufferCount)")
        print("--------------------------")
        print("TOTAL MOVIES LEFT:      \(totalMoviesLeft)")
        print("==========================")
    }
    
    func loadMoreMovies() {
        // Prevent re-entry if we are already dealing with a fetch that might update the list
        // However, loadMoreMovies primarily pages from memory.
        
        let currentCount = recommendations.count
        
        // If we are running low on buffered movies (less than 15 unseen left), sync and fetch more
        // Increased threshold to 15 to ensure we fetch BEFORE the user hits the wall.
        if allFetchedMovies.count - currentCount < 15 {
             print("[LiveRecs] Buffer low (\(allFetchedMovies.count - currentCount) left). Syncing and fetching more...")
             Task {
                 do {
                     // 1. Sync shown movies to backend
                     if !shownMovieIds.isEmpty {
                         flushShownMovies()
                     }
                     
                     // 2. Then fetch fresh ones
                     // We await this so it can update the buffer
                     await fetchRecommendations(isLiveRefill: true)
                 } catch {
                     print("[LiveRecs] Sync/Fetch failed: \(error)")
                 }
             }
        }
        
        // Only page from memory if we have more in the buffer than currently shown
        guard currentCount < allFetchedMovies.count else {
            printQueueStatus()
            return
        }
        
        // Ensure we don't grab an invalid range
        let remaining = allFetchedMovies.count - currentCount
        let batchSize = min(10, remaining)
        let nextBatch = allFetchedMovies[currentCount..<(currentCount + batchSize)]
        
        recommendations.append(contentsOf: nextBatch)
        print("[LiveRecs] Paged \(batchSize) movies from buffer.")
        printQueueStatus()
    }
}

actor PendingActionsQueue {
    private var actions: [UserState.PendingAction] = []
    
    func enqueue(_ action: UserState.PendingAction) {
        actions.append(action)
    }
    
    func peek() -> UserState.PendingAction? {
        actions.first
    }
    
    func removeFirst() {
        if !actions.isEmpty {
            actions.removeFirst()
        }
    }
    
    var isEmpty: Bool {
        actions.isEmpty
    }
}
