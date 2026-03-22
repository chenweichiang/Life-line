// GenerationService — HTTP 通訊層，呼叫 Vision API 生成圖片

import Foundation
import AppKit

class GenerationService {
    private let baseURL = "http://127.0.0.1:8001"

    /// 呼叫 Vision API 生成圖片
    func generate(prompt: String, intensity: Double, loraScale: Double, steps: Int, guidance: Double) async throws -> (NSImage, String) {
        guard let url = URL(string: "\(baseURL)/generate_vision") else {
            throw GenerationError.invalidURL
        }

        let vector = EmotionVector(
            intensity: intensity,
            color_tone: "warm",
            flow: "chaotic",
            custom_prompt: prompt
        )

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 180 // SDXL 推論需要時間

        let encoder = JSONEncoder()
        request.httpBody = try encoder.encode(vector)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw GenerationError.serverError
        }

        let decoder = JSONDecoder()
        let result = try decoder.decode(GenerationResponse.self, from: data)

        guard !result.image_base64.isEmpty,
              let imageData = Data(base64Encoded: result.image_base64),
              let image = NSImage(data: imageData) else {
            throw GenerationError.invalidImage
        }

        return (image, result.prompt)
    }
}

enum GenerationError: LocalizedError {
    case invalidURL
    case serverError
    case invalidImage

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "無效的 API 地址"
        case .serverError: return "伺服器錯誤"
        case .invalidImage: return "無法解析生成的圖片"
        }
    }
}
