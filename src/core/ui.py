# core/ui.py
# -*- coding: utf-8 -*-
import pygame
from typing import Optional
from core.fonts import render_text

import math
from typing import List, Tuple

"""
共通UI部品：
- ToastManager: 一定時間表示されるトースト風メッセージ
- ラベル描画（角丸背景+余白）ヘルパ
"""
# --------------------------------------------------------------------------------------
# 前面固定ラベル：blit_pill_label_midtop
#   ・画面の「X=中央」「Y=top_y」から下方向へ表示するピル型（角丸）ラベル。
#   ・背景は半透明、文字はアウトライン付きで可読性を確保。
#   ・世界座標に貼るのではなく、スクリーン固定なので壁に隠れません。
# --------------------------------------------------------------------------------------

def _render_text_with_outline(text: str, font: pygame.font.Font,
                              color=(255, 255, 255),
                              outline_color=(0, 0, 0),
                              outline_px: int = 2) -> pygame.Surface:
    """テキストにアウトライン（縁取り）を付けたSurfaceを作成する。
    outline_px=0 の場合は通常レンダリングのみ。
    """
    # 先に文字本体
    text_surf = font.render(text, True, color)

    if outline_px <= 0:
        return text_surf

    # アウトラインは黒テキストを周囲8方向に薄くずらして重ねる簡易法
    base = font.render(text, True, outline_color)
    w, h = text_surf.get_width() + outline_px * 2, text_surf.get_height() + outline_px * 2
    surf = pygame.Surface((w, h), pygame.SRCALPHA)

    # 8方向に配置（角含む）
    offs = [-outline_px, 0, outline_px]
    for ox in offs:
        for oy in offs:
            if ox == 0 and oy == 0:
                continue
            surf.blit(base, (ox + outline_px, oy + outline_px))

    # 真ん中に本体
    surf.blit(text_surf, (outline_px, outline_px))
    return surf


def _draw_round_rect(dest: pygame.Surface, rect: pygame.Rect,
                     bg_rgba=(0, 0, 0, 160), radius: int = 8) -> None:
    """半透明の角丸矩形を描画する。"""
    # 角丸とアルファを両立させるため、専用の透過Surfaceに描画してから合成
    tmp = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(tmp, bg_rgba, tmp.get_rect(), border_radius=radius)
    dest.blit(tmp, rect.topleft)


