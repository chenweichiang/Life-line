// LifeLineApp — SwiftUI App 進入點
// 啟動時自動初始化 Python AI 後端

import SwiftUI

@main
struct LifeLineApp: App {
    @StateObject private var backend = PythonBackend()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(backend)
                .onAppear {
                    backend.start()
                }
        }
        .windowStyle(.hiddenTitleBar)
        .defaultSize(width: 1100, height: 780)
        .commands {
            CommandGroup(replacing: .newItem) { }
        }
    }
}
