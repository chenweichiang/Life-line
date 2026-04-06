"""
diffvg_torch.py — 純 PyTorch 微分向量渲染引擎 v2
Life Line 專案的 DiffVG 替代品，無任何 C++ 編譯依賴。

v2 核心改進：
  - 使用「點到線段的連續距離場」取代「點到離散取樣點距離」
  - 消除先前版本的虛線/點狀偽影
  - 渲染出的線條與真實 SVG 渲染器視覺一致
  
原理：
  1. 沿貝茲曲線密集取樣 → 得到折線段序列
  2. 計算每個像素到最近「線段」（不是最近「點」）的距離
  3. sigmoid 軟邊界 → 抗鋸齒 coverage
  4. 所有運算為 PyTorch 原生 ops，autograd 全程追蹤
"""

import torch
import xml.etree.ElementTree as etree
from xml.dom import minidom


# ═══════════════════════════════════════════════════════════════
# 資料結構
# ═══════════════════════════════════════════════════════════════

class Path:
    """一條貝茲曲線路徑（可包含多段曲線串接）"""
    def __init__(self, num_control_points, points, is_closed=False,
                 stroke_width=torch.tensor(1.0)):
        self.num_control_points = num_control_points
        self.points = points
        self.is_closed = is_closed
        self.stroke_width = stroke_width


class ShapeGroup:
    """將形狀與顏色綁定"""
    def __init__(self, shape_ids, fill_color=None, stroke_color=None):
        self.shape_ids = shape_ids
        self.fill_color = fill_color
        self.stroke_color = stroke_color


# ═══════════════════════════════════════════════════════════════
# 貝茲曲線取樣
# ═══════════════════════════════════════════════════════════════

def cubic_bezier_sample(p0, p1, p2, p3, t):
    """
    三階貝茲曲線 Bernstein 展開（完全可微分）
    p0..p3: [2], t: [S] → 回傳 [S, 2]
    """
    mt = 1.0 - t
    w0 = (mt * mt * mt).unsqueeze(-1)          # (1-t)^3
    w1 = (3.0 * mt * mt * t).unsqueeze(-1)     # 3(1-t)^2 t
    w2 = (3.0 * mt * t * t).unsqueeze(-1)      # 3(1-t)t^2
    w3 = (t * t * t).unsqueeze(-1)             # t^3
    return w0 * p0 + w1 * p1 + w2 * p2 + w3 * p3


def _collect_polylines(shapes, shape_groups, t_vals):
    """
    取樣所有曲線，轉為折線段序列。
    
    回傳: list of (polyline_pts, stroke_color, stroke_width)
      polyline_pts: [N, 2] — 折線的頂點序列（相鄰兩點構成一條線段）
    """
    results = []
    for group in shape_groups:
        color = group.stroke_color
        if color is None:
            continue
        for shape_idx in group.shape_ids:
            shape = shapes[shape_idx]
            pts = shape.points
            ncp = shape.num_control_points
            
            all_samples = []
            pi = 0  # point index
            
            for seg_i in range(len(ncp)):
                c = ncp[seg_i].item()
                if c == 2:  # cubic
                    p0 = pts[pi]
                    p1 = pts[pi + 1]
                    p2 = pts[pi + 2]
                    p3 = pts[pi + 3] if pi + 3 < len(pts) else pts[0]
                    all_samples.append(cubic_bezier_sample(p0, p1, p2, p3, t_vals))
                    pi += 3
                elif c == 1:  # quadratic → promote to cubic
                    p0 = pts[pi]
                    q1 = pts[pi + 1]
                    p2 = pts[pi + 2] if pi + 2 < len(pts) else pts[0]
                    c1 = p0 + 2.0 / 3.0 * (q1 - p0)
                    c2 = p2 + 2.0 / 3.0 * (q1 - p2)
                    all_samples.append(cubic_bezier_sample(p0, c1, c2, p2, t_vals))
                    pi += 2
                elif c == 0:  # line
                    p0 = pts[pi]
                    p1 = pts[pi + 1] if pi + 1 < len(pts) else pts[0]
                    lerp = t_vals.unsqueeze(-1)
                    all_samples.append(p0 * (1 - lerp) + p1 * lerp)
                    pi += 1
                else:
                    pi += c + 1
            
            if all_samples:
                polyline = torch.cat(all_samples, dim=0)  # [N, 2]
                results.append((polyline, color, shape.stroke_width))
    return results