def blit_pill_label_midtop(screen: pygame.Surface, text: str,
                           center_x: int, top_y: int,
                           size: int = 18,
                           text_color=(255, 255, 255),
                           outline_color=(0, 0, 0),
                           outline_px: int = 2,
                           bg_rgba=(0, 0, 0, 170),
                           radius: int = 6,
                           pad_x: int = 12, pad_y: int = 6) -> pygame.Rect:
    """画面固定の“ピル型ラベル”を、(center_x, top_y) を上辺中央として描画する。

    Parameters
    ----------
    screen : pygame.Surface
        描画先（メイン画面）
    text : str
        表示文字列（例：「古い鍵が必要」「E：開ける」）
    center_x, top_y : int
        画面上の配置。center_x=中央X、top_y=上端Y（ここから下方向に伸びます）
    size : int
        フォントサイズ
    text_color, outline_color, outline_px :
        文字色・縁取り色と太さ（0で縁取りなし）
    bg_rgba : tuple
        背景色（RGBA）。Aを上げるほど不透明に
    radius : int
        角丸半径
    pad_x, pad_y : int
        背景内側の左右・上下余白

    Returns
    -------
    pygame.Rect : 描画した矩形
    """
    # フォント生成（デフォルト）
    font = pygame.font.Font(None, size)

    # 縁取り付きテキストSurface
    text_surf = _render_text_with_outline(text, font, text_color, outline_color, outline_px)

    # 背景サイズ（余白ぶんを足す）
    bw = text_surf.get_width() + pad_x * 2
    bh = text_surf.get_height() + pad_y * 2

    # top-left を計算（center_x で中央寄せ）
    left = int(center_x - bw // 2)
    top  = int(top_y)

    # 画面外にはみ出さないようクランプ（特に上端）
    sw, sh = screen.get_size()
    if left < 8:
        left = 8
    if left + bw > sw - 8:
        left = sw - 8 - bw
    if top < 8:
        top = 8
    if top + bh > sh - 8:
        top = sh - 8 - bh

    rect = pygame.Rect(left, top, bw, bh)

    # 背景（半透明の角丸）
    _draw_round_rect(screen, rect, bg_rgba=bg_rgba, radius=radius)

    # テキスト本体
    tx = rect.left + pad_x
    ty = rect.top + pad_y
    screen.blit(text_surf, (tx, ty))

    return rect

def draw_label(
    surface: pygame.Surface,
    text: str,
    *,
    size: int = 18,
    pos: tuple[int, int] = (10, 10),
    anchor: str = "topleft",
    bg_color: tuple[int, int, int, int] = (0, 0, 0, 150),
):
    """
    角丸の半透明背景の上にテキストを載せて描画。
    - 戻り値: 実際に描画した矩形（レイアウトに使える）
    """
    txt = render_text(text, size=size, color=(255, 255, 255), outline=True)
    padding = 8
    w, h = txt.get_width() + padding * 2, txt.get_height() + padding * 2
    bg = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(bg, bg_color, bg.get_rect(), border_radius=8)
    rect = bg.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(bg, rect.topleft)
    surface.blit(txt, (rect.left + padding, rect.top + padding))
    return rect

class ToastManager:
    """
    画面下部センターに一定時間だけ表示するトースト。
    - show(text, ms): メッセージ表示開始（msミリ秒）
    - draw(surface, now_ms, screen_w, screen_h): フレームごとに呼ぶ
    """
    def __init__(self, *, default_ms: int = 1200, size: int = 20):
        self.text: Optional[str] = None
        self.until_ms: int = 0
        self.default_ms = default_ms
        self.size = size

    def show(self, text: str, ms: Optional[int] = None):
        dur = ms if ms is not None else self.default_ms
        self.text = text
        self.until_ms = pygame.time.get_ticks() + int(dur)

    def draw(self, surface: pygame.Surface, now_ms: int, screen_w: int, screen_h: int):
        if not self.text or now_ms > self.until_ms:
            return
        txt = render_text(self.text, size=self.size, color=(255, 255, 255), outline=True)
        w, h = txt.get_width() + 16, txt.get_height() + 12
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(bg, (0, 0, 0, 160), bg.get_rect(), border_radius=8)
        rect = bg.get_rect()
        rect.centerx = screen_w // 2
        rect.bottom = screen_h - 14
        surface.blit(bg, rect.topleft)
        surface.blit(txt, (rect.left + 8, rect.top + 6))

_WORLD_TOASTS: list[tuple[float, int, int, str]] = []  # (depth, sx, sy, text)

def begin_world_toasts() -> None:
    """今フレームのワールドトーストを初期化"""
    _WORLD_TOASTS.clear()

def _project_tile_to_screen(tx: int, ty: int,
                            player_x: float, player_y: float, player_angle: float,
                            *, fov_rad: float) -> tuple[int, float, float] | None:
    """
    タイル中心を画面へ投影し、(ray_index, dist, screen_x) を返す。
    視野外なら None。
    - ray_index: Zバッファ参照用（0..NUM_RAYS-1）
    - dist: プレイヤーからタイル中心までの距離
    - screen_x: ピクセルX座標
    """
    # タイル中心のワールド座標(px)
    wx = tx * TILE + TILE * 0.5
    wy = ty * TILE + TILE * 0.5

    dx = wx - player_x
    dy = wy - player_y
    dist = math.hypot(dx, dy)
    if dist < 1e-3:
        return None

    # 相対角 = ターゲット方向 - 視線方向、を [-pi, pi] に正規化
    ang_to = math.atan2(dy, dx)
    rel = (ang_to - player_angle + math.pi) % (2 * math.pi) - math.pi

    # FOV外は描かない
    half = fov_rad * 0.5
    if rel < -half or rel > half:
        return None

    # レイ番号へ
    ray_index = int((rel + half) / DELTA_ANGLE)
    if ray_index < 0 or ray_index >= NUM_RAYS:
        return None

    # 画面X（中央を基準に角度から算出）
    # 焦点距離
    screen_cx = WIDTH // 2
    dist_to_plane = screen_cx / math.tan(half)
    screen_x = int(screen_cx + math.tan(rel) * dist_to_plane)

    return ray_index, dist, screen_x

def emit_label_for_tile(tx: int, ty: int, text: str,
                        zbuffer: List[float],
                        overlap_frac: float = 0.18,
                        *,
                        player_x: float = None,
                        player_y: float = None,
                        player_angle: float = None,
                        fov_deg: float = None) -> None:
    """
    互換API：既存の呼び出しはそのまま使えます。
    - tx, ty       : タイル座標
    - text        : 表示テキスト（例："E：押す"）
    - zbuffer     : レイキャストの距離配列（壁の手前/奥判定に必須）
    - overlap_frac: 少し上に浮かせる率（0.0=中央, 0.18推奨）
    - player_*    : 未指定なら game_state から取得（循環import回避のため遅延読み込み）
    """
    # 遅延 import（循環回避）
    from core import game_state as _gs
    from core.config import HEIGHT, FOV as _FOV

    px = _gs.player_x if player_x is None else player_x
    py = _gs.player_y if player_y is None else player_y
    pang = _gs.player_angle if player_angle is None else player_angle
    fov_rad = math.radians(_FOV if fov_deg is None else fov_deg)

    proj = _project_tile_to_screen(tx, ty, px, py, pang, fov_rad=fov_rad)
    if proj is None:
        return
    ray_idx, dist, sx = proj

    # 壁に隠れていないか？（少し手前補正 eps を持たせる）
    eps = 4.0
    if ray_idx < 0 or ray_idx >= len(zbuffer):
        return
    if dist > (zbuffer[ray_idx] - eps):
        return  # 壁の“向こう側”なので表示しない

    # 画面Yの決定：中央基準から上に少し浮かせる
    sy = int(HEIGHT * (0.5 - overlap_frac))

    # 深度でソートしたいのでキューへ積む
    # depth（小さい=近い）で並べたいが、重なり順は“遠い→近い”に描くので符号反転で持つ
    _WORLD_TOASTS.append((dist, sx, sy, text))

def flush_world_toasts(screen) -> None:
    """
    今フレームに積まれたワールドトーストを一括描画。
    遠い順に先描き→近い順を後描きにして視認性を高める。
    """
    from core.ui import blit_pill_label_midtop  # 既存描画ユーティリティを活用
    # 遠い順でソート
    _WORLD_TOASTS.sort(key=lambda e: e[0], reverse=True)
    for _, sx, sy, text in _WORLD_TOASTS:
        blit_pill_label_midtop(screen, text, sx, sy)

