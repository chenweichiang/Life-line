// Data Models — 對應 Python API 的資料結構

import Foundation
import SwiftUI

// MARK: - API 請求

/// 情緒向量（對應 Python EmotionVector）
struct EmotionVector: Codable {
    var intensity: Double = 0.85
    var color_tone: String = "warm"
    var flow: String = "chaotic"
    var custom_prompt: String = ""
}

// MARK: - API 回應

struct GenerationResponse: Codable {
    let image_base64: String
    let prompt: String
}

// MARK: - 歷史記錄

struct GenerationRecord: Identifiable {
    let id = UUID()
    let prompt: String
    let image: NSImage
    let timestamp: Date
    let seed: String
}

// MARK: - App 狀態

enum BackendStatus: Equatable {
    case notStarted
    case starting
    case loadingModel
    case ready
    case error(String)

    var displayText: String {
        switch self {
        case .notStarted: return "尚未啟動"
        case .starting: return "啟動中..."
        case .loadingModel: return "載入 SDXL 模型中..."
        case .ready: return "模型已就緒"
        case .error(let msg): return "錯誤：\(msg)"
        }
    }

    var color: Color {
        switch self {
        case .ready: return .green
        case .error: return .red
        case .starting, .loadingModel: return .orange
        case .notStarted: return .gray
        }
    }
}

enum GenerationState {
    case idle
    case generating
    case completed(NSImage)
    case failed(String)
}
