# core/player.py
# -*- coding: utf-8 -*-
"""
プレイヤー移動と衝突判定（最小スコープ）のユーティリティ。
"""
from __future__ import annotations
from typing import Callable, Tuple, Optional
import math
import pygame


IsWallFn = Callable[[float, float], bool]

def handle_movement(
    *,
    keys,                        # pygame.key.get_pressed() の戻り
    state,                       # game_state モジュール（player_x / player_y / player_angle / player_speed を持つ）
    is_wall: IsWallFn,          # 壁判定コールバック（main.py から渡す）
    tile_size: int,              # TILE（タイルのピクセルサイズ）
) -> tuple[bool, Optional[Tuple[int, int]]]:
    """
    プレイヤーを移動させ、タイル座標を返す。
    - state: game_state モジュール（player_x / player_y / player_angle / player_speed を持つ）
    - keys: pygame.key.get_pressed() の結果
    - is_wall: (x, y) が壁かどうかを判定するコールバック
    """
    # ★ カットシーン中/イベント抑止中は移動も足音も発火させない
    #   - ムービー再生:  game_state.is_cutscene = True（cinematics.py）
    #   - ドクターイベント: game_state.suppress_footsteps = True（doctor_event.py）
    if getattr(state, "is_cutscene", False) or getattr(state, "suppress_footsteps", False):
        return False, None

    move_x = 0.0
    move_y = 0.0

    # ↑↓キーで前後移動
    if keys[pygame.K_UP]: # 前進
        move_x += state.player_speed * math.cos(state.player_angle)
        move_y += state.player_speed * math.sin(state.player_angle)
    if keys[pygame.K_DOWN]: # 後退
        move_x -= state.player_speed * math.cos(state.player_angle)
        move_y -= state.player_speed * math.sin(state.player_angle)

    moved = False

    # --- X軸移動（“実際に位置が変わったら” moved=True）---
    # 0移動でも is_wall は False になり得るため、差分があるかを必ず確認する
    next_x = state.player_x + move_x
    if abs(move_x) > 1e-6:  # ← ほぼ0は無視（浮動小数の揺れ対策）
        if not is_wall(next_x, state.player_y):
            if abs(next_x - state.player_x) > 1e-6:
                state.player_x = next_x
                moved = True

    # --- Y軸移動（こちらも同様に厳密チェック）---
    next_y = state.player_y + move_y
    if abs(move_y) > 1e-6:
        if not is_wall(state.player_x, next_y):
            if abs(next_y - state.player_y) > 1e-6:
                state.player_y = next_y
                moved = True

    # 移動がなければタイル計算は省略
    if not moved:
        return False, None

    # 現在タイル座標を返す（呼び出し側で last_tile と比較してトリガー発火に使うかも）
    px = int(state.player_x // tile_size)
    py = int(state.player_y // tile_size)
    return True, (px, py)

def handle_rotation(
    *,
    keys,                 # pygame.key.get_pressed() の戻り
    state,                # game_state モジュール（player_angle を持つ）
    rot_per_tick: float = 0.04,
    key_left: int = pygame.K_LEFT,
    key_right: int = pygame.K_RIGHT,
) -> bool:
    """
    ←→キーで視点回転を処理する。
    - 回転が発生したら True を返す
    - 角度は [0, 2π) に正規化する
    - キーカスタマイズ可能（将来パッド/マウス対応に拡張しやすいらしい？）
    """
    rotated = False

    # --- 左右回転 ---------------------------------------------------------
    if keys[key_left]:
        state.player_angle -= rot_per_tick
        rotated = True
    if keys[key_right]:
        state.player_angle += rot_per_tick
        rotated = True

    # --- 角度の正規化 -----------------------------------------------------
    if rotated:
        # Python 3.8+ で OK: マイナスでも正の範囲に丸めてくれる
        state.player_angle %= (2.0 * math.pi)

    return rotated
