// PythonBackend — 管理 Python FastAPI subprocess 生命週期
// 支援兩種模式：開發模式（專案目錄）+ 發行模式（.app bundle 內）

import Foundation
import Combine

@MainActor
class PythonBackend: ObservableObject {
    @Published var status: BackendStatus = .notStarted
    @Published var statusDetail: String = ""

    private var process: Process?
    private var healthCheckTimer: Timer?
    private let apiURL = "http://127.0.0.1:8001"

    /// 解析資源路徑：優先使用 .app bundle 內的資源，否則使用開發目錄
    private var resourcePaths: (python: String, apiDir: String, modelDir: String) {
        let bundle = Bundle.main

        // 模式 1：.app bundle 內（發行版）
        if let resourcePath = bundle.resourcePath {
            let bundlePython = "\(resourcePath)/python/bin/python3"
            let bundleAPI = "\(resourcePath)/api"
            let bundleModel = "\(resourcePath)/models"

            if FileManager.default.fileExists(atPath: bundlePython) {
                return (bundlePython, bundleAPI, bundleModel)
            }
        }

        // 模式 2：開發目錄
        let projectRoot = findProjectRoot()
        return (
            "\(projectRoot)/api_vision_python/.venv/bin/python3",
            "\(projectRoot)/api_vision_python",
            "\(projectRoot)/ai_models"
        )
    }

    /// 找到專案根目錄（往上搜尋 life_line）
    private func findProjectRoot() -> String {
        // 從執行檔位置往上找
        let execPath = ProcessInfo.processInfo.arguments[0]
        if let range = execPath.range(of: "life_line") {
            return String(execPath[execPath.startIndex..<range.upperBound])
        }
        // 從 bundle path 找
        let bundlePath = Bundle.main.bundlePath
        if let range = bundlePath.range(of: "life_line") {
            return String(bundlePath[bundlePath.startIndex..<range.upperBound])
        }
        // 嘗試常見路徑
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        let candidates = [
            "\(home)/Documents/Developer/life_line",
            "\(home)/Developer/life_line",
            FileManager.default.currentDirectoryPath
        ]
        for path in candidates {
            if FileManager.default.fileExists(atPath: "\(path)/api_vision_python/main.py") {
                return path
            }
        }
        return FileManager.default.currentDirectoryPath
    }

    /// 啟動 Python API 後端
    func start() {
        status = .starting
        statusDetail = "檢查 API 狀態..."

        // 先檢查 API 是否已在跑
        checkHealth { [weak self] isRunning in
            Task { @MainActor in
                if isRunning {
                    self?.status = .ready
                    self?.statusDetail = "已連接到現有 API"
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
        let paths = resourcePaths

        // 檢查 Python 是否存在
        guard FileManager.default.fileExists(atPath: paths.python) else {
            status = .error("找不到 Python 環境")
            statusDetail = "路徑：\(paths.python)"
            return
        }

        status = .loadingModel
        statusDetail = "正在載入 SDXL + LoRA 模型（首次約需 60 秒）..."

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: paths.python)
        proc.arguments = ["-m", "uvicorn", "main:app", "--port", "8001", "--host", "127.0.0.1"]
        proc.currentDirectoryURL = URL(fileURLWithPath: paths.apiDir)

        // 設定環境變數讓 Python 找到模型
        var env = ProcessInfo.processInfo.environment
        env["LIFELINE_MODEL_DIR"] = paths.modelDir
        proc.environment = env

        // 靜默輸出
        proc.standardOutput = FileHandle.nullDevice
        proc.standardError = FileHandle.nullDevice

        do {
            try proc.run()
            self.process = proc
            startHealthCheck()
        } catch {
            status = .error("無法啟動 AI 引擎")
            statusDetail = error.localizedDescription
        }
    }

    private func startHealthCheck() {
        var checkCount = 0

        healthCheckTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] timer in
            Task { @MainActor in
                checkCount += 1
                self?.checkHealth { isRunning in
                    Task { @MainActor in
                        if isRunning {
                            timer.invalidate()
                            self?.status = .ready
                            self?.statusDetail = "模型已就緒，可以開始創作"
                        } else {
                            self?.statusDetail = "載入模型中...(\(checkCount * 2)秒)"
                        }
                    }
                }
            }
        }

        // 120 秒超時
        DispatchQueue.main.asyncAfter(deadline: .now() + 120) { [weak self] in
            if self?.status != .ready {
                self?.healthCheckTimer?.invalidate()
                self?.status = .error("模型載入超時")
                self?.statusDetail = "請確認記憶體是否足夠（需要至少 10GB）"
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
