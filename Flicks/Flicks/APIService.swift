import Foundation

struct CreateUserProfileRequest: Codable {
    let name: String
    let genres: [String]
    let movie_ids: [Int]
    let personas: [String]?
}

struct WatchlistRequest: Codable {
    let movie_id: Int
}

struct RatingRequest: Codable {
    let movie_id: Int
    let rating: String
}

struct SyncShownRequest: Codable {
    let shown_ids: [Int]
}

struct BatchMoviesRequest: Codable {
    let movie_ids: [Int]
}

struct CreateCustomListRequest: Codable {
    let name: String
}

struct RenameCustomListRequest: Codable {
    let name: String
}

struct CustomListMovieRequest: Codable {
    let movie_id: Int
}

enum APIError: Error {
    case invalidURL
    case networkError(Error)
    case decodingError(Error)
    case serverError(statusCode: Int)
}

class APIService {
    static let shared = APIService()
    private var baseURL: String { Configuration.backendURL }

    private init() {}
    
    func fetchMovies(ids: [Int]) async throws -> [MovieDTO] {
        guard !ids.isEmpty else { return [] }
        
        guard let url = URL(string: "\(baseURL)/movies/batch") else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = BatchMoviesRequest(movie_ids: ids)
        request.httpBody = try JSONEncoder().encode(body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        if let httpResponse = response as? HTTPURLResponse,
           !(200...299).contains(httpResponse.statusCode) {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }
        
        return try JSONDecoder().decode([MovieDTO].self, from: data)
    }

    func createUserProfile(request: CreateUserProfileRequest) async throws {
        guard let url = URL(string: "\(baseURL)/encode") else {
            throw APIError.invalidURL
        }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

        do {
            let jsonData = try JSONEncoder().encode(request)
            urlRequest.httpBody = jsonData
        } catch {
            throw APIError.decodingError(error)
        }

        do {
            let (_, response) = try await URLSession.shared.data(for: urlRequest)
            
            if let httpResponse = response as? HTTPURLResponse,
               !(200...299).contains(httpResponse.statusCode) {
                throw APIError.serverError(statusCode: httpResponse.statusCode)
            }
        } catch {
            throw APIError.networkError(error)
        }
    }
    
    // Convenience method for domain objects
    func createProfile(name: String, genres: [String], movies: [Movie], personas: [String] = []) async throws {
        let request = CreateUserProfileRequest(
            name: name,
            genres: genres,
            movie_ids: movies.map { $0.tmdbId },
            personas: personas
        )
        try await createUserProfile(request: request)
    }

    // Alias for updating profile (same endpoint)
    func updateProfile(name: String, genres: [String], movies: [Movie]) async throws {
        try await createProfile(name: name, genres: genres, movies: movies)
    }

    func fetchRecommendations(for userId: String) async throws -> [MovieDTO] {
        guard let encodedUserId = userId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/users/\(encodedUserId)/recommendations?language=en") else {
            throw APIError.invalidURL
        }

        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            
            if let httpResponse = response as? HTTPURLResponse,
               !(200...299).contains(httpResponse.statusCode) {
                throw APIError.serverError(statusCode: httpResponse.statusCode)
            }
            
            let movies = try JSONDecoder().decode([MovieDTO].self, from: data)
            return movies
        } catch {
            print("Decoding error or network error: \(error)")
            throw error
        }
    }
    
    // Convenience method for domain objects
    func getRecommendations(for userId: String) async throws -> [Movie] {
        let dtos = try await fetchRecommendations(for: userId)
        return dtos.compactMap { dto in
            guard let backdropPath = dto.backdrop_path, !backdropPath.isEmpty else { return nil }
            return Movie(
                tmdbId: Int(dto.movie_id) ?? 0,
                title: dto.title,
                subtitle: dto.genres?.joined(separator: " · ") ?? "Recommended",
                imageName: "https://image.tmdb.org/t/p/original\(backdropPath)",
                friendInitials: [],
                dateAdded: Date(),
                dateWatched: Date()
            )
        }
    }

    func fetchUserProfile(for userId: String) async throws -> UserProfileDTO {
        guard let encodedUserId = userId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/users/\(encodedUserId)") else {
            throw APIError.invalidURL
        }

        let (data, response) = try await URLSession.shared.data(from: url)
        
        if let httpResponse = response as? HTTPURLResponse,
           !(200...299).contains(httpResponse.statusCode) {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }
        
        return try JSONDecoder().decode(UserProfileDTO.self, from: data)
    }
    
    func addToWatchlist(userId: String, movieId: Int) async throws {
        guard let encodedUserId = userId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/users/\(encodedUserId)/watchlist") else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = WatchlistRequest(movie_id: movieId)
        request.httpBody = try JSONEncoder().encode(body)
        
        let (_, response) = try await URLSession.shared.data(for: request)
        if let httpResponse = response as? HTTPURLResponse,
           !(200...299).contains(httpResponse.statusCode) {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }
    }

    func removeFromWatchlist(userId: String, movieId: Int) async throws {
        guard let encodedUserId = userId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/users/\(encodedUserId)/watchlist/\(movieId)") else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        
        let (_, response) = try await URLSession.shared.data(for: request)
        if let httpResponse = response as? HTTPURLResponse,
           !(200...299).contains(httpResponse.statusCode) {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }
    }

    func rateMovie(userId: String, movieId: Int, rating: String) async throws {
        guard let encodedUserId = userId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/users/\(encodedUserId)/ratings") else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = RatingRequest(movie_id: movieId, rating: rating)
        request.httpBody = try JSONEncoder().encode(body)
        
        let (_, response) = try await URLSession.shared.data(for: request)
        if let httpResponse = response as? HTTPURLResponse,
           !(200...299).contains(httpResponse.statusCode) {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }
    }

    func syncShownMovies(userId: String, movieIds: [Int]) async throws {
        guard let encodedUserId = userId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/users/\(encodedUserId)/sync") else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = SyncShownRequest(shown_ids: movieIds)
        request.httpBody = try JSONEncoder().encode(body)
        
        let (_, response) = try await URLSession.shared.data(for: request)
        if let httpResponse = response as? HTTPURLResponse,
           !(200...299).contains(httpResponse.statusCode) {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }
    }

    func fetchPersonas() async throws -> [PersonaDTO] {
        guard let url = URL(string: "\(baseURL)/onboarding/personas") else {
            throw APIError.invalidURL
        }

        let (data, response) = try await URLSession.shared.data(from: url)
        
        if let httpResponse = response as? HTTPURLResponse,
           !(200...299).contains(httpResponse.statusCode) {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }
        
        return try JSONDecoder().decode([PersonaDTO].self, from: data)
    }

    func fetchCustomLists(userId: String) async throws -> [CustomListSummaryDTO] {
        guard let encodedUserId = userId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/users/\(encodedUserId)/lists") else {
            throw APIError.invalidURL
        }

        let (data, response) = try await URLSession.shared.data(from: url)
        if let httpResponse = response as? HTTPURLResponse,
           !(200...299).contains(httpResponse.statusCode) {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }
        return try JSONDecoder().decode([CustomListSummaryDTO].self, from: data)
    }

    func fetchCustomList(userId: String, listId: String) async throws -> CustomListDetailDTO {
        guard let encodedUserId = userId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let encodedListId = listId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/users/\(encodedUserId)/lists/\(encodedListId)") else {
            throw APIError.invalidURL
        }

        let (data, response) = try await URLSession.shared.data(from: url)
        if let httpResponse = response as? HTTPURLResponse,
           !(200...299).contains(httpResponse.statusCode) {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }
        return try JSONDecoder().decode(CustomListDetailDTO.self, from: data)
    }

    func createCustomList(userId: String, name: String) async throws -> CustomListDetailDTO {
        guard let encodedUserId = userId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/users/\(encodedUserId)/lists") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(CreateCustomListRequest(name: name))

        let (data, response) = try await URLSession.shared.data(for: request)
        if let httpResponse = response as? HTTPURLResponse,
           !(200...299).contains(httpResponse.statusCode) {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }
        return try JSONDecoder().decode(CustomListDetailDTO.self, from: data)
    }

    func renameCustomList(userId: String, listId: String, name: String) async throws -> CustomListDetailDTO {
        guard let encodedUserId = userId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let encodedListId = listId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/users/\(encodedUserId)/lists/\(encodedListId)") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "PATCH"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(RenameCustomListRequest(name: name))

        let (data, response) = try await URLSession.shared.data(for: request)
        if let httpResponse = response as? HTTPURLResponse,
           !(200...299).contains(httpResponse.statusCode) {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }
        return try JSONDecoder().decode(CustomListDetailDTO.self, from: data)
    }

    func deleteCustomList(userId: String, listId: String) async throws {
        guard let encodedUserId = userId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let encodedListId = listId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/users/\(encodedUserId)/lists/\(encodedListId)") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"

        let (_, response) = try await URLSession.shared.data(for: request)
        if let httpResponse = response as? HTTPURLResponse,
           !(200...299).contains(httpResponse.statusCode) {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }
    }

    func addMovieToCustomList(userId: String, listId: String, movieId: Int) async throws -> CustomListMutationResponseDTO {
        guard let encodedUserId = userId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let encodedListId = listId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/users/\(encodedUserId)/lists/\(encodedListId)/movies") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(CustomListMovieRequest(movie_id: movieId))

        let (data, response) = try await URLSession.shared.data(for: request)
        if let httpResponse = response as? HTTPURLResponse,
           !(200...299).contains(httpResponse.statusCode) {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }
        return try JSONDecoder().decode(CustomListMutationResponseDTO.self, from: data)
    }

    func removeMovieFromCustomList(userId: String, listId: String, movieId: Int) async throws -> CustomListMutationResponseDTO {
        guard let encodedUserId = userId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let encodedListId = listId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/users/\(encodedUserId)/lists/\(encodedListId)/movies/\(movieId)") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"

        let (data, response) = try await URLSession.shared.data(for: request)
        if let httpResponse = response as? HTTPURLResponse,
           !(200...299).contains(httpResponse.statusCode) {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }
        return try JSONDecoder().decode(CustomListMutationResponseDTO.self, from: data)
    }
}

struct MovieDTO: Codable {
    let movie_id: String
    let title: String
    let genres: [String]?
    let score: Double?
    let backdrop_path: String?
}

struct PersonaDTO: Codable {
    let title: String
    let description: String
    let color: String
    let icon: String
    let image: String
}

struct UserProfileDTO: Codable {
    let name: String
    let genres: [String]?
    let movie_ids: [Int]?
    let data: UserDataDTO
    let personas: [String]?
}

struct UserDataDTO: Codable {
    let liked: [Int]
    let disliked: [Int]
    let neutral: [Int]
    let watchlist: [Int]
    let history: [Int]
}

struct CustomListSummaryDTO: Codable {
    let list_id: String
    let name: String
    let movie_count: Int
    let created_at: String
    let updated_at: String
}

struct CustomListDetailDTO: Codable {
    let list_id: String
    let name: String
    let movie_ids: [Int]
    let created_at: String
    let updated_at: String
}

struct CustomListMutationResponseDTO: Codable {
    let message: String
    let list: CustomListDetailDTO
}
