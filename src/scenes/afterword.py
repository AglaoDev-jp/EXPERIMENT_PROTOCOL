# scenes/afterword.py
# -*- coding: utf-8 -*-
"""
ゲームクリア後に読む「あとがき」イベントシーン。

- UI/挙動は IntroEventScene と同一
  （タイプライター / AUTO / SKIP / FAST / Enterヒント / バッジ表示など）
- スクリプト形式も IntroEventScene / DoctorEventScene と同じ
  「ページのリスト → 行(dict) のリスト」構造。

このファイルでは：
- AFTERWORD_SCRIPT: あとがき本文（JSON的なリスト構造）
- AfterwordScene  : IntroEventScene のサブクラス（UI共通）
- run_afterword() : 既存シーンと同じ感覚で呼べるラッパ（将来用）

を提供します。
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional

import pygame

# ✅ 既存の“共通イベントUI”をそのまま再利用しています。
#    - タイプライター / AUTO / SKIP / FAST（Ctrl）/ Enterヒント / バッジ表示 など
from scenes.intro_event import IntroEventScene   # 共通UI本体
from scenes.scene_manager import make_dialogue_controller, run_scene


# ------------------------------------------------------------
# あとがき用スクリプト（Intro/Doctor と同じ JSON 風構造）書き方
#   - List[Page]        : AFTERWORD_SCRIPT
#   - Page              : List[Line]
#   - Line (dict 例)   :
#       {
#           "text": "テキスト本文",
#           "voice": "voice_afterword_001.mp3.enc",   # 任意
#           "bgm": "afterword_bgm.mp3.enc",           # 任意
#           "bgm_stop": True, "bgm_fade_ms": 800,     # 任意
#           "se": "switch_ok",                        # 任意（SoundManager の SEキー）
#           "bg": "assets/sprites/afterword_bg.png",  # 任意（背景差し替え）
#           "bg_color": [0, 0, 0],                    # 任意（画面を単色で塗りつぶし）
#       }
#
#   - 文字列だけの行もOK：
#       "遊んでいただき、ありがとうございました。"
#
#   - ページを増やしたいときは、AFTERWORD_SCRIPT に Page を追加してください。
# ------------------------------------------------------------
AFTERWORD_SCRIPT: List[List[Dict[str, Any] | str]] = [

    [
        {
            "text": "◆ あとがき ◆",
            "bgm": "私の部屋.mp3.enc",
            "bg": "assets/sprites/afterword.png",
        },
        {
            "text": "はじめまして。作者の AglaoDev-jp です。",
        },
        {
            "text": "拙作を最後まで観ていただいて、ありがとうございました。",
        },
    ],
    [
        {
            "text": "Pythonと聞くと、",
        },
        {
            "text": "「処理が重い」",

        },
        {
            "text": "「ゲーム制作には向かない」",
        },
        {
            "text": "というイメージを持たれがちかもしれません。",
        },
    ],
    [
        {
            "text": "Pygameも、一般的には",
        },
        {
            "text": "“2D向けのGUIライブラリ”",

        },
        {
            "text": "という印象が強いと思います。",
        },
    ],    
    [
        {
            "text": "私もそんな印象があるものですから",
        },        
        {
            "text": "3Dのゲーム作ってみたいけど無理かな？と思いつつ",
        },
        {
            "text": "本格的な3Dは無理でも、疑似3Dならできるかも？",

        },
        {
            "text": "などと思い ChatGPT に相談しました。",
        },
    ],    
    [
        {
            "text": "その時、紹介されたのが",

        },        
        {
            "text": "”レイキャスティングとフロアキャスティング”",
        },
        {
            "text": "の技法でした。",

        },
    ],    
    [
        {
            "text": "ということで、このゲームは",
        },
        {
            "text": "3Dライブラリを一切使わず、",

        },
        {
            "text": "**Pythonだけで疑似3Dを描画するアドベンチャーゲーム**",
        },
        {
            "text": "という、ある意味とてもロマンのある構成なんですよ。",
        },
    ],    
    [
        {
            "text": "ただ、なんか重くなっちゃって",
        },
        {
            "text": "結局、高速化のために NumPy の力をお借りしています。",

        },
        {
            "text": "……ライブラリって、素晴らしいですね！",
        },

    ],    
    [
        {
            "text": "最近はAIで3Dアセットを自動生成できたり、",
        },
        {
            "text": "3Dワールドを一瞬で構築できたりと、",

        },
        {
            "text": "そんなサービスも登場しているようです。",
        },

    ],    
    [
        {
            "text": "私の努力が泡沫に消えた感がありますが、",
        },
        {
            "text": "まあ、人生ってそんなもんっすよね。",

        },
        {
            "text": "悲しいです。",
        },
    ],
    [
        {
            "text": "今回もコードなどGitHubにて公開しています。",
        },
        {
            "text": "素材やライセンス情報、"
        },
        {
            "text": "READMEを含む詳細な説明もすべてGitHubに掲載しています。",
        },
        {
            "text": "何かのお役に立てれば幸いです。",
        },
    ],
    [
        {
            "text": "また何か作るかもしれませんので、"
        },
        {
            "text": "そのときはどうぞよろしくお願いします。",
        },
        {
            "text": "それでは、またいつか。",

            "bgm_stop": True, "bgm_fade_ms": 800,
        },
    ],
]


# ------------------------------------------------------------
# 状態初期化ヘルパー（再読用）
# ------------------------------------------------------------
def init_state():
    """
    あとがき用の状態を初期化して返す関数。

    - text_index : 現在のページ番号（将来的な拡張用）
    - in_dialog  : ダイアログ中フラグ（IntroEventScene との整合用の名残）
    - bg_images  : 背景画像キャッシュなど（今回は未使用）
    """
    return {
        "text_index": 0,
        "in_dialog": True,
        "bg_images": None,
    }


# 初期状態（main から import 時にも使えるようにモジュール変数として保持）
state = init_state()


# ------------------------------------------------------------
# AfterwordScene 本体（UI は IntroEventScene に丸投げ）
# ------------------------------------------------------------
class AfterwordScene(IntroEventScene):
    """
    ゲームクリア後に読む「あとがき」用イベント。

    - IntroEventScene を継承することで、
      タイプライター / AUTO / SKIP / FAST / Enterヒント / バッジ表示 など
      既存イベントとまったく同じ UI/操作性になります。

    - ページ内容は AFTERWORD_SCRIPT を参照します。
    """

    def __init__(
        self,
        base_dir: Path,
        *,
        dialogue_ctrl=None,
        sound_manager=None,
        bg_path: Optional[str] = None,
        pages: Optional[List[List[Dict[str, Any] | str]]] = None,
    ):
        """
        パラメータ:
        - base_dir       : ゲームのベースディレクトリ
        - dialogue_ctrl  : 既存共通の DialogueController（省略可）
                           省略時は make_dialogue_controller() で生成します。
        - sound_manager  : SoundManager のインスタンス（BGM/SE/VOICE 連携用）
        - bg_path        : デフォルト背景画像パス（未指定ならイントロと同じもの）
        - pages          : デフォルト以外のスクリプトを使いたいときに差し替え可
        """
        # 共通の会話コントローラを使う（doctor_event.py と同じ思想で）
        if dialogue_ctrl is None:
            dialogue_ctrl = make_dialogue_controller()

        #  bg_path が指定されていない場合は、あとがき用」の背景にしておく
        if bg_path is None:
            bg_path = "assets/sprites/afterword.png"

        # 親クラス側で背景などを初期化
        super().__init__(
            base_dir=base_dir,
            bg_path=bg_path,
            dialogue_ctrl=dialogue_ctrl,
            sound_manager=sound_manager,
        )

        # あとがき用スクリプトに差し替え
        self.pages = pages or AFTERWORD_SCRIPT

        # Escなどスキップ用フラグ（サイレントモードなど親クラスの仕様に合わせておく）
        self._skip_all_silent = False

        # モジュールグローバル state を参照して、将来的な再読・途中再開も可能にしておく（現状は 0 に戻すだけ）
        self.page_idx = state.get("text_index", 0)

    def run(self, screen: pygame.Surface):
        """
        IntroEventScene.run() をオーバーライドしつつ、
        終了時に state を初期化しておく（再読のため常に先頭からに戻したい場合）。
        """
        # 通常のイントロイベントと同じループ・描画を実行
        super().run(screen)

        # 終了後：再読時は 1 ページ目から始めたいので state をリセット
        global state
        state = init_state()

# ------------------------------------------------------------
# 既存呼び出しスタイルに合わせたラッパ（任意で使用）
#   - main.py からは直接 AfterwordScene(...) を new して
#     run_scene(scene, screen) してもOK。
#   - もし doctor_event.py と同じ感覚で使いたい場合は、
#     この run_afterword() を経由してください。
# ------------------------------------------------------------
def run_afterword(
    screen: pygame.Surface,
    base_dir: Path,
    *,
    sound_manager=None,
) -> Dict[str, bool]:
    """
    あとがきシーンを実行するラッパ関数。

    戻り値:
        {"played_to_end": bool}
        - True  : 最後まで読了
        - False : Esc スキップなどで途中終了
    """
    ctrl = make_dialogue_controller()
    scene = AfterwordScene(
        base_dir=base_dir,
        dialogue_ctrl=ctrl,
        sound_manager=sound_manager,
    )
    run_scene(scene, screen)

    # IntroEventScene の内部状態から「スキップで終わったかどうか」を判定
    played_to_end = not getattr(getattr(scene, "ctrl", None), "st", object()).__dict__.get("is_skip", False)
    return {"played_to_end": bool(played_to_end)}
