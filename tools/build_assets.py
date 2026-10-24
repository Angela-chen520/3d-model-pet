#!/usr/bin/env python3
"""
Step 1: Create or Destroy - 雪靈 (Xueling) & 凌風 (Ling Feng) 視覺素材庫拆解、去背與建置工具
Extracts, seam-splits, removes background (flood-fill + color decontamination),
generates expression variants & SVG icons, and renders verification contact sheets.
"""

import os
import math
import struct
import zlib
import json
from collections import deque

BASE_DIR = "/home/angela/3d model"
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

for sub in [
    "reference",
    "xueling/turnaround",
    "xueling/heads",
    "xueling/expressions",
    "xueling/details",
    "lingfeng/turnaround",
    "lingfeng/expressions",
    "lingfeng/props",
    "lingfeng/details",
    "shop_items",
    "effects",
    "previews",
]:
    os.makedirs(os.path.join(ASSETS_DIR, sub), exist_ok=True)


def save_png_rgba(path, width, height, rgba_bytes):
    """Write an RGBA buffer (width * height * 4 bytes) to a standard PNG file."""
    def make_chunk(chunk_type, data):
        chunk = struct.pack(">I", len(data)) + chunk_type + data
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return chunk + struct.pack(">I", crc)

    raw_rows = bytearray()
    stride = width * 4
    for y in range(height):
        raw_rows.append(0)  # Filter type 0 (None)
        raw_rows.extend(rgba_bytes[y * stride : (y + 1) * stride])

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw_rows), level=6)
    png_data = (
        b"\x89PNG\r\n\x1a\n"
        + make_chunk(b"IHDR", ihdr)
        + make_chunk(b"IDAT", idat)
        + make_chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png_data)


def load_raw_rgb(path):
    with open(path, "rb") as f:
        w, h = struct.unpack("<II", f.read(8))
        buf = f.read()
    return w, h, buf


def find_dp_seam(w, buf, x0, x1, y0, y1, bg_color=(242, 245, 251)):
    """Find minimum-energy vertical seam from y0 to y1 within [x0, x1]."""
    width = x1 - x0 + 1
    height = y1 - y0 + 1
    dp = [[0.0] * width for _ in range(height)]
    parent = [[0] * width for _ in range(height)]
    br, bg, bb = bg_color

    def pix_cost(x, y):
        idx = (y * w + x) * 3
        r, g, b = buf[idx], buf[idx + 1], buf[idx + 2]
        diff = abs(r - br) + abs(g - bg) + abs(b - bb)
        dark = max(0, 235 - min(r, g, b))
        return diff + (dark * 12.0 if dark > 18 else 0.0)

    for xi in range(width):
        dp[0][xi] = pix_cost(x0 + xi, y0)

    for yi in range(1, height):
        y = y0 + yi
        for xi in range(width):
            c = pix_cost(x0 + xi, y)
            best_prev = 1e18
            best_pxi = xi
            for d in (-2, -1, 0, 1, 2):
                pxi = xi + d
                if 0 <= pxi < width:
                    val = dp[yi - 1][pxi] + abs(d) * 2.5
                    if val < best_prev:
                        best_prev = val
                        best_pxi = pxi
            dp[yi][xi] = best_prev + c
            parent[yi][xi] = best_pxi

    cur = min(range(width), key=lambda xi: dp[-1][xi])
    seam = [0] * height
    for yi in range(height - 1, -1, -1):
        seam[yi] = x0 + cur
        cur = parent[yi][cur]
    return seam


def extract_clean_sprite(
    sheet_w,
    sheet_h,
    sheet_buf,
    x0,
    y0,
    x1,
    y1,
    bg_color=(253, 253, 253),
    left_seam=None,
    right_seam=None,
    mask_rects=None,
    remove_leg_gaps=True,
    pad=6,
):
    """
    Crop [x0..x1, y0..y1], apply optional seam boundaries & mask_rects,
    perform exterior flood-fill background removal + interior gap removal +
    soft edge alpha matting & white-halo color decontamination,
    then trim to tight foreground bounding box + uniform padding.
    """
    cw = x1 - x0 + 1
    ch = y1 - y0 + 1
    rgb = bytearray(cw * ch * 3)
    forced_bg = bytearray(cw * ch)  # 1 if masked out by seam or mask_rect

    br, bg, bb = bg_color

    for cy in range(ch):
        sy = y0 + cy
        l_bound = left_seam[cy] if left_seam is not None else x0 - 1
        r_bound = right_seam[cy] if right_seam is not None else x1 + 1
        for cx in range(cw):
            sx = x0 + cx
            d_idx = (cy * cw + cx) * 3
            if sx <= l_bound or sx >= r_bound:
                rgb[d_idx] = br
                rgb[d_idx + 1] = bg
                rgb[d_idx + 2] = bb
                forced_bg[cy * cw + cx] = 1
            else:
                s_idx = (sy * sheet_w + sx) * 3
                rgb[d_idx] = sheet_buf[s_idx]
                rgb[d_idx + 1] = sheet_buf[s_idx + 1]
                rgb[d_idx + 2] = sheet_buf[s_idx + 2]

    if mask_rects:
        for mx0, my0, mx1, my1 in mask_rects:
            for sy in range(max(y0, my0), min(y1, my1) + 1):
                cy = sy - y0
                for sx in range(max(x0, mx0), min(x1, mx1) + 1):
                    cx = sx - x0
                    idx = cy * cw + cx
                    forced_bg[idx] = 1
                    rgb[idx * 3] = br
                    rgb[idx * 3 + 1] = bg
                    rgb[idx * 3 + 2] = bb

    # Compute background distance metric for each pixel
    # Paper background is bright and low-saturation (or matches bg_color closely)
    bg_dist = [0.0] * (cw * ch)
    is_bg_candidate = bytearray(cw * ch)

    for i in range(cw * ch):
        if forced_bg[i]:
            bg_dist[i] = 0.0
            is_bg_candidate[i] = 1
            continue
        r, g, b = rgb[i * 3], rgb[i * 3 + 1], rgb[i * 3 + 2]
        # Difference from local background color
        dr = abs(r - br)
        dg = abs(g - bg)
        db = abs(b - bb)
        color_diff = max(dr, dg, db)
        sat = max(r, g, b) - min(r, g, b)
        # Skin tone protection (#FFDCC5 has R > G > B, R-B >= 22)
        warmth = max(0, (r - b) - (br - bb))
        dist = color_diff + sat * 0.65 + warmth * 0.9
        bg_dist[i] = dist
        # Background or faint watermark threshold
        if dist < 24.0 and min(r, g, b) > 218:
            is_bg_candidate[i] = 1

    # 1. Exterior Flood Fill from all 4 edges of the crop box
    bg_mask = bytearray(cw * ch)
    q = deque()
    for cx in range(cw):
        for cy in (0, ch - 1):
            idx = cy * cw + cx
            if is_bg_candidate[idx] and not bg_mask[idx]:
                bg_mask[idx] = 1
                q.append((cx, cy))
    for cy in range(ch):
        for cx in (0, cw - 1):
            idx = cy * cw + cx
            if is_bg_candidate[idx] and not bg_mask[idx]:
                bg_mask[idx] = 1
                q.append((cx, cy))

    while q:
        cx, cy = q.popleft()
        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if 0 <= nx < cw and 0 <= ny < ch:
                nidx = ny * cw + nx
                if not bg_mask[nidx] and is_bg_candidate[nidx]:
                    bg_mask[nidx] = 1
                    q.append((nx, ny))

    # 2. Check enclosed background pockets (e.g. between legs, between ponytail and neck/arm)
    # while protecting eyes (upper head) and small jacket logo letters (surrounded by very dark jacket)
    if remove_leg_gaps:
        visited = bytearray(bg_mask)
        for start_y in range(ch):
            for start_x in range(cw):
                sidx = start_y * cw + start_x
                if not visited[sidx] and is_bg_candidate[sidx] and bg_dist[sidx] < 16.0:
                    # BFS this enclosed light component
                    comp = []
                    cq = deque([(start_x, start_y)])
                    visited[sidx] = 1
                    border_lums = []
                    min_cy, max_cy = start_y, start_y
                    while cq:
                        px, py = cq.popleft()
                        comp.append((px, py))
                        if py < min_cy:
                            min_cy = py
                        if py > max_cy:
                            max_cy = py
                        for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
                            if 0 <= nx < cw and 0 <= ny < ch:
                                nidx = ny * cw + nx
                                if not visited[nidx] and is_bg_candidate[nidx] and bg_dist[nidx] < 18.0:
                                    visited[nidx] = 1
                                    cq.append((nx, ny))
                                elif not is_bg_candidate[nidx]:
                                    bi = nidx * 3
                                    lum = 0.299 * rgb[bi] + 0.587 * rgb[bi + 1] + 0.114 * rgb[bi + 2]
                                    border_lums.append(lum)
                    # Decide if this enclosed pocket is background gap vs eye/logo:
                    # - Gaps between legs/arms/ponytail are either lower half (min_cy > ch * 0.45 and len >= 14)
                    #   or large enclosed pockets (len >= 55)
                    avg_b_lum = sum(border_lums) / len(border_lums) if border_lums else 0
                    is_gap = False
                    if min_cy > int(ch * 0.58) and len(comp) >= 12:
                        is_gap = True  # Gap between legs/shoes
                    elif len(comp) >= 65 and avg_b_lum > 35:
                        is_gap = True  # Large arm/ponytail gap
                    if is_gap:
                        for px, py in comp:
                            bg_mask[py * cw + px] = 1

    # 3. Remove tiny isolated dust specks (< 10 pixels) detached in the background
    fg_visited = bytearray(cw * ch)
    for sy in range(ch):
        for sx in range(cw):
            sidx = sy * cw + sx
            if not bg_mask[sidx] and not fg_visited[sidx]:
                comp = []
                cq = deque([(sx, sy)])
                fg_visited[sidx] = 1
                touches_main = False
                while cq:
                    px, py = cq.popleft()
                    comp.append((px, py))
                    for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
                        if 0 <= nx < cw and 0 <= ny < ch:
                            nidx = ny * cw + nx
                            if not bg_mask[nidx] and not fg_visited[nidx]:
                                fg_visited[nidx] = 1
                                cq.append((nx, ny))
                if len(comp) < 85:
                    for px, py in comp:
                        bg_mask[py * cw + px] = 1

    # 4. Build RGBA with soft edge anti-aliasing and white-halo decontamination
    rgba = bytearray(cw * ch * 4)
    fg_xs, fg_ys = [], []

    for cy in range(ch):
        for cx in range(cw):
            idx = cy * cw + cx
            if bg_mask[idx]:
                continue
            # Check if adjacent to background
            adj_bg = 0
            for nx, ny in (
                (cx - 1, cy),
                (cx + 1, cy),
                (cx, cy - 1),
                (cx, cy + 1),
                (cx - 1, cy - 1),
                (cx + 1, cy - 1),
                (cx - 1, cy + 1),
                (cx + 1, cy + 1),
            ):
                if nx < 0 or nx >= cw or ny < 0 or ny >= ch or bg_mask[ny * cw + nx]:
                    adj_bg += 1

            r, g, b = rgb[idx * 3], rgb[idx * 3 + 1], rgb[idx * 3 + 2]
            dist = bg_dist[idx]

            if adj_bg > 0 and dist < 52.0:
                # Smooth ramp alpha on the boundary
                alpha_f = max(0.0, min(1.0, (dist - 10.0) / 42.0))
                if adj_bg >= 5:
                    alpha_f *= 0.75
                alpha = int(round(alpha_f * 255))
                if alpha < 12:
                    continue
                # Decontaminate white background bleed from edge pixel
                af = max(0.25, alpha / 255.0)
                r = int(max(0, min(255, (r - (1.0 - af) * br) / af)))
                g = int(max(0, min(255, (g - (1.0 - af) * bg) / af)))
                b = int(max(0, min(255, (b - (1.0 - af) * bb) / af)))
            else:
                alpha = 255

            di = idx * 4
            rgba[di] = r
            rgba[di + 1] = g
            rgba[di + 2] = b
            rgba[di + 3] = alpha
            fg_xs.append(cx)
            fg_ys.append(cy)

    if not fg_xs:
        return cw, ch, bytes(rgba)

    # Trim to tight bounding box + pad
    tx0 = max(0, min(fg_xs) - pad)
    ty0 = max(0, min(fg_ys) - pad)
    tx1 = min(cw - 1, max(fg_xs) + pad)
    ty1 = min(ch - 1, max(fg_ys) + pad)
    tw = tx1 - tx0 + 1
    th = ty1 - ty0 + 1

    trimmed = bytearray(tw * th * 4)
    for ty in range(th):
        sy = ty0 + ty
        s_start = (sy * cw + tx0) * 4
        d_start = ty * tw * 4
        trimmed[d_start : d_start + tw * 4] = rgba[s_start : s_start + tw * 4]

    return tw, th, bytes(trimmed)


