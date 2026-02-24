//
//  MenuButton.swift
//  Flicks
//
//  Created by Shamik Karkhanis on 1/5/26.
//

import SwiftUI

struct MenuButton: View {
    let currentTitle: String
    @State private var isExpanded = false
    
    var body: some View {
        ZStack(alignment: .bottom) {
            // Background dimmer
            if isExpanded {
                Color.black.opacity(0.01) // Invisible but captures taps
                    .ignoresSafeArea()
                    .onTapGesture {
                        withAnimation(.spring(response: 0.4, dampingFraction: 0.6)) {
                            isExpanded = false
                        }
                    }
            }
            
            VStack(spacing: 12) {
                if isExpanded {
                    // Option 1: Profile
                    NavigationLink(destination: ProfileView()) {
                        MenuPill(icon: "person.crop.circle.fill", title: "Profile")
                    }
                    .transition(
                        .asymmetric(
                            insertion: .move(edge: .bottom).combined(with: .opacity).combined(with: .scale(scale: 0.5)),
                            removal: .move(edge: .bottom).combined(with: .opacity).combined(with: .scale(scale: 0.5))
                        )
                    )
                    .zIndex(2)
                    
                    // Option 2: Watchlist
                    NavigationLink(destination: WatchlistView()) {
                        MenuPill(icon: "bookmark.fill", title: "Watchlist")
                    }
                    .transition(
                        .asymmetric(
                            insertion: .move(edge: .bottom).combined(with: .opacity).combined(with: .scale(scale: 0.5)),
                            removal: .move(edge: .bottom).combined(with: .opacity).combined(with: .scale(scale: 0.5))
                        )
                    )
                    .zIndex(1)

                    NavigationLink(destination: ListsView()) {
                        MenuPill(icon: "list.bullet.rectangle", title: "Lists")
                    }
                    .transition(
                        .asymmetric(
                            insertion: .move(edge: .bottom).combined(with: .opacity).combined(with: .scale(scale: 0.5)),
                            removal: .move(edge: .bottom).combined(with: .opacity).combined(with: .scale(scale: 0.5))
                        )
                    )
                    .zIndex(0)
                }
                
                // Main Toggle Pill
                Button(action: toggleMenu) {
                    HStack(spacing: 6) {
                        Text(currentTitle)
                            .font(.system(size: 18, weight: .bold))
                    }
                    .foregroundColor(.white)
                    .padding(.horizontal, 18)
                    .padding(.vertical, 10)
                    .glassEffect()
                }
                .overlay(
                    Color.clear
                        .padding(80)
                        .contentShape(Rectangle())
                        .onTapGesture(perform: toggleMenu)
                )
                .buttonStyle(BouncyButtonStyle())
                .zIndex(-1)
            }
            .padding(.bottom, 10)
        }
        .frame(maxWidth: .infinity, alignment: .bottom)
        .animation(.spring(response: 0.4, dampingFraction: 0.6), value: isExpanded)
    }

    private func toggleMenu() {
        withAnimation(.spring(response: 0.4, dampingFraction: 0.6)) {
            isExpanded.toggle()
        }
    }
}

struct MenuPill: View {
    let icon: String
    let title: String
    
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 18, weight: .semibold))
            
            Text(title)
                .font(.system(size: 18, weight: .semibold))
        }
        .foregroundColor(.white)
        .padding(.horizontal, 18)
        .padding(.vertical, 12)
        .glassEffect()
    }
}

struct BouncyButtonStyle: ButtonStyle {
    func makeBody(configuration: ButtonStyle.Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.9 : 1.0)
            .animation(.spring(response: 0.3, dampingFraction: 0.5), value: configuration.isPressed)
    }
}

#Preview {
    ZStack(alignment: .bottom) {
        Color.blue.opacity(0.8)
            .ignoresSafeArea()
        
        MenuButton(currentTitle: "For You")
    }
}