# ═══════════════════════════════════════════════════════════════
# 核心：點到線段的可微分距離計算
# ═══════════════════════════════════════════════════════════════

def _distance_to_segments(pixels, seg_a, seg_b):
    """
    計算像素到一批線段的最短距離（完全可微分）
    
    pixels: [H, W, 2] — 像素座標
    seg_a:  [M, 2]    — 線段起點
    seg_b:  [M, 2]    — 線段終點
    
    回傳:   [H, W]    — 每個像素到最近線段的距離
    
    對於每條線段 AB，像素 P 到它的最近點為：
      t = clamp( dot(P-A, B-A) / dot(B-A, B-A), 0, 1 )
      closest = A + t * (B-A)
      distance = |P - closest|
    """
    # ab = B - A: [M, 2]
    ab = seg_b - seg_a
    # ab_sq = |AB|^2: [M]
    ab_sq = (ab * ab).sum(dim=-1).clamp(min=1e-10)
    
    H, W, _ = pixels.shape
    M = seg_a.shape[0]
    
    # [H, W, 1, 2] - [1, 1, M, 2] = [H, W, M, 2]
    ap = pixels.unsqueeze(2) - seg_a.unsqueeze(0).unsqueeze(0)
    
    # dot(AP, AB) / |AB|^2 → t 投影參數: [H, W, M]
    t = (ap * ab.unsqueeze(0).unsqueeze(0)).sum(dim=-1) / ab_sq.unsqueeze(0).unsqueeze(0)
    t = t.clamp(0.0, 1.0)
    
    # 最近點: A + t * AB: [H, W, M, 2]
    closest = seg_a.unsqueeze(0).unsqueeze(0) + t.unsqueeze(-1) * ab.unsqueeze(0).unsqueeze(0)
    
    # 距離: |P - closest|: [H, W, M]
    diff = pixels.unsqueeze(2) - closest
    dist_sq = (diff * diff).sum(dim=-1)
    
    # 取最近的線段距離: [H, W]
    min_dist_sq, _ = dist_sq.min(dim=-1)
    return torch.sqrt(min_dist_sq + 1e-8)


# ═══════════════════════════════════════════════════════════════
# 渲染器
# ═══════════════════════════════════════════════════════════════

