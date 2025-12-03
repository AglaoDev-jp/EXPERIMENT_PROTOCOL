# scenes/scene_manager.py
# -*- coding: utf-8 -*-
"""
“シーン実行ヘルパー”。
scene.run(screen) を呼ぶだけだが、
将来ここで一時停止/スキップ/ログ/例外処理などを共通化する予定。
"""
from core.dialogue_flow import DialogueConfig, DialogueController
from core.dialogue_flow import KEY_AUTO_TOGGLE, KEY_SKIP_TOGGLE, KEY_FAST_HELD

def make_dialogue_controller() -> DialogueController:
    """
    共通コントローラを作成して“渡す”
    """
    cfg = DialogueConfig(
        type_ms_per_char=22,
        auto_enabled_default=False,
        auto_line_delay_ms=700,
        auto_page_delay_ms=900,
        fast_multiplier=0.33,
    )
    return DialogueController(cfg)

import pygame

def run_scene(scene, screen: pygame.Surface):
    """
    ・各シーンは .run(screen) を持つ想定（ブロッキングでOK）
    ・戻れば次の処理へ進む
    """
    return scene.run(screen)