print("Loading cached raw RGB sheets...")
w1, h1, b1 = load_raw_rgb("/tmp/xueling.rgb")
w2, h2, b2 = load_raw_rgb("/tmp/lingfeng.rgb")

manifest = {"xueling": {}, "lingfeng": {}, "shop_items": {}, "effects": {}}

# ==============================================================================
# 1. EXTRACT XUELING (雪靈) ASSETS
# ==============================================================================
print("Extracting Xueling (雪靈) sprites...")
xl_bg = (253, 253, 253)

# 1.1 Main Full-Body Sprite
w, h, data = extract_clean_sprite(
    w1, h1, b1, 185, 25, 344, 391, bg_color=xl_bg,
    mask_rects=[
        (185, 25, 344, 43),   # top header slant bar
        (185, 200, 201, 295), # left text column character ("搭")
    ],
)
p = os.path.join(ASSETS_DIR, "xueling/turnaround/main_fullbody.png")
save_png_rgba(p, w, h, data)
manifest["xueling"]["main_fullbody"] = {"path": "assets/xueling/turnaround/main_fullbody.png", "size": [w, h], "label": "雪靈 - 主立繪 (Full Body)"}

# 1.2 5 Full-Body Turnaround Views
xl_turn_specs = [
    ("turn_1_front", "正面 FRONT", 24, 540, 140, 782, [(24, 540, 140, 560)]),
    ("turn_2_left45", "左前45度 45°LEFT", 160, 540, 272, 782, [(160, 540, 248, 560), (240, 540, 272, 550)]),
    ("turn_3_side", "左側 SIDE", 300, 550, 402, 782, []),
    ("turn_4_right45", "右後45度 45°RIGHT", 408, 550, 524, 782, []),
    ("turn_5_back", "背面 BACK", 550, 550, 662, 782, []),
]
for key, label, x0, y0, x1, y1, masks in xl_turn_specs:
    w, h, data = extract_clean_sprite(w1, h1, b1, x0, y0, x1, y1, bg_color=xl_bg, mask_rects=masks)
    rel = f"assets/xueling/turnaround/{key}.png"
    save_png_rgba(os.path.join(BASE_DIR, rel), w, h, data)
    manifest["xueling"][key] = {"path": rel, "size": [w, h], "label": f"雪靈五視圖 - {label}"}

# 1.3 5 Head Turnaround Views
xl_head_specs = [
    ("head_1_front", "頭部 正面 FRONT", 24, 834, 140, 984, [(24, 834, 140, 853)]),
    ("head_2_left45", "頭部 左前45度 45°LEFT", 150, 834, 275, 984, [(150, 834, 246, 853), (240, 834, 275, 845)]),
    ("head_3_side", "頭部 左側 SIDE", 292, 845, 412, 984, []),
    ("head_4_right45", "頭部 右後45度 45°RIGHT", 418, 845, 536, 984, []),
    ("head_5_back", "頭部 背面 BACK", 556, 845, 658, 984, []),
]
for key, label, x0, y0, x1, y1, masks in xl_head_specs:
    w, h, data = extract_clean_sprite(w1, h1, b1, x0, y0, x1, y1, bg_color=xl_bg, mask_rects=masks, remove_leg_gaps=False)
    rel = f"assets/xueling/heads/{key}.png"
    save_png_rgba(os.path.join(BASE_DIR, rel), w, h, data)
    manifest["xueling"][key] = {"path": rel, "size": [w, h], "label": f"雪靈 - {label}"}

# 1.4 Xueling Details & Costume Breakdown
xl_detail_specs = [
    ("detail_hair", "髮型拆解 (高馬尾)", 426, 34, 528, 118),
    ("prop_sunglasses", "配件 - 藍色圓形墨鏡", 445, 130, 524, 160),
    ("costume_jacket_front", "LEGEND X 外套 (正面)", 432, 168, 540, 257),
    ("costume_jacket_back", "LEGEND X 外套 (背面)", 547, 168, 650, 256),
    ("costume_tshirt", "LEGEND X 短袖 T-Shirt", 450, 265, 526, 312),
    ("costume_shorts_front", "電競短褲 (正面)", 453, 319, 512, 357),
    ("costume_shorts_back", "電競短褲 (背面)", 539, 319, 604, 361),
    ("costume_shoes", "電競運動鞋與高筒藍襪", 430, 366, 539, 411),
]
for key, label, x0, y0, x1, y1 in xl_detail_specs:
    w, h, data = extract_clean_sprite(w1, h1, b1, x0, y0, x1, y1, bg_color=xl_bg, remove_leg_gaps=False)
    rel = f"assets/xueling/details/{key}.png"
    save_png_rgba(os.path.join(BASE_DIR, rel), w, h, data)
    manifest["xueling"][key] = {"path": rel, "size": [w, h], "label": f"雪靈細節 - {label}"}


# ==============================================================================
# 2. EXTRACT LING FENG (凌風) ASSETS
# ==============================================================================
print("Extracting Ling Feng (凌風) sprites...")
lf_bg = (240, 244, 250)

# Compute DP seams for Ling Feng's 5 turnaround views (y: 35..286)
ty0, ty1 = 35, 286
seam_v0_v1 = find_dp_seam(w2, b2, 246, 274, ty0, ty1, lf_bg)
seam_v1_v2 = find_dp_seam(w2, b2, 368, 396, ty0, ty1, lf_bg)
seam_v2_v3 = find_dp_seam(w2, b2, 482, 510, ty0, ty1, lf_bg)
seam_v3_v4 = find_dp_seam(w2, b2, 596, 622, ty0, ty1, lf_bg)
seam_v4_v5 = find_dp_seam(w2, b2, 725, 748, ty0, ty1, lf_bg)

lf_turn_specs = [
    ("turn_1_front", "正面 FRONT", 246, 396, seam_v0_v1, seam_v1_v2, [(246, 35, 365, 50), (246, 130, 270, 286)]),
    ("turn_2_side", "側面 SIDE", 368, 510, seam_v1_v2, seam_v2_v3, []),
    ("turn_3_back", "背面 BACK", 482, 622, seam_v2_v3, seam_v3_v4, []),
    ("turn_4_three_quarter", "斜側面 3/4", 596, 748, seam_v3_v4, seam_v4_v5, []),
    ("turn_5_top", "俯視 TOP", 725, 855, seam_v4_v5, None, [(815, 35, 855, 85)]),
]
for key, label, x0, x1, l_seam, r_seam, masks in lf_turn_specs:
    w, h, data = extract_clean_sprite(
        w2, h2, b2, x0, ty0, x1, ty1, bg_color=lf_bg,
        left_seam=l_seam, right_seam=r_seam,
        mask_rects=masks,
        remove_leg_gaps=(key != "turn_5_top"),
    )
    rel = f"assets/lingfeng/turnaround/{key}.png"
    save_png_rgba(os.path.join(BASE_DIR, rel), w, h, data)
    manifest["lingfeng"][key] = {"path": rel, "size": [w, h], "label": f"凌風五視圖 - {label}"}
    if key == "turn_1_front":
        main_rel = "assets/lingfeng/turnaround/main_fullbody.png"
        save_png_rgba(os.path.join(BASE_DIR, main_rel), w, h, data)
        manifest["lingfeng"]["main_fullbody"] = {"path": main_rel, "size": [w, h], "label": "凌風 - 主立繪 (Full Body)"}

