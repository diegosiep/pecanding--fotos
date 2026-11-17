import SwiftUI

@main
struct PecandingFotosApp: App {
    @StateObject private var store = ProjectStore()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(store)
                .frame(minWidth: 1100, minHeight: 700)
        }
    }
}
