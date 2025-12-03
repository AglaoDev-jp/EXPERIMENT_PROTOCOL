# scenes/startup.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
import pygame

from scenes.video_event import VideoEvent
from scenes.intro_event import IntroEventScene
from scenes.title_scene import TitleScene  # （タイトル画面）
from scenes.menu import MenuScene          # （ロード専用で使う）
from scenes.scene_manager import run_scene, make_dialogue_controller  

from core.sound_manager import SoundManager

def _run_menu_as_modal_load(screen: pygame.Surface, base_dir: Path, sound_manager=None) -> bool:
    """
    ロード専用メニューをモーダル表示。
    戻り値 True: ロード成功 → タイトルの後続（ムービー/イントロ）はスキップしたい
    戻り値 False: キャンセル/失敗 → いつも通りムービー/イントロへ
    """
    menu = MenuScene(sound_manager=sound_manager)
    menu.state = "saveload"
    menu.saveload_mode = "load"
    menu.modal_load_only = True # タイトル専用ロード画面（疑似 run）でフラグをON

    clock = pygame.time.Clock()
    WIDTH, HEIGHT = screen.get_width(), screen.get_height()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            res = menu.handle_event(event)
            if isinstance(res, str) and res == "close":
                # True=読込成功 / False=Escキャンセル
                # ★ Escで閉じた“だけ”の時は、ここで menu_close を鳴らす（ロード成功時は鳴らさない）
                if not menu.did_load_success and sound_manager and sound_manager.has_se("menu_close"):
                    sound_manager.play_se("menu_close")
                return menu.did_load_success

        screen.fill((0, 0, 0))
        menu.draw(screen, WIDTH, HEIGHT)
        pygame.display.flip()
        clock.tick(60)

def run_startup_sequence(screen, base_dir: Path, sound_manager=None):
    while True:
        # 0) タイトル
        # ★重要：TitleScene へ sound_manager を確実に注入
        #  - ここで渡し忘れると SE が鳴らない（cursor/select）
        title = TitleScene(base_dir=base_dir, sound_manager=sound_manager)
        choice = run_scene(title, screen)   # "start"/"load"/"quit" を受け取る 

        if choice == "quit":
            return "quit" # ゲーム終了 →上流へ タイトルで×

        if choice == "load":
            loaded = _run_menu_as_modal_load(screen, base_dir, sound_manager=sound_manager)  # Esc なら False, 読込成功なら True 
            if loaded == "quit":
                return "quit"                  # 上流へ→ ロード画面で×
            if loaded is True:
                return "loaded"                # 読込成功：即本編へ（ムービー/イントロ省略）
            continue                           # Esc 等でキャンセル→タイトルへ戻す

        # choice == "start" のときだけ、ここへ到達（ムービー→イントロへ）
        movie = VideoEvent(
            base_dir=base_dir,
            video_path="assets/movies/forest_intro.mp4",
            audio_path="assets/sounds/bgm/恐怖.mp3.enc", # 音楽は拡張子あってもなくてもOKになるようにしてます。
            allow_skip=True,
            sound_manager=sound_manager,  # ← 連動の要
        )
        run_scene(movie, screen)

        ctrl = make_dialogue_controller()
        intro = IntroEventScene(
            base_dir=base_dir,
            dialogue_ctrl=ctrl,
            sound_manager=sound_manager,  # intro_event にも SoundManager を注入する。これ大事。
        )
        run_scene(intro, screen)
        return  # 本編へ

def run_newgame_sequence_without_title(screen, base_dir: Path, sound_manager=None):
    """
    タイトル画面を再表示せずに、「スタート後のムービー→イントロ」だけを実行するヘルパー。

    エンディング後に一度タイトルへ戻り、そこで「Start」を選んだ場合に、
    もう一度タイトルを挟まずに本編を始めたいときに使用します。
    """
    # run_startup_sequence() の「choice == 'start'」ブロックと同じ処理。
    movie = VideoEvent(
        base_dir=base_dir,
        video_path="assets/movies/forest_intro.mp4",
        audio_path="assets/sounds/bgm/恐怖.mp3.enc",  # 拡張子あり/なし両対応の想定
        allow_skip=True,
        sound_manager=sound_manager,
    )
    run_scene(movie, screen)

    ctrl = make_dialogue_controller()
    intro = IntroEventScene(
        base_dir=base_dir,
        dialogue_ctrl=ctrl,
        sound_manager=sound_manager,
    )
    run_scene(intro, screen)