# 2.2 Ling Feng 5 Native Expressions (y: 344..443 - pure head without top line or bottom text pill)
ey0, ey1 = 344, 443
seam_e1_e2 = find_dp_seam(w2, b2, 348, 366, ey0, ey1, lf_bg)
seam_e2_e3 = find_dp_seam(w2, b2, 432, 448, ey0, ey1, lf_bg)
seam_e3_e4 = find_dp_seam(w2, b2, 515, 532, ey0, ey1, lf_bg)
seam_e4_e5 = find_dp_seam(w2, b2, 598, 616, ey0, ey1, lf_bg)

lf_expr_specs = [
    ("expr_1_normal", "普通 (Normal)", 272, 366, None, seam_e1_e2),
    ("expr_2_smile", "微笑 (Smile)", 348, 448, seam_e1_e2, seam_e2_e3),
    ("expr_3_angry", "生氣 (Angry)", 432, 532, seam_e2_e3, seam_e3_e4),
    ("expr_4_surprised", "驚訝 (Surprised)", 515, 616, seam_e3_e4, seam_e4_e5),
    ("expr_5_shy", "害羞 (Shy)", 598, 687, seam_e4_e5, None),
]
for key, label, x0, x1, l_seam, r_seam in lf_expr_specs:
    w, h, data = extract_clean_sprite(
        w2, h2, b2, x0, ey0, x1, ey1, bg_color=lf_bg,
        left_seam=l_seam, right_seam=r_seam, remove_leg_gaps=False
    )
    rel = f"assets/lingfeng/expressions/{key}.png"
    save_png_rgba(os.path.join(BASE_DIR, rel), w, h, data)
    manifest["lingfeng"][key] = {"path": rel, "size": [w, h], "label": f"凌風表情 - {label}"}

# 2.3 Ling Feng 4 Exclusive Props & Gear (y: 506..611 - above bottom Chinese labels)
py0, py1 = 506, 611
seam_p1_p2 = find_dp_seam(w2, b2, 642, 672, py0, py1, lf_bg)
seam_p2_p3 = find_dp_seam(w2, b2, 716, 735, py0, py1, lf_bg)
seam_p3_p4 = find_dp_seam(w2, b2, 778, 804, py0, py1, lf_bg)

lf_prop_specs = [
    ("prop_carkey", "BMW 跑車鑰匙", 599, 672, None, seam_p1_p2),
    ("prop_sunglasses", "電競飛行員墨鏡", 642, 735, seam_p1_p2, seam_p2_p3),
    ("prop_headphones", "電競耳罩式耳機", 716, 804, seam_p2_p3, seam_p3_p4),
    ("prop_gaming_chair", "專屬藍黑電競座椅", 778, 855, seam_p3_p4, None),
]
for key, label, x0, x1, l_seam, r_seam in lf_prop_specs:
    w, h, data = extract_clean_sprite(
        w2, h2, b2, x0, py0, x1, py1, bg_color=lf_bg,
        left_seam=l_seam, right_seam=r_seam,
        remove_leg_gaps=(key == "prop_headphones"),
    )
    rel = f"assets/lingfeng/props/{key}.png"
    save_png_rgba(os.path.join(BASE_DIR, rel), w, h, data)
    manifest["lingfeng"][key] = {"path": rel, "size": [w, h], "label": f"凌風裝備 - {label}"}

# 2.4 Ling Feng Costume Details (y: 504..611 - above bottom Chinese labels)
cy0, cy1 = 504, 611
seam_c1_c2 = find_dp_seam(w2, b2, 350, 366, cy0, cy1, lf_bg)
seam_c2_c3 = find_dp_seam(w2, b2, 430, 445, cy0, cy1, lf_bg)
seam_c3_c4 = find_dp_seam(w2, b2, 482, 498, cy0, cy1, lf_bg)
seam_c4_c5 = find_dp_seam(w2, b2, 541, 554, cy0, cy1, lf_bg)

lf_costume_specs = [
    ("costume_jacket_front", "E-SPORTS 連帽外套 (正面)", 276, 366, None, seam_c1_c2),
    ("costume_jacket_back", "E-SPORTS 連帽外套 (背面)", 350, 445, seam_c1_c2, seam_c2_c3),
    ("costume_hood", "連帽設計細節", 430, 498, seam_c2_c3, seam_c3_c4),
    ("costume_pants", "多口袋機能工裝長褲", 482, 554, seam_c3_c4, seam_c4_c5),
    ("costume_shoes", "高筒賽車運動鞋", 541, 585, seam_c4_c5, None),
]
for key, label, x0, x1, l_seam, r_seam in lf_costume_specs:
    w, h, data = extract_clean_sprite(
        w2, h2, b2, x0, cy0, x1, cy1, bg_color=lf_bg,
        left_seam=l_seam, right_seam=r_seam,
        remove_leg_gaps=(key == "costume_pants"),
    )
    rel = f"assets/lingfeng/details/{key}.png"
    save_png_rgba(os.path.join(BASE_DIR, rel), w, h, data)
    manifest["lingfeng"][key] = {"path": rel, "size": [w, h], "label": f"凌風服裝 - {label}"}

# 2.5 Ling Feng Racing Scene Portrait (Left Panel x: 0..255, y: 125..640)
rw, rh = 255, 515
r_rgba = bytearray(rw * rh * 4)
for ry in range(rh):
    sy = 125 + ry
    for rx in range(rw):
        sx = rx
        s_idx = (sy * w2 + sx) * 3
        d_idx = (ry * rw + rx) * 4
        r_rgba[d_idx] = b2[s_idx]
        r_rgba[d_idx + 1] = b2[s_idx + 1]
        r_rgba[d_idx + 2] = b2[s_idx + 2]
        r_rgba[d_idx + 3] = 255
rel_race = "assets/lingfeng/turnaround/racing_scene.png"
save_png_rgba(os.path.join(BASE_DIR, rel_race), rw, rh, bytes(r_rgba))
manifest["lingfeng"]["racing_scene"] = {"path": rel_race, "size": [rw, rh], "label": "凌風 - 藍色跑車駕駛特寫"}


# ==============================================================================
# 3. GENERATE EXAGGERATED ANIME EXPRESSIONS (7 FOR XUELING + 7 FOR LING FENG)
# ==============================================================================
print("Generating exaggerated anime expressions for Xueling & Ling Feng...")

def pad_rgba_canvas(rgba, w, h, pad_l, pad_t, pad_r, pad_b):
    nw = w + pad_l + pad_r
    nh = h + pad_t + pad_b
    out = bytearray(nw * nh * 4)
    for y in range(h):
        ty = y + pad_t
        s_off = y * w * 4
        d_off = (ty * nw + pad_l) * 4
        out[d_off : d_off + w * 4] = rgba[s_off : s_off + w * 4]
    return nw, nh, out

def draw_pixel(buf, w, h, x, y, r, g, b, a=255):
    if 0 <= x < w and 0 <= y < h:
        idx = (y * w + x) * 4
        sa = max(0.0, min(1.0, a / 255.0))
        if sa <= 0:
            return
        da = buf[idx + 3] / 255.0
        oa = sa + da * (1.0 - sa)
        if oa > 0:
            buf[idx] = int(max(0, min(255, (r * sa + buf[idx] * da * (1.0 - sa)) / oa)))
            buf[idx + 1] = int(max(0, min(255, (g * sa + buf[idx + 1] * da * (1.0 - sa)) / oa)))
            buf[idx + 2] = int(max(0, min(255, (b * sa + buf[idx + 2] * da * (1.0 - sa)) / oa)))
            buf[idx + 3] = int(max(0, min(255, oa * 255)))

def draw_thick_line(buf, w, h, x0, y0, x1, y1, color, radius=1.5):
    steps = int(max(abs(x1 - x0), abs(y1 - y0)) * 3) + 1
    r, g, b, a = color
    ir = int(math.ceil(radius)) + 1
    for s in range(steps + 1):
        t = s / max(1, steps)
        cx = x0 + (x1 - x0) * t
        cy = y0 + (y1 - y0) * t
        ix, iy = int(round(cx)), int(round(cy))
        for dy in range(-ir, ir + 1):
            for dx in range(-ir, ir + 1):
                px, py = ix + dx, iy + dy
                d = math.hypot(px - cx, py - cy)
                if d <= radius + 0.45:
                    fa = a if d <= radius - 0.35 else int(a * max(0.0, (radius + 0.45 - d) / 0.8))
                    draw_pixel(buf, w, h, px, py, r, g, b, fa)

def draw_outlined_line(buf, w, h, x0, y0, x1, y1, fill_color, outline_color, radius=1.8, outline_w=1.2):
    draw_thick_line(buf, w, h, x0, y0, x1, y1, outline_color, radius + outline_w)
    draw_thick_line(buf, w, h, x0, y0, x1, y1, fill_color, radius)

def draw_soft_circle(buf, w, h, cx, cy, rad, color):
    r, g, b, a = color
    for py in range(int(cy - rad - 1), int(cy + rad + 2)):
        for px in range(int(cx - rad - 1), int(cx + rad + 2)):
            d = math.hypot(px - cx, py - cy)
            if d <= rad:
                falloff = (1.0 - (d / rad) ** 2)
                draw_pixel(buf, w, h, px, py, r, g, b, int(a * falloff))

def draw_solid_circle(buf, w, h, cx, cy, rad, fill_color, outline_color=None, outline_w=1.3):
    if outline_color:
        orad = rad + outline_w
        or_, og, ob, oa = outline_color
        for py in range(int(cy - orad - 2), int(cy + orad + 3)):
            for px in range(int(cx - orad - 2), int(cx + orad + 3)):
                d = math.hypot(px - cx, py - cy)
                if d <= orad + 0.45:
                    fa = oa if d <= orad - 0.35 else int(oa * max(0.0, (orad + 0.45 - d) / 0.8))
                    draw_pixel(buf, w, h, px, py, or_, og, ob, fa)
    r, g, b, a = fill_color
    for py in range(int(cy - rad - 2), int(cy + rad + 3)):
        for px in range(int(cx - rad - 2), int(cx + rad + 3)):
            d = math.hypot(px - cx, py - cy)
            if d <= rad + 0.45:
                fa = a if d <= rad - 0.35 else int(a * max(0.0, (rad + 0.45 - d) / 0.8))
                draw_pixel(buf, w, h, px, py, r, g, b, fa)

