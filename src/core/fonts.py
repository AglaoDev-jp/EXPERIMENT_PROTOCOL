# core/fonts.py
# -*- coding: utf-8 -*-
"""
Noto Sans JP をプロジェクト全体で統一的に扱うためのヘルパ。
- Pathlibでパス解決（assets/fonts/NotoSansJP-Regular.ttf 固定）
- サイズごとにフォントオブジェクトをキャッシュ（lru_cache）
- 影/縁取り付きの描画ヘルパ（UIテキストを読みやすく）
"""

from __future__ import annotations
from pathlib import Path
from functools import lru_cache
import pygame

# プロジェクトのルート（core/ から2階層遡る）
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FONT_PATH = PROJECT_ROOT / "assets" / "fonts" / "NotoSansJP-Regular.ttf"

if not FONT_PATH.exists():
    raise FileNotFoundError(f"フォントが見つかりません: {FONT_PATH}")

# ------------------------------------------------------------
# フォント取得（サイズごとにキャッシュ）
# ------------------------------------------------------------
@lru_cache(maxsize=32)
def get_font(size: int) -> pygame.font.Font:
    """
    指定ポイントサイズの Noto Sans JP フォントを返す。
    - pygame.font は初期化済み（pygame.init() 後）であること。
    - lru_cache で再利用（パフォーマンス＆一貫性）
    """
    # NOTE: pygame.font.Font は Path でもOKだが、古い環境配慮で str() 化
    return pygame.font.Font(str(FONT_PATH), size)

# ------------------------------------------------------------
# テキスト描画ヘルパ（影・縁取り）
# ------------------------------------------------------------
def render_text(
    text: str,
    size: int = 20,
    color: tuple[int, int, int] = (255, 255, 255),
    *,
    shadow: bool = True,
    shadow_offset: tuple[int, int] = (1, 1),
    outline: bool = False,
    outline_color: tuple[int, int, int] = (0, 0, 0),
    outline_px: int = 2,
) -> pygame.Surface:
    """
    指定文字列をサーフェスに描画して返す。
    - 影/shadow: 背景と馴染ませやすく視認性UP
    - 縁取り/outline: コントラストが弱い背景で視認性UP
    """
    font = get_font(size)
    base = font.render(text, True, color)

    # 影のみ（軽量）
    if shadow and not outline:
        sx, sy = shadow_offset
        surf = pygame.Surface(
            (base.get_width() + abs(sx), base.get_height() + abs(sy)),
            pygame.SRCALPHA,
        )
        # 影
        shadow_img = font.render(text, True, (0, 0, 0))
        surf.blit(shadow_img, (max(sx, 0), max(sy, 0)))
        # 本体
        surf.blit(base, (0, 0))
        return surf

    # 縁取りあり（8方向にアウトラインを敷く簡易法）
    if outline:
        pad = outline_px
        w, h = base.get_width() + pad * 2, base.get_height() + pad * 2
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for dx in range(-outline_px, outline_px + 1):
            for dy in range(-outline_px, outline_px + 1):
                if dx == 0 and dy == 0:
                    continue
                surf.blit(font.render(text, True, outline_color), (pad + dx, pad + dy))
        surf.blit(base, (pad, pad))
        return surf

    # 影・縁取りなし
    return base