def render_paths_soft(shapes, shape_groups, canvas_size=512,
                      num_samples_per_segment=15, device=None):
    """
    軟體光柵化渲染器 v2 — 連續線段距離場
    
    核心流程：
      1. 沿曲線取樣 → 產生折線段序列
      2. 對每組折線段，計算 AABB 包圍盒
      3. 包圍盒內的像素計算「點到最近線段」的連續距離
      4. sigmoid 做軟邊界 → 抗鋸齒 coverage
      5. 前到後 alpha 混合
    
    由於使用線段距離（而非點距離），15 個取樣點/段即可產出平滑線條。
    
    回傳：[canvas_size, canvas_size, 4] RGBA（float32, 0~1）
    """
    if device is None:
        device = shapes[0].points.device if shapes else torch.device('cpu')
    
    canvas = torch.zeros(canvas_size, canvas_size, 4, device=device)
    t_vals = torch.linspace(0.0, 1.0, num_samples_per_segment, device=device)
    
    polylines = _collect_polylines(shapes, shape_groups, t_vals)
    
    for poly_pts, stroke_color, stroke_w in polylines:
        half_w = stroke_w * 0.5
        sharpness = 2.0 / half_w.clamp(min=0.5)
        
        seg_a = poly_pts[:-1]
        seg_b = poly_pts[1:]
        num_segs = seg_a.shape[0]
        
        # AABB
        margin = half_w.detach() + 2.0
        with torch.no_grad():
            d = poly_pts.detach()
            x_lo = max(0, int(d[:,0].min().item() - margin.item()))
            x_hi = min(canvas_size, int(d[:,0].max().item() + margin.item()) + 1)
            y_lo = max(0, int(d[:,1].min().item() - margin.item()))
            y_hi = min(canvas_size, int(d[:,1].max().item() + margin.item()) + 1)
        
        if x_lo >= x_hi or y_lo >= y_hi:
            continue
        
        aabb_h = y_hi - y_lo
        aabb_w = x_hi - x_lo
        
        # 局部像素座標
        ly = torch.arange(y_lo, y_hi, dtype=torch.float32, device=device)
        lx = torch.arange(x_lo, x_hi, dtype=torch.float32, device=device)
        gy, gx = torch.meshgrid(ly, lx, indexing='ij')
        local_pixels = torch.stack([gx, gy], dim=-1)
        
        # 分塊：每塊的總元素數 < 2M 以控制記憶體
        # [chunk_h, aabb_w, num_segs] ~= chunk_h * aabb_w * num_segs
        chunk_h = max(1, min(aabb_h, 2_000_000 // max(1, aabb_w * num_segs)))
        
        for r0 in range(0, aabb_h, chunk_h):
            r1 = min(r0 + chunk_h, aabb_h)
            chunk = local_pixels[r0:r1]
            min_dist = _distance_to_segments(chunk, seg_a, seg_b)
            
            coverage = torch.sigmoid((half_w - min_dist) * sharpness)
            alpha = (coverage * stroke_color[3]).clamp(0.0, 1.0)
            
            gy_s = y_lo + r0
            gy_e = y_lo + r1
            exist_a = canvas[gy_s:gy_e, x_lo:x_hi, 3]
            blend = alpha * (1.0 - exist_a)
            
            canvas[gy_s:gy_e, x_lo:x_hi, 0] += blend * stroke_color[0]
            canvas[gy_s:gy_e, x_lo:x_hi, 1] += blend * stroke_color[1]
            canvas[gy_s:gy_e, x_lo:x_hi, 2] += blend * stroke_color[2]
            canvas[gy_s:gy_e, x_lo:x_hi, 3] += blend
    
    return canvas.clamp(0.0, 1.0)


# ═══════════════════════════════════════════════════════════════
# SVG 匯出
# ═══════════════════════════════════════════════════════════════

def save_svg(filename, canvas_size, shapes, shape_groups):
    """將場景匯出為標準 SVG（M + C 路徑碼）"""
    root = etree.Element('svg')
    root.set('version', '1.1')
    root.set('xmlns', 'http://www.w3.org/2000/svg')
    root.set('width', str(canvas_size))
    root.set('height', str(canvas_size))
    root.set('viewBox', f'0 0 {canvas_size} {canvas_size}')
    
    bg = etree.SubElement(root, 'rect')
    bg.set('width', str(canvas_size))
    bg.set('height', str(canvas_size))
    bg.set('fill', '#000000')
    
    g = etree.SubElement(root, 'g')
    
    for group in shape_groups:
        color = group.stroke_color
        if color is None:
            continue
        for shape_idx in group.shape_ids:
            shape = shapes[shape_idx]
            points = shape.points.detach().cpu().numpy()
            ncp = shape.num_control_points
            sw = shape.stroke_width.detach().cpu().item()
            
            path_str = ''
            pi = 0
            for seg_i in range(len(ncp)):
                c = ncp[seg_i].item()
                if seg_i == 0:
                    path_str += f'M {points[pi,0]:.2f} {points[pi,1]:.2f}'
                if c == 2:
                    i1, i2 = pi+1, pi+2
                    i3 = pi+3 if pi+3 < len(points) else 0
                    path_str += (f' C {points[i1,0]:.2f} {points[i1,1]:.2f}'
                                 f' {points[i2,0]:.2f} {points[i2,1]:.2f}'
                                 f' {points[i3,0]:.2f} {points[i3,1]:.2f}')
                    pi += 3
                elif c == 1:
                    i1 = pi+1
                    i2 = pi+2 if pi+2 < len(points) else 0
                    path_str += (f' Q {points[i1,0]:.2f} {points[i1,1]:.2f}'
                                 f' {points[i2,0]:.2f} {points[i2,1]:.2f}')
                    pi += 2
                elif c == 0:
                    i1 = pi+1 if pi+1 < len(points) else 0
                    path_str += f' L {points[i1,0]:.2f} {points[i1,1]:.2f}'
                    pi += 1
                else:
                    pi += c + 1
            
            if shape.is_closed:
                path_str += ' Z'
            
            el = etree.SubElement(g, 'path')
            el.set('d', path_str)
            el.set('fill', 'none')
            cv = color.detach().cpu().numpy()
            el.set('stroke', f'rgb({int(cv[0]*255)},{int(cv[1]*255)},{int(cv[2]*255)})')
            el.set('stroke-opacity', f'{float(cv[3]):.3f}')
            el.set('stroke-width', f'{sw:.2f}')
            el.set('stroke-linecap', 'round')
            el.set('stroke-linejoin', 'round')
    
    rough = etree.tostring(root, 'unicode')
    dom = minidom.parseString(rough)
    with open(filename, 'w') as f:
        f.write(dom.toprettyxml(indent="  "))
    return filename


# ═══════════════════════════════════════════════════════════════
# 場景初始化
# ═══════════════════════════════════════════════════════════════

def set_use_gpu(val):
    """相容性介面"""
    pass


def initialize_random_paths(num_paths=128, canvas_size=512, device=None):
    """在畫布上隨機播撒貝茲曲線"""
    import random
    if device is None:
        device = torch.device('cpu')
    
    shapes = []
    shape_groups = []
    
    for i in range(num_paths):
        num_segments = random.randint(1, 3)
        num_control_points = torch.zeros(num_segments, dtype=torch.int32) + 2
        
        pts = []
        p0 = [random.random() * canvas_size, random.random() * canvas_size]
        pts.append(p0)
        
        for _ in range(num_segments):
            r = canvas_size * 0.15
            p1 = [p0[0] + r*(random.random()-0.5), p0[1] + r*(random.random()-0.5)]
            p2 = [p1[0] + r*(random.random()-0.5), p1[1] + r*(random.random()-0.5)]
            p3 = [p2[0] + r*(random.random()-0.5), p2[1] + r*(random.random()-0.5)]
            pts.extend([p1, p2, p3])
            p0 = p3
        
        points = torch.tensor(pts, dtype=torch.float32, device=device)
        points.requires_grad = True
        
        sw = torch.tensor(random.random()*3.0+1.0, dtype=torch.float32, device=device)
        sw.requires_grad = True
        
        shapes.append(Path(num_control_points, points, False, sw))
        
        color = torch.tensor(
            [random.random(), random.random(), random.random(), 0.8],
            dtype=torch.float32, device=device
        )
        color.requires_grad = True
        shape_groups.append(ShapeGroup(torch.tensor([i]), None, color))
    
    return shapes, shape_groups


# ═══════════════════════════════════════════════════════════════
# 自我測試
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import time, os
    from PIL import Image
    import numpy as np
    
    print("=" * 60)
    print("  diffvg_torch v2 — 線段距離場渲染引擎 自我測試")
    print("=" * 60)
    
    device = torch.device('cpu')
    if torch.backends.mps.is_available():
        device = torch.device('mps')
        print(f"⚡ Apple MPS")
    elif torch.cuda.is_available():
        device = torch.device('cuda')
    
    cs = 512
    np_paths = 32
    
    print(f"\n[1] 初始化 {np_paths} 條曲線...")
    shapes, groups = initialize_random_paths(np_paths, cs, device)
    
    print(f"[2] 渲染 {cs}x{cs}...")
    t0 = time.time()
    img = render_paths_soft(shapes, groups, cs, 30, device)
    t1 = time.time()
    print(f"  渲染: {t1-t0:.3f}s | shape: {img.shape}")
    
    print(f"[3] 梯度測試...")
    loss = img[:,:,:3].sum()
    loss.backward()
    ok = all(s.points.grad is not None for s in shapes)
    print(f"  梯度: {'✅ OK' if ok else '❌ FAIL'}")
    
    print(f"[4] 存圖...")
    bg = torch.ones(cs, cs, 3, device=device)
    rgb = img[:,:,3:4]*img[:,:,:3] + bg*(1-img[:,:,3:4])
    arr = (rgb.detach().cpu().numpy()*255).astype(np.uint8)
    Image.fromarray(arr).save('/tmp/diffvg_v2_test.png')
    
    save_svg('/tmp/diffvg_v2_test.svg', cs, shapes, groups)
    print(f"  PNG: /tmp/diffvg_v2_test.png")
    print(f"  SVG: /tmp/diffvg_v2_test.svg")
    print("=" * 60)