def draw_heart_icon(buf, w, h, cx, cy, size, fill_color, outline_color=(255, 255, 255, 255)):
    # Draw outline first if given, then fill
    for col, scale in [(outline_color, size + 1.4), (fill_color, size)]:
        if col is None:
            continue
        r, g, b, a = col
        ir = int(math.ceil(scale * 1.4)) + 2
        for py in range(int(cy - ir), int(cy + ir + 1)):
            for px in range(int(cx - ir), int(cx + ir + 1)):
                nx = (px - cx) / scale
                ny = -(py - cy) / scale + 0.25
                val = (nx * nx + ny * ny - 1.0) ** 3 - (nx * nx) * (ny ** 3)
                if val <= 0.0:
                    draw_pixel(buf, w, h, px, py, r, g, b, a)

def draw_sparkle_star(buf, w, h, cx, cy, rad, fill_color=(255, 235, 80, 255), outline_color=(180, 95, 0, 240)):
    # 4-point anime star burst
    draw_soft_circle(buf, w, h, cx, cy, rad * 1.15, (255, 240, 130, 120))
    draw_outlined_line(buf, w, h, cx - rad, cy, cx + rad, cy, fill_color, outline_color, radius=1.3, outline_w=1.0)
    draw_outlined_line(buf, w, h, cx, cy - rad, cx, cy + rad, fill_color, outline_color, radius=1.3, outline_w=1.0)
    d = rad * 0.48
    draw_thick_line(buf, w, h, cx - d, cy - d, cx + d, cy + d, fill_color, 1.0)
    draw_thick_line(buf, w, h, cx - d, cy + d, cx + d, cy - d, fill_color, 1.0)
    draw_solid_circle(buf, w, h, cx, cy, rad * 0.28, (255, 255, 255, 255))

def draw_anger_vein(buf, w, h, cx, cy, size=9.0):
    # Classic 4-curved-corner anime popping anger vein 💢 with white border and bright red core
    out_c = (255, 255, 255, 250)
    in_c = (255, 35, 55, 255)
    g = size * 0.26
    s = size
    segments = [
        (cx - s, cy - g, cx - g, cy - g), (cx - g, cy - g, cx - g, cy - s),
        (cx + s, cy - g, cx + g, cy - g), (cx + g, cy - g, cx + g, cy - s),
        (cx - s, cy + g, cx - g, cy + g), (cx - g, cy + g, cx - g, cy + s),
        (cx + s, cy + g, cx + g, cy + g), (cx + g, cy + g, cx + g, cy + s),
    ]
    for x0, y0, x1, y1 in segments:
        draw_thick_line(buf, w, h, x0, y0, x1, y1, out_c, 2.5)
    for x0, y0, x1, y1 in segments:
        draw_thick_line(buf, w, h, x0, y0, x1, y1, in_c, 1.4)

def draw_sweat_drop(buf, w, h, cx, cy, size=8.5):
    # Big anime teardrop with dark blue outline, sky-blue fill, and white highlight
    out_c = (20, 75, 165, 250)
    fill_c = (110, 215, 255, 250)
    draw_solid_circle(buf, w, h, cx, cy + size * 0.35, size * 0.48, fill_c, out_c, 1.3)
    draw_outlined_line(buf, w, h, cx, cy - size * 0.55, cx - size * 0.32, cy + size * 0.25, fill_c, out_c, 1.4, 1.2)
    draw_outlined_line(buf, w, h, cx, cy - size * 0.55, cx + size * 0.32, cy + size * 0.25, fill_c, out_c, 1.4, 1.2)
    draw_thick_line(buf, w, h, cx, cy - size * 0.35, cx, cy + size * 0.35, fill_c, size * 0.32)
    draw_solid_circle(buf, w, h, cx - size * 0.14, cy + size * 0.28, size * 0.16, (255, 255, 255, 250))

def draw_shock_bolt(buf, w, h, x0, y0, x1, y1):
    # Zig-zag anime lightning bolt
    mx1 = x0 + (x1 - x0) * 0.45 - 3
    my1 = y0 + (y1 - y0) * 0.45 + 2
    mx2 = x0 + (x1 - x0) * 0.55 + 3
    my2 = y0 + (y1 - y0) * 0.55 - 2
    out_c = (190, 90, 0, 245)
    in_c = (255, 240, 70, 255)
    for ax, ay, bx, by in [(x0, y0, mx1, my1), (mx1, my1, mx2, my2), (mx2, my2, x1, y1)]:
        draw_thick_line(buf, w, h, ax, ay, bx, by, out_c, 2.3)
    for ax, ay, bx, by in [(x0, y0, mx1, my1), (mx1, my1, mx2, my2), (mx2, my2, x1, y1)]:
        draw_thick_line(buf, w, h, ax, ay, bx, by, in_c, 1.3)

def draw_rect_patch(buf, w, h, x0, y0, x1, y1, fill_rgba, border_rgba=None):
    ix0, iy0, ix1, iy1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
    for y in range(iy0, iy1 + 1):
        for x in range(ix0, ix1 + 1):
            if border_rgba and (x in (ix0, ix0 + 1, ix1 - 1, ix1) or y in (iy0, iy0 + 1, iy1 - 1, iy1)):
                draw_pixel(buf, w, h, x, y, *border_rgba)
            else:
                draw_pixel(buf, w, h, x, y, *fill_rgba)

def draw_happy_open_mouth(buf, w, h, mx, my, mw=8.0, mh=5.5):
    # Wide open cheerful D-shaped anime mouth with dark outline, coral-pink interior, and white teeth
    out_c = (45, 20, 30, 250)
    tongue_c = (255, 105, 130, 255)
    dark_in = (185, 45, 75, 255)
    irx, iry = int(mw) + 2, int(mh) + 2
    for dy in range(-2, iry + 1):
        for dx in range(-irx, irx + 1):
            nx = dx / mw
            ny = dy / mh
            if dy >= 0 and (nx * nx + ny * ny) <= 1.25:
                if (nx * nx + ny * ny) > 0.85 or dy <= 1:
                    draw_pixel(buf, w, h, int(mx + dx), int(my + dy), *out_c)
                elif dy <= 2:
                    draw_pixel(buf, w, h, int(mx + dx), int(my + dy), 255, 255, 255, 250)
                elif dy < mh * 0.55:
                    draw_pixel(buf, w, h, int(mx + dx), int(my + dy), *dark_in)
                else:
                    draw_pixel(buf, w, h, int(mx + dx), int(my + dy), *tongue_c)

def draw_angry_fang_mouth(buf, w, h, mx, my, mw=8.5, mh=5.0):
    # Fierce open shouting mouth with white canine fangs
    out_c = (45, 15, 25, 250)
    in_c = (210, 45, 65, 255)
    for dy in range(-int(mh), int(mh) + 1):
        for dx in range(-int(mw), int(mw) + 1):
            # Trapezoid mouth wider at bottom
            w_at_y = mw * (0.78 + 0.22 * (dy + mh) / (2 * mh))
            if abs(dx) <= w_at_y + 1.2 and abs(dy) <= mh + 1.0:
                if abs(dx) >= w_at_y - 0.5 or abs(dy) >= mh - 0.5:
                    draw_pixel(buf, w, h, int(mx + dx), int(my + dy), *out_c)
                else:
                    draw_pixel(buf, w, h, int(mx + dx), int(my + dy), *in_c)
    # Two sharp white fangs at top corners
    for fx in (mx - mw * 0.45, mx + mw * 0.45):
        draw_thick_line(buf, w, h, fx - 1.2, my - mh + 1, fx, my - 0.5, (255, 255, 255, 255), 1.1)
        draw_thick_line(buf, w, h, fx + 1.2, my - mh + 1, fx, my - 0.5, (255, 255, 255, 255), 1.1)

def draw_wavy_cat_mouth(buf, w, h, mx, my, mw=7.5):
    # Cute exaggerated ω cat mouth
    c = (55, 25, 35, 250)
    draw_thick_line(buf, w, h, mx - mw, my - 1.0, mx - mw * 0.45, my + 2.2, c, 1.3)
    draw_thick_line(buf, w, h, mx - mw * 0.45, my + 2.2, mx, my - 0.8, c, 1.3)
    draw_thick_line(buf, w, h, mx, my - 0.8, mx + mw * 0.45, my + 2.2, c, 1.3)
    draw_thick_line(buf, w, h, mx + mw * 0.45, my + 2.2, mx + mw, my - 1.0, c, 1.3)

def draw_thermometer(buf, w, h, mx, my):
    # Fever thermometer sticking out diagonally from mouth
    x1, y1 = mx + 16, my + 9
    draw_outlined_line(buf, w, h, mx + 1, my, x1, y1, (245, 250, 255, 255), (40, 60, 90, 250), 2.1, 1.1)
    # Red mercury line inside
    draw_thick_line(buf, w, h, mx + 2, my + 0.5, mx + 11, my + 6.2, (255, 50, 65, 255), 0.9)
    # Tick marks
    for t in (0.35, 0.55, 0.75):
        tx = mx + 1 + (x1 - (mx + 1)) * t
        ty = my + (y1 - my) * t
        draw_thick_line(buf, w, h, tx - 1, ty + 1.5, tx + 1, ty - 1.5, (40, 60, 90, 220), 0.7)

def apply_upper_face_tint(buf, w, h, ymin, ymax, tint_rgb, max_alpha=125):
    # Smoothly tints from the very top of the head down to ymax so there is no horizontal cut line
    tr, tg, tb = tint_rgb
    start_y = 0
    for y in range(start_y, min(h, int(ymax))):
        if y < ymin:
            prog = 0.85
        else:
            prog = 0.85 * (1.0 - (y - ymin) / max(1.0, (ymax - ymin)))
        a = int(max_alpha * max(0.0, min(1.0, prog)))
        for x in range(w):
            idx = (y * w + x) * 4
            if buf[idx + 3] > 140:
                draw_pixel(buf, w, h, x, y, tr, tg, tb, a)

