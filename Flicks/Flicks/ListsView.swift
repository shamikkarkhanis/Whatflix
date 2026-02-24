import SwiftUI

struct ListsView: View {
    @EnvironmentObject var userState: UserState

    @State private var showCreateAlert = false
    @State private var newListName = ""
    @State private var renamingList: CustomMovieList?
    @State private var renameListName = ""

    var body: some View {
        NavigationStack {
            List {
                if userState.customLists.isEmpty {
                    ContentUnavailableView(
                        "No Lists Yet",
                        systemImage: "list.bullet.rectangle",
                        description: Text("Create a custom list and start saving movies by theme, mood, or occasion.")
                    )
                } else {
                    ForEach(userState.customLists) { list in
                        NavigationLink(destination: CustomListDetailView(listId: list.id)) {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(list.name)
                                        .font(.headline)
                                    Text("\(list.movies.count) movies")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .font(.caption)
                                    .foregroundStyle(.tertiary)
                            }
                        }
                        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                            Button(role: .destructive) {
                                Task { await userState.deleteCustomList(listId: list.id) }
                            } label: {
                                Label("Delete", systemImage: "trash")
                            }

                            Button {
                                renamingList = list
                                renameListName = list.name
                            } label: {
                                Label("Rename", systemImage: "pencil")
                            }
                            .tint(.blue)
                        }
                    }
                }
            }
            .navigationTitle("Lists")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        newListName = ""
                        showCreateAlert = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .task {
                await userState.fetchCustomLists()
            }
            .refreshable {
                await userState.fetchCustomLists()
            }
            .alert("New List", isPresented: $showCreateAlert) {
                TextField("List name", text: $newListName)
                Button("Create") {
                    let name = newListName.trimmingCharacters(in: .whitespacesAndNewlines)
                    guard !name.isEmpty else { return }
                    Task { _ = await userState.createCustomList(name: name) }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("Create a private custom list.")
            }
            .alert(
                "Rename List",
                isPresented: Binding(
                    get: { renamingList != nil },
                    set: { if !$0 { renamingList = nil } }
                ),
                presenting: renamingList
            ) { list in
                TextField("List name", text: $renameListName)
                Button("Save") {
                    let name = renameListName.trimmingCharacters(in: .whitespacesAndNewlines)
                    guard !name.isEmpty else { return }
                    Task { await userState.renameCustomList(listId: list.id, name: name) }
                }
                Button("Cancel", role: .cancel) {}
            } message: { _ in
                Text("Update the list name.")
            }
        }
    }
}

#Preview {
    ListsView()
        .environmentObject(UserState())
}
