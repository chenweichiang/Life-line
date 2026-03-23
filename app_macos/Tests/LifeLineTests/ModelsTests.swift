import XCTest
@testable import LifeLine

final class ModelsTests: XCTestCase {

    func testEmotionVectorDefaults() {
        let ev = EmotionVector()
        XCTAssertEqual(ev.intensity, 0.85)
        XCTAssertEqual(ev.color_tone, "warm")
        XCTAssertEqual(ev.flow, "chaotic")
        XCTAssertEqual(ev.custom_prompt, "")
    }

    func testEmotionVectorJSONEncoding() throws {
        let ev = EmotionVector(intensity: 0.5, color_tone: "cool", flow: "calm", custom_prompt: "test")
        let data = try JSONEncoder().encode(ev)
        let dict = try JSONSerialization.jsonObject(with: data, options: []) as? [String: Any]
        
        XCTAssertEqual(dict?["intensity"] as? Double, 0.5)
        XCTAssertEqual(dict?["color_tone"] as? String, "cool")
        XCTAssertEqual(dict?["flow"] as? String, "calm")
        XCTAssertEqual(dict?["custom_prompt"] as? String, "test")
    }

    func testBackendStatusDisplayText() {
        XCTAssertEqual(BackendStatus.notStarted.displayText, "尚未啟動")
        XCTAssertEqual(BackendStatus.starting.displayText, "啟動中...")
        XCTAssertEqual(BackendStatus.loadingModel.displayText, "載入 SDXL 模型中...")
        XCTAssertEqual(BackendStatus.ready.displayText, "模型已就緒")
        XCTAssertEqual(BackendStatus.error("Timeout").displayText, "錯誤：Timeout")
    }
}
