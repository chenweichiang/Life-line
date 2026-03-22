// ContentView — 主視窗 UI
// 科技藝術生成器：文字輸入 → AI 生圖 → 展示 + 儲存

import SwiftUI
import AppKit

struct ContentView: View {
    @EnvironmentObject var backend: PythonBackend

    @State private var prompt: String = ""
    @State private var currentImage: NSImage?
    @State private var isGenerating = false
    @State private var errorMessage: String?
    @State private var history: [GenerationRecord] = []
    @State private var selectedHistory: GenerationRecord?

    // 參數
    @State private var loraScale: Double = 0.4
    @State private var inferenceSteps: Double = 25
    @State private var guidanceScale: Double = 8.5
    @State private var intensity: Double = 0.85

    private let service = GenerationService()

    var body: some View {
        HSplitView {
            // ── 左：主要生成區 ──
            VStack(spacing: 0) {
                // 圖片顯示區
                imageDisplayArea
                    .frame(maxWidth: .infinity, maxHeight: .infinity)

                Divider()

                // 底部控制區
                VStack(spacing: 12) {
                    promptInputArea
                    parameterSliders
                    actionButtons
                }
                .padding(16)
                .background(.ultraThinMaterial)
            }

            // ── 右：歷史側欄 ──
            historySidebar
                .frame(width: 180)
        }
        .frame(minWidth: 900, minHeight: 700)
        .background(Color(nsColor: .windowBackgroundColor))
        // 狀態列
        .safeAreaInset(edge: .bottom, spacing: 0) {
            statusBar
        }
    }

    // MARK: - 圖片顯示區

    private var imageDisplayArea: some View {
        ZStack {
            // 深色背景
            Rectangle()
                .fill(
                    LinearGradient(
                        colors: [Color(white: 0.08), Color(white: 0.12)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )

            if isGenerating {
                VStack(spacing: 16) {
                    ProgressView()
                        .scaleEffect(1.5)
                        .tint(.white)
                    Text("AI 正在創作中...")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(.white.opacity(0.7))
                    Text(prompt.prefix(60) + (prompt.count > 60 ? "..." : ""))
                        .font(.system(size: 11))
                        .foregroundColor(.white.opacity(0.4))
                        .lineLimit(1)
                }
            } else if let image = currentImage {
                Image(nsImage: image)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .padding(20)
                    .shadow(color: .black.opacity(0.5), radius: 20)
                    .transition(.opacity.combined(with: .scale(scale: 0.95)))
            } else {
                VStack(spacing: 12) {
                    Image(systemName: "paintbrush.pointed")
                        .font(.system(size: 48, weight: .thin))
                        .foregroundColor(.white.opacity(0.2))
                    Text("輸入描述文字，開始創作")
                        .font(.system(size: 14))
                        .foregroundColor(.white.opacity(0.3))
                }
            }
        }
    }

    // MARK: - Prompt 輸入

    private var promptInputArea: some View {
        HStack(spacing: 10) {
            Image(systemName: "text.cursor")
                .foregroundColor(.secondary)
                .font(.system(size: 14))

            TextField("輸入創作描述（例：shattered glass prism, vivid rainbow spectrum）", text: $prompt)
                .textFieldStyle(.plain)
                .font(.system(size: 14))
                .onSubmit { generate() }

            Button(action: generate) {
                HStack(spacing: 4) {
                    Image(systemName: "wand.and.stars")
                    Text("生成")
                }
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(.white)
                .padding(.horizontal, 16)
                .padding(.vertical, 7)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .fill(backend.status == .ready && !isGenerating && !prompt.isEmpty
                              ? Color.accentColor
                              : Color.gray.opacity(0.4))
                )
            }
            .buttonStyle(.plain)
            .disabled(backend.status != .ready || isGenerating || prompt.isEmpty)
        }
        .padding(10)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(Color(nsColor: .controlBackgroundColor))
                .shadow(color: .black.opacity(0.1), radius: 2)
        )
    }

    // MARK: - 參數滑桿

    private var parameterSliders: some View {
        HStack(spacing: 20) {
            parameterSlider(label: "LoRA 強度", value: $loraScale, range: 0.1...1.0, format: "%.1f")
            parameterSlider(label: "推論步數", value: $inferenceSteps, range: 10...50, format: "%.0f")
            parameterSlider(label: "Guidance", value: $guidanceScale, range: 3...15, format: "%.1f")
        }
        .font(.system(size: 11))
    }

