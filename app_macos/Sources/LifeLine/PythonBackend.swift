// PythonBackend — 管理 Python FastAPI subprocess 生命週期

import Foundation
import Combine

@MainActor
class PythonBackend: ObservableObject {
    @Published var status: BackendStatus = .notStarted

    private var process: Process?
    private var healthCheckTimer: Timer?
    private let apiURL = "http://127.0.0.1:8001"

    // 專案根目錄（app_macos 的上一層）
    private var projectRoot: String {
        let bundlePath = Bundle.main.bundlePath
        // 開發時：往上找到 life_line 目錄
        if let range = bundlePath.range(of: "life_line") {
            return String(bundlePath[bundlePath.startIndex..<range.upperBound])
        }
        // 打包後：Resources 內
        return Bundle.main.resourcePath ?? FileManager.default.currentDirectoryPath
    }

    /// 啟動 Python API 後端
    func start() {
        status = .starting

        // 檢查 API 是否已經在跑
        checkHealth { [weak self] isRunning in
            Task { @MainActor in
                if isRunning {
                    self?.status = .ready
                    return
                }
                self?.launchProcess()
            }
        }
    }

    /// 停止 Python 後端
    func stop() {
        healthCheckTimer?.invalidate()
        process?.terminate()
        process = nil
        status = .notStarted
    }

    // MARK: - Private

    private func launchProcess() {
        let venvPython = "\(projectRoot)/api_vision_python/.venv/bin/python3"

        // 檢查檔案是否存在
        guard FileManager.default.fileExists(atPath: venvPython) else {
            status = .error("找不到 Python: \(venvPython)")
            return
        }

        status = .loadingModel

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: venvPython)
        proc.arguments = ["-m", "uvicorn", "main:app", "--port", "8001", "--host", "127.0.0.1"]
        proc.currentDirectoryURL = URL(fileURLWithPath: "\(projectRoot)/api_vision_python")

        // 靜默輸出
        proc.standardOutput = FileHandle.nullDevice
        proc.standardError = FileHandle.nullDevice

        do {
            try proc.run()
            self.process = proc
            startHealthCheck()
        } catch {
            status = .error("無法啟動 Python: \(error.localizedDescription)")
        }
    }

    private func startHealthCheck() {
        // 每 2 秒檢查一次 API 是否就緒
        healthCheckTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] timer in
            self?.checkHealth { isRunning in
                Task { @MainActor in
                    if isRunning {
                        timer.invalidate()
                        self?.status = .ready
                    }
                }
            }
        }

        // 90 秒超時（模型載入需要時間）
        DispatchQueue.main.asyncAfter(deadline: .now() + 90) { [weak self] in
            if self?.status != .ready {
                self?.healthCheckTimer?.invalidate()
                self?.status = .error("模型載入超時（90 秒）")
            }
        }
    }

    private func checkHealth(completion: @escaping (Bool) -> Void) {
        guard let url = URL(string: "\(apiURL)/docs") else {
            completion(false)
            return
        }

        URLSession.shared.dataTask(with: url) { _, response, _ in
            let httpResponse = response as? HTTPURLResponse
            completion(httpResponse?.statusCode == 200)
        }.resume()
    }

    deinit {
        process?.terminate()
    }
}
