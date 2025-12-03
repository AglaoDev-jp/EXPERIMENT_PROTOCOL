# scenes/video_event.py
# -*- coding: utf-8 -*-
"""
“ムービー →（戻り値で）次へ” の薄いラッパー。
SceneManager から呼べるように .run(screen) を持つ。
"""

from __future__ import annotations  # ← ★ ここ！ 他のimportより前（encodingとdocstringの直後）

from pathlib import Path
import pygame
from core.video_player import play_video

class VideoEvent:
    def __init__(self, base_dir: Path, video_path: str,
                 audio_path: str | None = None, allow_skip: bool = True,
                 sound_manager=None, se_cues: list[tuple[float, str]] | None = None):
        """
        base_dir    : プロジェクトのルート（Path）
        video_path  : 動画の“相対パス”（例: "assets/movies/foo.mp4"）
        audio_path  : 外部音声を別ファイルで流したい場合だけ指定（通常NoneでOK）
        allow_skip  : ユーザがスキップ可能か
        """
        self.base_dir = base_dir
        self.video_path = video_path
        self.audio_path = audio_path
        self.allow_skip = allow_skip
        # ムービー音声を SoundManager の voice_volume に連動させるため保持
        self.sound_manager = sound_manager
        self.se_cues = se_cues

    def run(self, screen: pygame.Surface) -> dict[str, bool]:
        """
        ムービーを“ブロッキング”再生します。
        戻り値: {"played_to_end": True/False}
          True  = 最後まで再生
          False = 途中でスキップ
        """
        played_to_end = play_video(
            screen,
            base_dir=self.base_dir,
            video_rel_path=self.video_path,   # 相対パスでOK（base_dirから解決）
            audio_rel_path=self.audio_path,
            allow_skip=self.allow_skip,
            fade_ms=600,
            sound_manager=self.sound_manager, # ムービー音声を voice_channel で再生するため渡す
            se_cues=self.se_cues, # ムービー用の効果音
        )
        return {"played_to_end": played_to_end}

