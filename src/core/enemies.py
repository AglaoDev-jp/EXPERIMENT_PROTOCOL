# core/enemies.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple, Callable
import math
import pygame

Vec2 = Tuple[float, float]
Grid = Tuple[int, int]

@dataclass
class Chaser:
    """地下通路向けのシンプル追跡者（最小実装）
    - プレイヤー方向の単位ベクトルに沿って等速移動
    - 次位置が「壁なら止まる」: is_block_px(nx, ny) を外から受け取る
    """
    # 初期化パラメータ
    spawn_px: Vec2
    speed: float = 2.2             # 1フレーム当たりの移動px（60fps基準）
    capture_radius_px: float = 28  # 捕獲判定のしきい値

    # ランタイム
    pos_px: Vec2 = field(init=False)

    def __post_init__(self) -> None:
        self.pos_px = self.spawn_px

    def reset(self) -> None:
        """捕獲後など初期状態へ"""
        self.pos_px = self.spawn_px

    def update(self,
               player_px: Vec2,
               is_block_px: Callable[[float, float], bool]) -> bool:
        """1フレーム更新。捕獲したら True を返す。"""
        dx = player_px[0] - self.pos_px[0]
        dy = player_px[1] - self.pos_px[1]
        dist = math.hypot(dx, dy)

        # 捕獲チェック
        if dist <= self.capture_radius_px:
            return True

        # 単位ベクトルで“まっすぐ”接近（壁ならそのフレームは停止）
        if dist > 1e-6:
            ux, uy = dx / dist, dy / dist
            nx = self.pos_px[0] + ux * self.speed
            ny = self.pos_px[1] + uy * self.speed
            if not is_block_px(nx, ny):
                self.pos_px = (nx, ny)

        return False

    def draw_debug_2d(self, screen: pygame.Surface, camera_offset: Vec2) -> None:
        """開発用の簡易2D表示（本番は既存のスプライト描画に統合OK）"""
        x = int(self.pos_px[0] - camera_offset[0])
        y = int(self.pos_px[1] - camera_offset[1])
        pygame.draw.circle(screen, (200, 40, 40), (x, y), 12)