def darken_lenses(buf, w, h, lx1, lx2, ly, rad, tint_rgb=(10, 22, 55), alpha=185):
    for lx in (lx1, lx2):
        draw_solid_circle(buf, w, h, lx, ly, rad, (*tint_rgb, alpha))


# ------------------------------------------------------------------------------
# 3.1 XUELING 7 EXAGGERATED EXPRESSIONS
# ------------------------------------------------------------------------------
xl_raw_w, xl_raw_h, xl_raw_data = extract_clean_sprite(
    w1, h1, b1, 24, 834, 140, 984, bg_color=xl_bg,
    mask_rects=[(24, 834, 140, 853)], remove_leg_gaps=False
)
pad_x, pad_y = 16, 14
xl_hw, xl_hh, xl_hdata = pad_rgba_canvas(xl_raw_data, xl_raw_w, xl_raw_h, pad_x, pad_y, pad_x, 6)

# Find center of blue sunglasses lenses on padded Xueling head
blue_xs, blue_ys = [], []
for y in range(xl_hh):
    for x in range(xl_hw):
        idx = (y * xl_hw + x) * 4
        if xl_hdata[idx + 3] > 200 and (xl_hdata[idx + 2] - xl_hdata[idx]) > 45 and y > xl_hh * 0.45:
            blue_xs.append(x)
            blue_ys.append(y)

mid_x = (min(blue_xs) + max(blue_xs)) / 2.0
lens_y = sum(blue_ys) / len(blue_ys)
left_lens_x = mid_x - 14.5
right_lens_x = mid_x + 13.5
xl_mouth_y = lens_y + 11.5

xl_expr_defs = [
    ("expr_1_normal", "普通 (Normal)"),
    ("expr_2_happy", "超開心/閃耀 (Happy ✨)"),
    ("expr_3_angry", "暴怒/爆青筋 (Angry 💢)"),
    ("expr_4_surprised", "大震驚/雷擊 (Shocked ⚡)"),
    ("expr_5_shy", "害羞心動/冒愛心 (Shy 💕)"),
    ("expr_6_focused", "番茄鐘極限專注 (Focused 💡)"),
    ("expr_7_sick", "重感冒/腸胃炎 (Sick 🤒🌡️)"),
]

for key, label in xl_expr_defs:
    buf = bytearray(xl_hdata)
    if key == "expr_2_happy":
        # Darken lenses slightly so giant neon ^ ^ arcs pop out cleanly
        darken_lenses(buf, xl_hw, xl_hh, left_lens_x, right_lens_x, lens_y, 8.2, (8, 30, 85), 165)
        # Glowing golden-cyan happy ^ ^ arcs
        for lx in (left_lens_x, right_lens_x):
            draw_outlined_line(buf, xl_hw, xl_hh, lx - 6.0, lens_y + 2.8, lx, lens_y - 4.8, (255, 250, 150, 255), (0, 225, 255, 255), 1.6, 1.3)
            draw_outlined_line(buf, xl_hw, xl_hh, lx, lens_y - 4.8, lx + 6.0, lens_y + 2.8, (255, 250, 150, 255), (0, 225, 255, 255), 1.6, 1.3)
        # Rosy cheeks + blush slashes + big happy open mouth
        draw_soft_circle(buf, xl_hw, xl_hh, left_lens_x - 5, lens_y + 9.5, 8.5, (255, 95, 130, 165))
        draw_soft_circle(buf, xl_hw, xl_hh, right_lens_x + 5, lens_y + 9.5, 8.5, (255, 95, 130, 165))
        draw_happy_open_mouth(buf, xl_hw, xl_hh, mid_x, xl_mouth_y, mw=6.5, mh=4.8)
        # Floating golden sparkles around head
        draw_sparkle_star(buf, xl_hw, xl_hh, 16, 36, 9.5)
        draw_sparkle_star(buf, xl_hw, xl_hh, xl_hw - 16, 28, 10.5)
        draw_sparkle_star(buf, xl_hw, xl_hh, 22, 95, 6.5)

    elif key == "expr_3_angry":
        # Crimson rage shadow over forehead + darkened crimson lenses
        apply_upper_face_tint(buf, xl_hw, xl_hh, lens_y - 45, lens_y - 2, (160, 10, 30), 115)
        darken_lenses(buf, xl_hw, xl_hh, left_lens_x, right_lens_x, lens_y, 8.5, (45, 8, 20), 195)
        # Giant glowing fiery > < eyes on lenses
        out_r = (255, 40, 55, 255)
        in_y = (255, 230, 90, 255)
        draw_outlined_line(buf, xl_hw, xl_hh, left_lens_x - 5.5, lens_y - 4.8, left_lens_x + 5.0, lens_y, in_y, out_r, 1.5, 1.3)
        draw_outlined_line(buf, xl_hw, xl_hh, left_lens_x + 5.0, lens_y, left_lens_x - 5.5, lens_y + 4.8, in_y, out_r, 1.5, 1.3)
        draw_outlined_line(buf, xl_hw, xl_hh, right_lens_x + 5.5, lens_y - 4.8, right_lens_x - 5.0, lens_y, in_y, out_r, 1.5, 1.3)
        draw_outlined_line(buf, xl_hw, xl_hh, right_lens_x - 5.0, lens_y, right_lens_x + 5.5, lens_y + 4.8, in_y, out_r, 1.5, 1.3)
        # Fierce V eyebrows
        draw_outlined_line(buf, xl_hw, xl_hh, left_lens_x - 7, lens_y - 11, left_lens_x + 6, lens_y - 6, (255, 80, 90, 255), (40, 10, 15, 255), 1.4, 1.0)
        draw_outlined_line(buf, xl_hw, xl_hh, right_lens_x + 7, lens_y - 11, right_lens_x - 6, lens_y - 6, (255, 80, 90, 255), (40, 10, 15, 255), 1.4, 1.0)
        # Shouting fanged mouth
        draw_angry_fang_mouth(buf, xl_hw, xl_hh, mid_x, xl_mouth_y + 0.5, mw=7.2, mh=4.5)
        # Giant popping anger vein 💢 on upper hair + rage fire puffs
        draw_anger_vein(buf, xl_hw, xl_hh, right_lens_x + 18, lens_y - 34, size=10.5)
        draw_anger_vein(buf, xl_hw, xl_hh, left_lens_x - 20, lens_y - 22, size=7.5)

    elif key == "expr_4_surprised":
        # Pale blue shock tint + darkened lenses with giant yellow ! ! + shock rings
        apply_upper_face_tint(buf, xl_hw, xl_hh, lens_y - 42, lens_y - 4, (30, 140, 255), 95)
        darken_lenses(buf, xl_hw, xl_hh, left_lens_x, right_lens_x, lens_y, 8.5, (10, 25, 65), 195)
        for lx in (left_lens_x, right_lens_x):
            draw_outlined_line(buf, xl_hw, xl_hh, lx, lens_y - 6.2, lx, lens_y + 0.8, (255, 255, 140, 255), (255, 120, 0, 255), 1.9, 1.2)
            draw_solid_circle(buf, xl_hw, xl_hh, lx, lens_y + 5.2, 2.1, (255, 255, 140, 255), (255, 120, 0, 255), 1.1)
        # Wide open O screaming mouth
        draw_solid_circle(buf, xl_hw, xl_hh, mid_x, xl_mouth_y + 1.0, 5.2, (195, 45, 70, 255), (40, 15, 25, 255), 1.4)
        # Lightning bolts + giant flying sweat drop
        draw_shock_bolt(buf, xl_hw, xl_hh, 8, 16, 26, 42)
        draw_shock_bolt(buf, xl_hw, xl_hh, xl_hw - 8, 16, xl_hw - 26, 42)
        draw_sweat_drop(buf, xl_hw, xl_hh, left_lens_x - 20, lens_y - 6, size=10.0)

    elif key == "expr_5_shy":
        # Heavy pink blush across nose & cheeks + diagonal slashes ///
        draw_soft_circle(buf, xl_hw, xl_hh, left_lens_x - 4, lens_y + 10, 10.5, (255, 75, 125, 185))
        draw_soft_circle(buf, xl_hw, xl_hh, right_lens_x + 4, lens_y + 10, 10.5, (255, 75, 125, 185))
        draw_soft_circle(buf, xl_hw, xl_hh, mid_x, lens_y + 8, 8.0, (255, 90, 135, 140))
        for bx in (left_lens_x - 8, left_lens_x - 4, left_lens_x, right_lens_x, right_lens_x + 4, right_lens_x + 8):
            draw_thick_line(buf, xl_hw, xl_hh, bx - 1.5, lens_y + 11.5, bx + 1.5, lens_y + 7.5, (255, 45, 95, 235), 0.9)
        # Darkened magenta lenses with GIANT glowing pink hearts
        darken_lenses(buf, xl_hw, xl_hh, left_lens_x, right_lens_x, lens_y, 8.5, (55, 12, 45), 190)
        for lx in (left_lens_x, right_lens_x):
            draw_heart_icon(buf, xl_hw, xl_hh, lx, lens_y + 0.5, 5.2, (255, 75, 155, 255), (255, 240, 250, 255))
        # Cute ω cat mouth
        draw_wavy_cat_mouth(buf, xl_hw, xl_hh, mid_x, xl_mouth_y + 0.5, mw=6.8)
        # Floating large pink hearts around head
        draw_heart_icon(buf, xl_hw, xl_hh, 16, 42, 6.2, (255, 70, 150, 255), (255, 255, 255, 255))
        draw_heart_icon(buf, xl_hw, xl_hh, xl_hw - 15, 32, 7.0, (255, 70, 150, 255), (255, 255, 255, 255))
        draw_heart_icon(buf, xl_hw, xl_hh, 14, 82, 4.6, (255, 110, 175, 255), (255, 255, 255, 255))

    elif key == "expr_6_focused":
        # Cyberpunk HUD Visor beam + emerald-cyan reticles + floating lightbulb above head
        darken_lenses(buf, xl_hw, xl_hh, left_lens_x, right_lens_x, lens_y, 8.5, (5, 35, 55), 205)
        # Glowing cyan HUD visor bar connecting both lenses
        draw_thick_line(buf, xl_hw, xl_hh, left_lens_x - 10, lens_y - 3, right_lens_x + 10, lens_y - 3, (0, 245, 212, 220), 1.6)
        for lx in (left_lens_x, right_lens_x):
            draw_solid_circle(buf, xl_hw, xl_hh, lx, lens_y, 6.2, (0, 245, 212, 70), (0, 255, 220, 255), 1.3)
            draw_thick_line(buf, xl_hw, xl_hh, lx - 7.5, lens_y, lx + 7.5, lens_y, (180, 255, 245, 255), 1.1)
            draw_thick_line(buf, xl_hw, xl_hh, lx, lens_y - 7.5, lx, lens_y + 7.5, (180, 255, 245, 255), 1.1)
            draw_solid_circle(buf, xl_hw, xl_hh, lx, lens_y, 2.2, (255, 255, 255, 255))
        # Determined confident smile
        draw_thick_line(buf, xl_hw, xl_hh, mid_x - 5, xl_mouth_y + 0.5, mid_x + 1, xl_mouth_y + 2.0, (45, 25, 35, 245), 1.2)
        draw_thick_line(buf, xl_hw, xl_hh, mid_x + 1, xl_mouth_y + 2.0, mid_x + 6, xl_mouth_y - 1.0, (45, 25, 35, 245), 1.2)
        # Glowing Golden Wisdom Lightbulb 💡 at top-left/top
        bx, by = 18, 28
        draw_soft_circle(buf, xl_hw, xl_hh, bx, by, 13.0, (255, 240, 90, 140))
        draw_solid_circle(buf, xl_hw, xl_hh, bx, by, 7.2, (255, 240, 80, 255), (180, 100, 0, 255), 1.3)
        draw_rect_patch(buf, xl_hw, xl_hh, bx - 3.5, by + 6.5, bx + 3.5, by + 10.5, (190, 205, 225, 255), (70, 85, 110, 255))
        for ang in (-135, -90, -45, 0, 180):
            rad_a = math.radians(ang)
            draw_outlined_line(
                buf, xl_hw, xl_hh,
                bx + math.cos(rad_a) * 9.5, by + math.sin(rad_a) * 9.5,
                bx + math.cos(rad_a) * 13.5, by + math.sin(rad_a) * 13.5,
                (255, 245, 120, 255), (190, 105, 0, 240), 1.1, 0.8
            )

    elif key == "expr_7_sick":
        # Sickly purple-blue-green gloom over upper face + vertical gloom lines |||
        apply_upper_face_tint(buf, xl_hw, xl_hh, lens_y - 48, lens_y + 2, (55, 25, 110), 135)
        for gx in range(12, 34, 5):
            draw_outlined_line(buf, xl_hw, xl_hh, gx, 22, gx, 56, (95, 45, 165, 240), (25, 10, 55, 240), 1.1, 0.8)
        # Flushed fever cheeks
        draw_soft_circle(buf, xl_hw, xl_hh, left_lens_x - 4, lens_y + 10, 9.5, (255, 60, 85, 180))
        draw_soft_circle(buf, xl_hw, xl_hh, right_lens_x + 4, lens_y + 10, 9.5, (255, 60, 85, 180))
        # Darkened lenses with giant glowing X X dizzy eyes
        darken_lenses(buf, xl_hw, xl_hh, left_lens_x, right_lens_x, lens_y, 8.5, (25, 15, 55), 200)
        for lx in (left_lens_x, right_lens_x):
            draw_outlined_line(buf, xl_hw, xl_hh, lx - 5.2, lens_y - 5.2, lx + 5.2, lens_y + 5.2, (255, 255, 255, 255), (0, 210, 255, 255), 1.5, 1.1)
            draw_outlined_line(buf, xl_hw, xl_hh, lx + 5.2, lens_y - 5.2, lx - 5.2, lens_y + 5.2, (255, 255, 255, 255), (0, 210, 255, 255), 1.5, 1.1)
        # Large Forehead Fever Cooling Patch (退熱貼)
        draw_rect_patch(
            buf, xl_hw, xl_hh,
            mid_x - 18, lens_y - 25, mid_x + 18, lens_y - 13,
            (235, 250, 255, 250), (30, 130, 235, 255)
        )
        draw_rect_patch(
            buf, xl_hw, xl_hh,
            mid_x - 14, lens_y - 21, mid_x + 14, lens_y - 17,
            (110, 205, 255, 255), None
        )
        # Wavy dizzy mouth + Thermometer sticking out + Giant Sweat Drop + Toxic Green Bubbles
        draw_wavy_cat_mouth(buf, xl_hw, xl_hh, mid_x - 1, xl_mouth_y + 1.0, mw=6.0)
        draw_thermometer(buf, xl_hw, xl_hh, mid_x + 2, xl_mouth_y + 1.0)
        draw_sweat_drop(buf, xl_hw, xl_hh, right_lens_x + 16, lens_y - 4, size=9.5)
        draw_solid_circle(buf, xl_hw, xl_hh, 16, 86, 5.5, (138, 201, 38, 235), (35, 75, 10, 250), 1.2)
        draw_solid_circle(buf, xl_hw, xl_hh, 23, 74, 3.8, (155, 93, 229, 235), (45, 15, 85, 250), 1.1)

    rel = f"assets/xueling/expressions/{key}.png"
    save_png_rgba(os.path.join(BASE_DIR, rel), xl_hw, xl_hh, bytes(buf))
    manifest["xueling"][key] = {"path": rel, "size": [xl_hw, xl_hh], "label": f"雪靈表情 - {label}"}