    private func parameterSlider(label: String, value: Binding<Double>, range: ClosedRange<Double>, format: String) -> some View {
        VStack(spacing: 2) {
            HStack {
                Text(label)
                    .foregroundColor(.secondary)
                Spacer()
                Text(String(format: format, value.wrappedValue))
                    .monospacedDigit()
                    .foregroundColor(.primary)
            }
            Slider(value: value, in: range)
                .controlSize(.small)
        }
    }

    // MARK: - 操作按鈕

    private var actionButtons: some View {
        HStack(spacing: 12) {
            Button(action: saveImage) {
                Label("儲存圖片", systemImage: "square.and.arrow.down")
                    .font(.system(size: 12))
            }
            .disabled(currentImage == nil)

            Button(action: { prompt = "" }) {
                Label("清除", systemImage: "xmark.circle")
                    .font(.system(size: 12))
            }

            Spacer()

            if let err = errorMessage {
                Text(err)
                    .font(.system(size: 11))
                    .foregroundColor(.red)
            }
        }
    }

    // MARK: - 歷史側欄

    private var historySidebar: some View {
        VStack(spacing: 0) {
            Text("歷史紀錄")
                .font(.system(size: 12, weight: .semibold))
                .foregroundColor(.secondary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
                .background(.ultraThinMaterial)

            Divider()

            if history.isEmpty {
                VStack {
                    Spacer()
                    Text("尚無紀錄")
                        .font(.system(size: 11))
                        .foregroundColor(.gray.opacity(0.4))
                    Spacer()
                }
            } else {
                ScrollView {
                    LazyVStack(spacing: 8) {
                        ForEach(history) { record in
                            historyThumbnail(record)
                        }
                    }
                    .padding(8)
                }
            }
        }
        .background(Color(nsColor: .controlBackgroundColor))
    }

    private func historyThumbnail(_ record: GenerationRecord) -> some View {
        VStack(spacing: 4) {
            Image(nsImage: record.image)
                .resizable()
                .aspectRatio(1, contentMode: .fill)
                .frame(width: 150, height: 150)
                .clipShape(RoundedRectangle(cornerRadius: 6))
                .shadow(radius: 2)

            Text(record.prompt.prefix(30) + (record.prompt.count > 30 ? "..." : ""))
                .font(.system(size: 9))
                .foregroundColor(.secondary)
                .lineLimit(2)
        }
        .onTapGesture {
            currentImage = record.image
            prompt = record.prompt
        }
    }

    // MARK: - 狀態列

    private var statusBar: some View {
        HStack {
            Circle()
                .fill(backend.status.color)
                .frame(width: 8, height: 8)
            Text(backend.status.displayText)
                .font(.system(size: 11))
                .foregroundColor(.secondary)

            Spacer()

            if isGenerating {
                ProgressView()
                    .scaleEffect(0.5)
                    .frame(width: 16, height: 16)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(.bar)
    }

    // MARK: - Actions

    private func generate() {
        guard !prompt.isEmpty, backend.status == .ready, !isGenerating else { return }

        isGenerating = true
        errorMessage = nil

        Task {
            do {
                let (image, _) = try await service.generate(
                    prompt: prompt,
                    intensity: intensity,
                    loraScale: loraScale,
                    steps: Int(inferenceSteps),
                    guidance: guidanceScale
                )

                withAnimation(.easeInOut(duration: 0.3)) {
                    currentImage = image
                }

                // 加入歷史
                let record = GenerationRecord(
                    prompt: prompt,
                    image: image,
                    timestamp: Date(),
                    seed: ""
                )
                history.insert(record, at: 0)

            } catch {
                errorMessage = error.localizedDescription
            }

            isGenerating = false
        }
    }

    private func saveImage() {
        guard let image = currentImage else { return }

        let panel = NSSavePanel()
        panel.allowedContentTypes = [.jpeg]
        panel.nameFieldStringValue = "lifeline_\(Int(Date().timeIntervalSince1970)).jpg"
        panel.title = "儲存 AI 生成圖片"

        if panel.runModal() == .OK, let url = panel.url {
            if let tiffData = image.tiffRepresentation,
               let bitmap = NSBitmapImageRep(data: tiffData),
               let jpegData = bitmap.representation(using: .jpeg, properties: [.compressionFactor: 0.9]) {
                try? jpegData.write(to: url)
            }
        }
    }
}
