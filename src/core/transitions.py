# core/transitions.py
# -*- coding: utf-8 -*-
"""
transitions.py
----------------------------
画面遷移時のエフェクトを管理するモジュール。

主な機能:
- fade_in(screen, duration_ms=600, draw_under=None)
    指定した時間をかけて画面を明るくしていく。
    draw_under: フェード中に毎フレーム背景を再描画したい場合に渡す関数。

- fade_out(screen, duration_ms=600, draw_under=None)
    指定した時間をかけて画面を暗くしていく。
    draw_under: フェード中に毎フレーム背景を再描画したい場合に渡す関数。

※ 厳密には「Surfaceを黒く塗って透明度を上げ下げしている」感じ

使い方の例（タイトルシーン）:
--------------------------------------------
    from core.transitions import fade_out

    def draw_current_frame():
        screen.fill((0, 0, 0))
        draw_title()
        draw_menu()

    # 600ms でフェードアウト
    fade_out(screen, duration_ms=600, draw_under=draw_current_frame)

備考:
--------------------------------------------
- Pygame の Surface と時間制御 (pygame.time.get_ticks) を使用。
- 「draw_under」は None の場合、前のフレームを保持したまま上に黒幕を重ねる。
- フレームレートは固定されないため、フレーム間隔が不均一でも自然に暗転。
- フェード中はイベント処理を行わない想定。
"""

from __future__ import annotations
import pygame
from typing import Callable

def fade_in(screen: pygame.Surface, duration_ms: int = 600,
            draw_under: Callable[[], None] | None = None, **kwargs):
    """黒→シーン表示。draw_under で“下地の描画関数”を渡すと都度再描画される。"""
    # --- 互換: fade_in(screen, ms=...) を許容 ---
    if 'ms' in kwargs:
        try:
            duration_ms = int(kwargs['ms'])
        except Exception:
            pass

    clock = pygame.time.Clock()
    w, h = screen.get_size()
    veil = pygame.Surface((w, h))
    veil = veil.convert()
    start = pygame.time.get_ticks()
    while True:
        now = pygame.time.get_ticks()
        t = now - start
        if draw_under:
            draw_under()
        alpha = max(0, min(255, 255 - int(255 * (t / max(1, duration_ms)))))
        veil.set_alpha(alpha)
        veil.fill((0, 0, 0))
        screen.blit(veil, (0, 0))
        pygame.display.flip()
        clock.tick(60)

        if t >= duration_ms:
            break

def fade_out(screen: pygame.Surface, duration_ms: int = 600,
             draw_under: Callable[[], None] | None = None, **kwargs):
    """シーン表示→黒。draw_under を渡すと都度再描画される。"""
    # --- 互換: fade_out(screen, ms=...) を許容 ---
    if 'ms' in kwargs:
        try:
            duration_ms = int(kwargs['ms'])
        except Exception:
            pass

    clock = pygame.time.Clock()
    w, h = screen.get_size()
    veil = pygame.Surface((w, h))
    veil = veil.convert()
    start = pygame.time.get_ticks()
    while True:
        now = pygame.time.get_ticks()
        t = now - start
        if draw_under:
            draw_under()
        alpha = max(0, min(255, int(255 * (t / max(1, duration_ms)))))
        veil.set_alpha(alpha)
        veil.fill((0, 0, 0))
        screen.blit(veil, (0, 0))
        pygame.display.flip()
        clock.tick(60)
        if t >= duration_ms:
            break