# ------------------------------------------------------------------------------
# 3.2 LING FENG 7 EXAGGERATED EXPRESSIONS
# ------------------------------------------------------------------------------
# Enhance all 7 of Ling Feng's expressions on padded canvases so animations pop clearly!
lf_all_expr_specs = [
    ("expr_1_normal", "普通 (Normal)", 272, 366, None, seam_e1_e2),
    ("expr_2_smile", "超開心/閃耀 (Happy ✨)", 348, 448, seam_e1_e2, seam_e2_e3),
    ("expr_3_angry", "暴怒/爆青筋 (Angry 💢)", 432, 532, seam_e2_e3, seam_e3_e4),
    ("expr_4_surprised", "大震驚/雷擊 (Shocked ⚡)", 515, 616, seam_e3_e4, seam_e4_e5),
    ("expr_5_shy", "害羞心動/冒愛心 (Shy 💕)", 598, 687, seam_e4_e5, None),
    ("expr_6_focused", "番茄鐘極限專注 (Focused 💡)", 272, 366, None, seam_e1_e2),
    ("expr_7_sick", "重感冒/腸胃炎 (Sick 🤒🌡️)", 432, 532, seam_e2_e3, seam_e3_e4),
]

for key, label, x0, x1, l_seam, r_seam in lf_all_expr_specs:
    raw_w, raw_h, raw_data = extract_clean_sprite(
        w2, h2, b2, x0, ey0, x1, ey1, bg_color=lf_bg,
        left_seam=l_seam, right_seam=r_seam, remove_leg_gaps=False
    )
    lpad_x, lpad_y = 16, 14
    lw, lh, lbuf_bytes = pad_rgba_canvas(raw_data, raw_w, raw_h, lpad_x, lpad_y, lpad_x, 6)
    lbuf = bytearray(lbuf_bytes)

    # Facial anchor coordinates on padded Ling Feng canvas
    lf_mid_x = lw / 2.0
    lf_eye_y = lpad_y + 61.5
    lf_lex = lf_mid_x - 12.5
    lf_rex = lf_mid_x + 12.5
    lf_mouth_y = lpad_y + 71.0

    if key == "expr_2_smile":
        # Golden star pupils in both eyes + warm rosy blush + big open cheerful cat-grin + floating stars
        draw_sparkle_star(lbuf, lw, lh, lf_lex, lf_eye_y, 4.2)
        draw_sparkle_star(lbuf, lw, lh, lf_rex, lf_eye_y, 4.2)
        draw_soft_circle(lbuf, lw, lh, lf_lex - 4, lf_eye_y + 7.5, 7.5, (255, 95, 130, 165))
        draw_soft_circle(lbuf, lw, lh, lf_rex + 4, lf_eye_y + 7.5, 7.5, (255, 95, 130, 165))
        draw_happy_open_mouth(lbuf, lw, lh, lf_mid_x, lf_mouth_y, mw=6.2, mh=4.5)
        draw_sparkle_star(lbuf, lw, lh, 14, 28, 9.0)
        draw_sparkle_star(lbuf, lw, lh, lw - 14, 24, 9.5)
        draw_sparkle_star(lbuf, lw, lh, 18, 82, 6.0)

    elif key == "expr_3_angry":
        # Crimson rage shadow over forehead + glowing red eye glints + fanged shouting mouth + giant 💢 veins
        apply_upper_face_tint(lbuf, lw, lh, lf_eye_y - 36, lf_eye_y - 2, (165, 10, 30), 120)
        for ex in (lf_lex, lf_rex):
            draw_solid_circle(lbuf, lw, lh, ex, lf_eye_y + 0.5, 3.2, (255, 45, 60, 245), (255, 220, 90, 240), 0.9)
        draw_outlined_line(lbuf, lw, lh, lf_lex - 6, lf_eye_y - 8, lf_lex + 5, lf_eye_y - 4, (255, 70, 80, 255), (35, 10, 15, 255), 1.3, 0.9)
        draw_outlined_line(lbuf, lw, lh, lf_rex + 6, lf_eye_y - 8, lf_rex - 5, lf_eye_y - 4, (255, 70, 80, 255), (35, 10, 15, 255), 1.3, 0.9)
        draw_angry_fang_mouth(lbuf, lw, lh, lf_mid_x, lf_mouth_y, mw=6.8, mh=4.2)
        draw_anger_vein(lbuf, lw, lh, lf_rex + 16, lf_eye_y - 28, size=10.0)
        draw_anger_vein(lbuf, lw, lh, lf_lex - 16, lf_eye_y - 18, size=7.2)

    elif key == "expr_4_surprised":
        # Blue shock tint + wide-eyed white shock rings + big O gasping mouth + lightning bolts + giant sweat drop
        apply_upper_face_tint(lbuf, lw, lh, lf_eye_y - 35, lf_eye_y - 3, (30, 140, 255), 95)
        for ex in (lf_lex, lf_rex):
            draw_solid_circle(lbuf, lw, lh, ex, lf_eye_y, 4.2, (255, 255, 255, 250), (20, 75, 175, 255), 1.2)
            draw_solid_circle(lbuf, lw, lh, ex, lf_eye_y, 1.6, (15, 35, 90, 255))
        draw_solid_circle(lbuf, lw, lh, lf_mid_x, lf_mouth_y + 0.5, 4.8, (195, 45, 70, 255), (40, 15, 25, 255), 1.3)
        draw_shock_bolt(lbuf, lw, lh, 7, 14, 24, 38)
        draw_shock_bolt(lbuf, lw, lh, lw - 7, 14, lw - 24, 38)
        draw_sweat_drop(lbuf, lw, lh, lf_lex - 18, lf_eye_y - 4, size=9.5)

    elif key == "expr_5_shy":
        # Heavy pink blush + diagonal blush slashes /// + glowing pink heart pupils + ω cat mouth + floating hearts
        draw_soft_circle(lbuf, lw, lh, lf_lex - 3, lf_eye_y + 7.5, 9.5, (255, 75, 125, 185))
        draw_soft_circle(lbuf, lw, lh, lf_rex + 3, lf_eye_y + 7.5, 9.5, (255, 75, 125, 185))
        draw_soft_circle(lbuf, lw, lh, lf_mid_x, lf_eye_y + 6.5, 7.5, (255, 90, 135, 135))
        for bx in (lf_lex - 6, lf_lex - 2, lf_lex + 2, lf_rex - 2, lf_rex + 2, lf_rex + 6):
            draw_thick_line(lbuf, lw, lh, bx - 1.5, lf_eye_y + 9.0, bx + 1.5, lf_eye_y + 5.5, (255, 40, 95, 240), 0.9)
        for ex in (lf_lex, lf_rex):
            draw_heart_icon(lbuf, lw, lh, ex, lf_eye_y + 0.5, 3.8, (255, 70, 155, 255), (255, 245, 250, 255))
        draw_wavy_cat_mouth(lbuf, lw, lh, lf_mid_x, lf_mouth_y, mw=6.2)
        draw_heart_icon(lbuf, lw, lh, 14, 34, 5.8, (255, 70, 150, 255), (255, 255, 255, 255))
        draw_heart_icon(lbuf, lw, lh, lw - 14, 26, 6.4, (255, 70, 150, 255), (255, 255, 255, 255))
        draw_heart_icon(lbuf, lw, lh, 14, 72, 4.4, (255, 110, 175, 255), (255, 255, 255, 255))

    elif key == "expr_6_focused":
        # Cyber AR Holographic Visor across eyes + cyan target reticles + Glowing Wisdom Lightbulb 💡 above head
        draw_rect_patch(
            lbuf, lw, lh,
            lf_lex - 11, lf_eye_y - 6, lf_rex + 11, lf_eye_y + 5,
            (0, 195, 255, 105), (0, 245, 212, 245)
        )
        for ex in (lf_lex, lf_rex):
            draw_solid_circle(lbuf, lw, lh, ex, lf_eye_y, 4.5, (0, 245, 212, 90), (190, 255, 245, 255), 1.1)
            draw_thick_line(lbuf, lw, lh, ex - 5.5, lf_eye_y, ex + 5.5, lf_eye_y, (255, 255, 255, 250), 0.9)
            draw_thick_line(lbuf, lw, lh, ex, lf_eye_y - 5.5, ex, lf_eye_y + 5.5, (255, 255, 255, 250), 0.9)
        # Glowing Golden Wisdom Lightbulb 💡 at top-right/top-left
        bx, by = 16, 24
        draw_soft_circle(lbuf, lw, lh, bx, by, 12.0, (255, 240, 90, 140))
        draw_solid_circle(lbuf, lw, lh, bx, by, 6.8, (255, 240, 80, 255), (180, 100, 0, 255), 1.2)
        draw_rect_patch(lbuf, lw, lh, bx - 3.2, by + 6.0, bx + 3.2, by + 9.5, (190, 205, 225, 255), (70, 85, 110, 255))
        for ang in (-135, -90, -45, 0, 180):
            rad_a = math.radians(ang)
            draw_outlined_line(
                lbuf, lw, lh,
                bx + math.cos(rad_a) * 8.8, by + math.sin(rad_a) * 8.8,
                bx + math.cos(rad_a) * 12.5, by + math.sin(rad_a) * 12.5,
                (255, 245, 120, 255), (190, 105, 0, 240), 1.0, 0.8
            )

    elif key == "expr_7_sick":
        # Sickly purple gloom + vertical gloom lines ||| + Fever cooling patch + X X eyes + Thermometer + Sweat + Toxic bubbles
        apply_upper_face_tint(lbuf, lw, lh, lf_eye_y - 40, lf_eye_y + 2, (55, 25, 110), 135)
        for gx in range(10, 30, 5):
            draw_outlined_line(lbuf, lw, lh, gx, 18, gx, 48, (95, 45, 165, 240), (25, 10, 55, 240), 1.0, 0.8)
        draw_soft_circle(lbuf, lw, lh, lf_lex - 3, lf_eye_y + 7.5, 8.5, (255, 60, 85, 180))
        draw_soft_circle(lbuf, lw, lh, lf_rex + 3, lf_eye_y + 7.5, 8.5, (255, 60, 85, 180))
        for ex in (lf_lex, lf_rex):
            draw_solid_circle(lbuf, lw, lh, ex, lf_eye_y, 5.2, (25, 15, 55, 210))
            draw_outlined_line(lbuf, lw, lh, ex - 4.2, lf_eye_y - 4.2, ex + 4.2, lf_eye_y + 4.2, (255, 255, 255, 255), (0, 210, 255, 255), 1.3, 1.0)
            draw_outlined_line(lbuf, lw, lh, ex + 4.2, lf_eye_y - 4.2, ex - 4.2, lf_eye_y + 4.2, (255, 255, 255, 255), (0, 210, 255, 255), 1.3, 1.0)
        # Large Forehead Fever Cooling Patch (退熱貼)
        draw_rect_patch(
            lbuf, lw, lh,
            lf_mid_x - 16, lf_eye_y - 21, lf_mid_x + 16, lf_eye_y - 10,
            (235, 250, 255, 250), (30, 130, 235, 255)
        )
        draw_rect_patch(
            lbuf, lw, lh,
            lf_mid_x - 12, lf_eye_y - 17, lf_mid_x + 12, lf_eye_y - 14,
            (110, 205, 255, 255), None
        )
        draw_wavy_cat_mouth(lbuf, lw, lh, lf_mid_x - 1, lf_mouth_y, mw=5.5)
        draw_thermometer(lbuf, lw, lh, lf_mid_x + 1, lf_mouth_y)
        draw_sweat_drop(lbuf, lw, lh, lf_rex + 15, lf_eye_y - 3, size=9.0)
        draw_solid_circle(lbuf, lw, lh, 14, 76, 5.0, (138, 201, 38, 235), (35, 75, 10, 250), 1.2)
        draw_solid_circle(lbuf, lw, lh, 20, 65, 3.5, (155, 93, 229, 235), (45, 15, 85, 250), 1.1)

    rel = f"assets/lingfeng/expressions/{key}.png"
    save_png_rgba(os.path.join(BASE_DIR, rel), lw, lh, bytes(lbuf))
    manifest["lingfeng"][key] = {"path": rel, "size": [lw, lh], "label": f"凌風表情 - {label}"}



