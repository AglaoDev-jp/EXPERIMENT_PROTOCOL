# core/asset_utils.py
# -*- coding: utf-8 -*-
"""
画像が無いときに使う“見やすいプレースホルダー”を生成するユーティリティ。
- スプライト用（丸/四角＋ラベル）
- 壁テクスチャ用（対角線パターン）
- 床/天井テクスチャ用（チェッカー or ライン）→ (TILE, TILE, 3) np.ndarray を返す
"""

from __future__ import annotations
from pathlib import Path
from typing import Tuple, Optional
import pygame
import numpy as np

MAGENTA = (220, 0, 220)   # “素材なし”感が分かりやすい色
WHITE   = (255, 255, 255)
GRAY1   = (180, 180, 180)
GRAY2   = (120, 120, 120)

def load_or_placeholder(base_dir: Path, rel_path: str, *,
                        size: Tuple[int,int]=(64,64),
                        shape: str="circle",
                        label: Optional[str]=None) -> pygame.Surface:
    """
    スプライト画像ローダ。失敗したらプレースホルダーを返す。
    - size: 出力Surfaceサイズ
    - shape: "circle" / "rect"
    - label: 2〜3文字程度の略称を中央に描く（AX, OR, KYなど）
    """
    # 実ファイル読み込みを試す
    try:
        path = (base_dir / rel_path) if rel_path else None
        if path and path.exists():
            img = pygame.image.load(str(path)).convert_alpha()
            return pygame.transform.smoothscale(img, size)
    except Exception:
        pass  # 失敗→プレースホルダーへ

    w, h = size
    surf = pygame.Surface(size, pygame.SRCALPHA)

    # 背景（マゼンタ）
    surf.fill((0, 0, 0, 0))
    bg = pygame.Surface(size, pygame.SRCALPHA)
    bg.fill((*MAGENTA, 220))
    surf.blit(bg, (0, 0))

    # 形状（丸 or 角丸四角）
    if shape == "circle":
        pygame.draw.ellipse(surf, (255, 255, 255, 230), (2, 2, w-4, h-4), width=3)
    else:
        pygame.draw.rect(surf, (255, 255, 255, 230), (2, 2, w-4, h-4), width=3, border_radius=10)

    # ラベル表示（簡易・英数のみ）
    if label:
        try:
            font = pygame.font.SysFont(None, int(min(w, h) * 0.45))
            text = font.render(label, True, WHITE)
            surf.blit(text, (w//2 - text.get_width()//2, h//2 - text.get_height()//2))
        except Exception:
            pass

    return surf

# ---------- 壁/床/天井のプレースホルダー ----------

def make_wall_placeholder_surface(tile_px: int=64) -> pygame.Surface:
    """
    壁用パターン（マゼンタ地に白の対角線）。1タイル分のSurfaceを返す。
    """
    s = pygame.Surface((tile_px, tile_px)).convert()
    s.fill(MAGENTA)
    # 対角線グリッド
    step = max(4, tile_px // 8)
    for x in range(0, tile_px, step):
        pygame.draw.line(s, WHITE, (x, 0), (0, x), 2)
        pygame.draw.line(s, WHITE, (tile_px-1, x), (x, tile_px-1), 2)
    return s

def make_floor_placeholder_array(tile_px: int=64) -> np.ndarray:
    """
    床用パターン（チェッカー）。(tile_px, tile_px, 3) の uint8 ndarray。
    """
    arr = np.zeros((tile_px, tile_px, 3), dtype=np.uint8)
    cell = max(4, tile_px // 8)
    for y in range(tile_px):
        for x in range(tile_px):
            arr[y, x] = GRAY1 if ((x // cell) + (y // cell)) % 2 == 0 else GRAY2
    return arr

def make_ceiling_placeholder_array(tile_px: int=64) -> np.ndarray:
    """
    天井用パターン（薄紫のグラデ＋点）。(tile_px, tile_px, 3)
    """
    arr = np.zeros((tile_px, tile_px, 3), dtype=np.uint8)
    base = np.array([200, 160, 220], dtype=np.uint8)
    for y in range(tile_px):
        shade = base * (0.8 + 0.2 * (y / max(1, tile_px-1)))
        arr[y, :, :] = np.clip(shade, 0, 255)
    # 点を少し
    for y in range(0, tile_px, max(4, tile_px // 10)):
        for x in range(0, tile_px, max(4, tile_px // 10)):
            arr[y, x] = WHITE
    return arr