# ==============================================================================
# 4. GENERATE 23 ISLAND SHOP ITEM SVG ICONS & STATUS EFFECT SVGS
# ==============================================================================
print("Generating 23 Create or Destroy Island Shop item SVG icons & effect badges...")

shop_items_catalog = [
    ("water_normal", "一般水", "+5 恢復值", 5, "💧", "#1472FF", "#0A2540"),
    ("water_pure", "純水", "+10 恢復值", 8, "💦", "#00D2FF", "#0A2E4D"),
    ("water_spring", "靈泉水", "+100 恢復值", 50, "✨", "#00F5D4", "#083A3A"),
    ("tea_black_latte", "紅茶拿鐵", "+20 恢復經驗值", 15, "🧋", "#E07A5F", "#3D1E16"),
    ("tea_matcha_latte", "抹茶拿鐵", "+20 恢復經驗值", 15, "🍵", "#52B788", "#1B4332"),
    ("tea_boba", "珍珠奶茶", "+30 恢復經驗值", 20, "🧋", "#F4A261", "#3B2314"),
    ("tea_oolong", "烏龍奶茶", "+30 恢復經驗值", 20, "🥤", "#D4A373", "#33261A"),
    ("food_hotdog", "熱狗", "+5 恢復經驗值", 5, "🌭", "#E63946", "#3D1014"),
    ("food_tea_egg", "茶葉蛋", "+5 恢復經驗值", 5, "🥚", "#B5838D", "#2E1F24"),
    ("food_bread", "麵包", "+10 恢復值", 8, "🍞", "#F4A261", "#3D2714"),
    ("food_chawanmushi", "茶碗蒸", "+15 恢復經驗值", 12, "🍮", "#FFD166", "#3D3114"),
    ("food_noodles", "泡麵", "+15 經驗值", 15, "🍜", "#FF9F1C", "#3D2408"),
    ("food_chicken_cutlet", "炸雞排", "+20 恢復經驗值", 18, "🍗", "#F77F00", "#3D1F00"),
    ("food_bun", "包子", "+40 恢復經驗值", 25, "🥟", "#EAE2B7", "#333022"),
    ("food_shaobing", "燒餅油條", "+40 恢復經驗值", 25, "🥖", "#E9C46A", "#382E16"),
    ("food_bento", "便當", "+80 恢復經驗值", 40, "🍱", "#FF595E", "#3B1517"),
    ("ice_cream", "冰淇淋", "+10 經驗值", 10, "🍦", "#FF99C8", "#3B1D2C"),
    ("haagen_dazs", "哈根達斯冰品", "+30 恢復經驗值", 22, "🍨", "#C77DFF", "#2C1642"),
    ("bad_expired_water", "過期水", "-50 恢復值", 3, "☠️", "#8AC926", "#23330A"),
    ("bad_expired_food", "過期食品", "-70 恢復經驗值", 3, "🦠", "#6A994E", "#1B2913"),
    ("bad_mystery_drink", "不知放多少天的飲料", "-70 恢復 (觸發腸胃炎)", 3, "🧪", "#9B5DE5", "#24133B"),
    ("med_cold", "感冒藥", "+25 恢復 (治感冒)", 18, "💊", "#4CC9F0", "#10323D"),
    ("med_gastro_3d", "腸胃藥三天份", "+100 恢復 (治腸胃炎)", 45, "🏥", "#06D6A0", "#063B2C"),
]

for item_id, name, effect_str, price, emoji, accent, dark_bg in shop_items_catalog:
    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="120" height="120">
  <defs>
    <linearGradient id="bg_{item_id}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0D0F14"/>
      <stop offset="100%" stop-color="{dark_bg}"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="112" height="112" rx="18" fill="url(#bg_{item_id})" stroke="{accent}" stroke-width="2.5"/>
  <circle cx="60" cy="48" r="28" fill="{accent}" fill-opacity="0.16" stroke="{accent}" stroke-width="1" stroke-dasharray="4 3"/>
  <text x="60" y="58" font-size="34" text-anchor="middle">{emoji}</text>
  <text x="60" y="90" font-family="sans-serif" font-size="12" font-weight="bold" fill="#E6EAF0" text-anchor="middle">{name}</text>
  <text x="60" y="106" font-family="sans-serif" font-size="10" fill="{accent}" text-anchor="middle">{effect_str}</text>
</svg>"""
    rel = f"assets/shop_items/{item_id}.svg"
    with open(os.path.join(BASE_DIR, rel), "w", encoding="utf-8") as f:
        f.write(svg_content)
    manifest["shop_items"][item_id] = {
        "path": rel,
        "name": name,
        "effect": effect_str,
        "price": price,
        "emoji": emoji,
        "accent": accent,
    }


# ==============================================================================
# 5. RENDER VISUAL PREVIEW CONTACT SHEETS FOR USER VERIFICATION
# ==============================================================================
print("Rendering visual preview contact sheets...")

def load_png_from_manifest(rel_path):
    # We already have the dimensions; let's decode via gdk_pixbuf or keep in memory
    pass

# Let's build contact sheets directly in memory as we load the saved PNGs using zlib!
def read_our_png(path):
    with open(path, "rb") as f:
        data = f.read()
    pos = 8
    w = h = 0
    idat = bytearray()
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        ctype = data[pos + 4 : pos + 8]
        chunk_data = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            w, h = struct.unpack(">II", chunk_data[:8])
        elif ctype == b"IDAT":
            idat.extend(chunk_data)
    raw = zlib.decompress(bytes(idat))
    rgba = bytearray(w * h * 4)
    stride = w * 4
    for y in range(h):
        rgba[y * stride : (y + 1) * stride] = raw[y * (stride + 1) + 1 : (y + 1) * (stride + 1)]
    return w, h, rgba

def blit_scaled(canvas, cw, ch, src_rgba, sw, sh, dst_x, dst_y, max_w, max_h):
    scale = min(max_w / max(1, sw), max_h / max(1, sh))
    nw = max(1, int(round(sw * scale)))
    nh = max(1, int(round(sh * scale)))
    ox = dst_x + (max_w - nw) // 2
    oy = dst_y + (max_h - nh) // 2
    for y in range(nh):
        sy = min(sh - 1, int(y / scale))
        for x in range(nw):
            sx = min(sw - 1, int(x / scale))
            sidx = (sy * sw + sx) * 4
            sa = src_rgba[sidx + 3] / 255.0
            if sa <= 0:
                continue
            tx, ty = ox + x, oy + y
            if 0 <= tx < cw and 0 <= ty < ch:
                didx = (ty * cw + tx) * 4
                canvas[didx] = int(src_rgba[sidx] * sa + canvas[didx] * (1.0 - sa))
                canvas[didx + 1] = int(src_rgba[sidx + 1] * sa + canvas[didx + 1] * (1.0 - sa))
                canvas[didx + 2] = int(src_rgba[sidx + 2] * sa + canvas[didx + 2] * (1.0 - sa))
                canvas[didx + 3] = 255

def create_card_grid_preview(out_path, items, cols=5, cell_w=170, cell_h=220, accent=(20, 114, 255)):
    rows = (len(items) + cols - 1) // cols
    pad = 16
    cw = cols * cell_w + (cols + 1) * pad
    ch = rows * cell_h + (rows + 1) * pad
    canvas = bytearray(cw * ch * 4)
    # Fill dark esports background #0D0F14 with subtle checkerboard in cells
    for y in range(ch):
        for x in range(cw):
            idx = (y * cw + x) * 4
            canvas[idx] = 13
            canvas[idx + 1] = 15
            canvas[idx + 2] = 20
            canvas[idx + 3] = 255

    for idx_item, rel_path in enumerate(items):
        r = idx_item // cols
        c = idx_item % cols
        cx0 = pad + c * (cell_w + pad)
        cy0 = pad + r * (cell_h + pad)
        # Draw subtle dark card with checkerboard to prove alpha transparency
        for y in range(cy0, cy0 + cell_h):
            for x in range(cx0, cx0 + cell_w):
                pidx = (y * cw + x) * 4
                is_border = (x in (cx0, cx0 + cell_w - 1) or y in (cy0, cy0 + cell_h - 1))
                if is_border:
                    canvas[pidx] = accent[0]
                    canvas[pidx + 1] = accent[1]
                    canvas[pidx + 2] = accent[2]
                else:
                    checker = ((x // 12) + (y // 12)) % 2
                    base = 24 if checker else 32
                    canvas[pidx] = base
                    canvas[pidx + 1] = base + 3
                    canvas[pidx + 2] = base + 10
        full_p = os.path.join(BASE_DIR, rel_path)
        sw, sh, srgba = read_our_png(full_p)
        blit_scaled(canvas, cw, ch, srgba, sw, sh, cx0 + 10, cy0 + 10, cell_w - 20, cell_h - 20)

    save_png_rgba(out_path, cw, ch, bytes(canvas))

# Preview 1: Xueling Turnaround + Heads + Details
create_card_grid_preview(
    os.path.join(ASSETS_DIR, "previews/xueling_turnaround_and_heads.png"),
    [
        "assets/xueling/turnaround/main_fullbody.png",
        "assets/xueling/turnaround/turn_1_front.png",
        "assets/xueling/turnaround/turn_2_left45.png",
        "assets/xueling/turnaround/turn_3_side.png",
        "assets/xueling/turnaround/turn_4_right45.png",
        "assets/xueling/turnaround/turn_5_back.png",
        "assets/xueling/heads/head_1_front.png",
        "assets/xueling/heads/head_2_left45.png",
        "assets/xueling/heads/head_3_side.png",
        "assets/xueling/heads/head_4_right45.png",
        "assets/xueling/heads/head_5_back.png",
        "assets/xueling/details/prop_sunglasses.png",
        "assets/xueling/details/costume_jacket_front.png",
        "assets/xueling/details/costume_jacket_back.png",
        "assets/xueling/details/costume_shoes.png",
    ],
    cols=5, cell_w=160, cell_h=210, accent=(20, 114, 255)
)

# Preview 2: Ling Feng Turnaround + Props + Costume
create_card_grid_preview(
    os.path.join(ASSETS_DIR, "previews/lingfeng_turnaround_and_props.png"),
    [
        "assets/lingfeng/turnaround/turn_1_front.png",
        "assets/lingfeng/turnaround/turn_2_side.png",
        "assets/lingfeng/turnaround/turn_3_back.png",
        "assets/lingfeng/turnaround/turn_4_three_quarter.png",
        "assets/lingfeng/turnaround/turn_5_top.png",
        "assets/lingfeng/props/prop_carkey.png",
        "assets/lingfeng/props/prop_sunglasses.png",
        "assets/lingfeng/props/prop_headphones.png",
        "assets/lingfeng/props/prop_gaming_chair.png",
        "assets/lingfeng/turnaround/racing_scene.png",
        "assets/lingfeng/details/costume_jacket_front.png",
        "assets/lingfeng/details/costume_jacket_back.png",
        "assets/lingfeng/details/costume_hood.png",
        "assets/lingfeng/details/costume_pants.png",
        "assets/lingfeng/details/costume_shoes.png",
    ],
    cols=5, cell_w=160, cell_h=210, accent=(30, 58, 138)
)

# Preview 3: Both Characters' 7 Expressions Side-by-Side (14 expressions total)
create_card_grid_preview(
    os.path.join(ASSETS_DIR, "previews/both_characters_14_expressions.png"),
    [
        "assets/lingfeng/expressions/expr_1_normal.png",
        "assets/lingfeng/expressions/expr_2_smile.png",
        "assets/lingfeng/expressions/expr_3_angry.png",
        "assets/lingfeng/expressions/expr_4_surprised.png",
        "assets/lingfeng/expressions/expr_5_shy.png",
        "assets/lingfeng/expressions/expr_6_focused.png",
        "assets/lingfeng/expressions/expr_7_sick.png",
        "assets/xueling/expressions/expr_1_normal.png",
        "assets/xueling/expressions/expr_2_happy.png",
        "assets/xueling/expressions/expr_3_angry.png",
        "assets/xueling/expressions/expr_4_surprised.png",
        "assets/xueling/expressions/expr_5_shy.png",
        "assets/xueling/expressions/expr_6_focused.png",
        "assets/xueling/expressions/expr_7_sick.png",
    ],
    cols=7, cell_w=135, cell_h=150, accent=(20, 114, 255)
)

with open(os.path.join(ASSETS_DIR, "asset_manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

print("All Step 1 assets and previews built successfully!")
