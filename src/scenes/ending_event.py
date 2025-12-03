# ending_event.py
# -*- coding: utf-8 -*-
"""
エンディング・シーケンス
- 構成: ムービー1 → シナリオ1 → ムービー2 → シナリオ2 → エンドロール（仮）
- 目的: 差し替えや順序変更が簡単（配列の入れ替えだけ）で、intro_event.py の入力系を踏襲
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Protocol, Union, Dict, Any

import pygame

# 既存の薄いラッパ群を活用
from scenes.video_event import VideoEvent  # ムービー用（.run(screen)でブロッキング再生）
from scenes.scene_manager import run_scene, make_dialogue_controller  # 実行ヘルパーと共通コントローラ生成

# シナリオ表示は intro_event の実装を“使い回す”
from scenes.intro_event import IntroEventScene  # .run(screen)で: 行送り/ページ送り/タイプ音/AUTO/SKIP対応（BGM/SE/VOICE 行頭副作用つき）
from scenes.end_roll import EndRollEvent
from scenes.scene_manager import run_scene, make_dialogue_controller
# ------------------------------------------------------------
# セグメント定義（順番を差し替えやすいようにデータ化）
# ------------------------------------------------------------

class RunnableScene(Protocol):
    def run(self, screen: pygame.Surface):
        ...

@dataclass
class MovieSegment:
    """ムービーを再生するセグメント（VideoEvent を内部で生成）"""
    video_path: str                    # 例: "assets/movies/ending01.mp4"
    audio_path: Optional[str] = None   # 通常 None
    allow_skip: bool = True

    def build(self, base_dir: Path) -> RunnableScene:
        """
        VideoEvent を生成する前に、動画/音声パスの存在を軽く検証
        - 動画が見つからない場合は候補名も併記して FileNotFoundError を投げる。
        - 音声は無ければ無しで続行（動画のみ再生）。
        """
        # --- 動画存在チェック（原因の早期発見用）---
        vpath = (base_dir / self.video_path)
        if not vpath.exists():
            # よくある命名ゆれの候補を提示（ending_03.mp4 / ending03.mp4 / ending_3.mp4 など）
            candidates = []
            try_name = self.video_path.replace("ending_03", "ending03")
            if try_name != self.video_path:
                candidates.append(str(base_dir / try_name))
            try_name2 = self.video_path.replace("ending_03", "ending_3")
            if try_name2 != self.video_path and try_name2 != try_name:
                candidates.append(str(base_dir / try_name2))
            msg = (
                f"[ENDING][ERROR] 動画が見つかりません: {vpath}\n"
                f"  - パスやファイル名（アンダースコア/ゼロ埋め）をご確認ください。\n"
                + ("  - 代替候補: \n    - " + "\n    - ".join(candidates) if candidates else "")
            )
            raise FileNotFoundError(msg)

        # --- 音声存在チェック（無ければスルーでOK）---
        # --- 音声パス解決（.enc 優先 → 平文 → 無ければ None）---
        apath_str: Optional[str] = None
        if self.audio_path:
            ap_rel = Path(self.audio_path)
            # 例: foo.mp3 → foo.mp3.enc を優先チェック
            penc = ap_rel.with_suffix(ap_rel.suffix + ".enc")
            if (base_dir / penc).exists():
                apath_str = penc.as_posix()
            elif (base_dir / ap_rel).exists():
                apath_str = ap_rel.as_posix()
            else:
                print(f"[ENDING][WARN] 音声が見つかりません（動画のみ再生）: {(base_dir / ap_rel)} / {(base_dir / penc)}")

        # VideoEvent は run(screen) を持ち、{"played_to_end": bool} を返す
        # - 既存の VideoEvent 実装に準拠（audio_path は None でもOK）
        return VideoEvent(base_dir, self.video_path, apath_str, self.allow_skip)

@dataclass
class ScriptSegment:
    """
    テキストシナリオを流すセグメント。
    - intro_event.IntroEventScene を内部で使い回し、
      生成後に .pages を差し替えて任意のシナリオを表示できるようにする。
    """
    # ★ dict 行も許容：各行で BGM/SE/VOICE/BG を指示可能（intro_event と同仕様）
    pages: List[List[Union[str, Dict[str, Any]]]]
    bg_path: Optional[str] = None                 # 任意の背景。未指定なら intro_event のデフォルト
    share_dialogue_controller: bool = True        # 入力/AUTO/SKIP状態をシーン間で共有する場合は True
    sound_manager: Optional[object] = None        # IntroEventScene に渡して行頭副作用（BGM/SE/VOICE）を有効化

    def build(self, base_dir: Path, shared_ctrl=None) -> RunnableScene:
        # 1) コントローラを用意（共有したい時は外部から受け取る）
        ctrl = shared_ctrl if (self.share_dialogue_controller and shared_ctrl) else make_dialogue_controller()

        # ------------------------------------------------------------
        # ★ 共有している DialogueController の“残りカス状態”をクリアする
        #   - オート ON/OFF（st.is_auto）
        #   - それ以外の「一時的な状態」は次のセグメントには持ち越さない
        #     ・is_skip          : スキップモード
        #     ・fast_held        : Ctrl での高速押しっぱなし状態
        #     ・auto_wait_until_ms: 前セグメントのオート待ち予約
        #     ・next_tick_ms     : 次の 1 文字を打つ時刻
        # ------------------------------------------------------------
        st = getattr(ctrl, "st", None)
        if st is not None:
            # スキップ関連は一度リセットしておく
            st.is_skip = False
            st.fast_held = False
            st.auto_wait_until_ms = 0
            try:
                # すぐに 1 文字目からタイプを開始できるように現在時刻をセット
                st.next_tick_ms = pygame.time.get_ticks()
            except Exception:
                st.next_tick_ms = 0

        # 2) IntroEventScene を生成（bg 差し替え可能）
        #    sound_manager を渡すことで、各行 dict の "bgm"/"se"/"voice" が有効になる
        scene = IntroEventScene(
            base_dir,
            bg_path=self.bg_path,
            dialogue_ctrl=ctrl,
            sound_manager=self.sound_manager,
        )

        # 3) 既存実装の .pages を差し替えることで、外部スクリプトを適用
        #    - IntroEventScene は .pages / page_idx / line_idx / char_idx を内部で管理
        #    - 差し替え時はインデックスも初期化しておく
        scene.pages = self.pages
        scene.page_idx = 0
        scene.line_idx = 0
        scene.char_idx = 0
        scene.finished = False

        # 念のため、行頭副作用まわりのフラグも初期化しておく
        # （前セグメントから残っていると 1 行目の BGM/SE/VOICE/BG が飛ぶ可能性があるため）
        if hasattr(scene, "_line_side_effect_applied"):
            scene._line_side_effect_applied = False
        if hasattr(scene, "_skip_all_silent"):
            scene._skip_all_silent = False

        return scene

@dataclass
class EndRollSegment:
    """本番エンドロール：黒背景スクロール＋点滅促し"""
    credits: List[str]
    bgm_path: Optional[str] = None
    bgm_volume: float = 0.6
    bgm_fade_ms: int = 1200
    speed_px_per_sec: float = 80.0
    line_px: int = 28
    line_gap: int = 10
    prompt_text: str = "何かキーを押すとタイトルへ"
    prompt_px: int = 22

    def build(self, base_dir: Path) -> RunnableScene:
        # --- BGM パス解決（.enc 優先 / 無ければ無し）---
        resolved_bgm: Optional[str] = None
        if self.bgm_path:
            bp = Path(self.bgm_path)
            penc = bp.with_suffix(bp.suffix + ".enc")
            if (base_dir / penc).exists():
                resolved_bgm = penc.as_posix()
            elif (base_dir / bp).exists():
                resolved_bgm = bp.as_posix()
            else:
                print(f"[ENDING][WARN] EndRoll BGM が見つかりません（無音で続行）: {(base_dir / bp)} / {(base_dir / penc)}")

        return EndRollEvent(
            credits=self.credits,
            bgm_path=resolved_bgm,         # EndRollEvent は bgm_path=None で無音進行
            bgm_volume=self.bgm_volume,
            bgm_fade_ms=self.bgm_fade_ms,
            speed_px_per_sec=self.speed_px_per_sec,
            line_px=self.line_px,
            line_gap=self.line_gap,
            prompt_text=self.prompt_text,
            prompt_px=self.prompt_px,
        )

def _resolve_audio(base_dir: Path, rel_path: Optional[str]) -> Optional[str]:
    """
    与えられた相対パスに対して、以下の優先順で存在チェックを行い、
    見つかったものだけを返す（なければ None を返す＝無音で続行）:
      1) <rel_path>.enc   （暗号化ファイル優先）
      2) <rel_path>       （平文）
    rel_path が None/空 のときも None を返す。
    """
    if not rel_path:
        return None
    p = base_dir / rel_path
    penc = p.with_suffix(p.suffix + ".enc")  # 例: .mp3 → .mp3.enc
    if penc.exists():
        return str(penc.as_posix())
    if p.exists():
        return str(p.as_posix())
    return None

# ------------------------------------------------------------
# 実行エントリ（順番はここで並べるだけ。差し替え・追加が超簡単）
# ------------------------------------------------------------

def run_ending_sequence(screen: pygame.Surface, base_dir: Path, sound_manager: Optional[object] = None) -> None:
    """
    エンディング本体。
    - ムービーやシナリオの差し替えは、下の segments 配列を書き換えるだけ。
    - 1つの DialogueController を共有することで、AUTO/SKIP 状態を通しで維持可能。
    """
    # 共有コントローラ（シナリオセグメント間で共有）
    shared_ctrl = make_dialogue_controller()

    # ★ 例：dict 行で BGM/SE/VOICE/BG を指定可能（intro_event と同フォーマット）
    #    - 実運用ではここを実エンディング用スクリプトに差し替えてください
    scenario1_pages: List[List[Union[str, Dict[str, Any]]]] = [
        [
            {"text": "どうにか追跡者から逃げ延びることができた。", 
             "voice": "ending_001.mp3.enc", 
             "bg": "assets/sprites/ending_bg1.png"},
            {"text": "息がまだ落ち着かない。", "voice": "ending_002.mp3.enc"},
            {"text": "あれが博士が言っていた”生物兵器”というものなのだろうか。", "voice": "ending_003.mp3.enc"},
            {"text": "人の姿ではあったけど、理性なんて欠片もなかった。", "voice": "ending_004.mp3.enc"},
        ],
        [
            {"text": "暗く湿った地下道を抜けると、視界がふっと開けた。", 
             "voice": "ending_005.mp3.enc", 
             "bg": "assets/sprites/ending_bg2.png",
             "bgm": "風に揺れる草木1.mp3.enc"},
            {"text": "そこは大きな山道で、夜風がひやりと肌を撫でた。", "voice": "ending_006.mp3.enc"},
            {"text": "きれいな月の夜空。", 
             "voice": "ending_007.mp3.enc", 
             "bg": "assets/sprites/ending_bg3.png"},
            {"text": "さっきまでの息苦しい恐怖が、嘘みたいに思えた。", "voice": "ending_008.mp3.enc",
            "bgm_stop": True, "bgm_fade_ms": 600},
        ],
        [
            {"text": "森を抜ける手助けをしてくれた、あの白衣の男性――博士？", 
             "voice": "ending_009.mp3.enc", 
             "bg": "assets/sprites/lab_front_doctor_hurry_06.png"},
            {"text": "彼のおかげでここまで来ることができたのは確かだ。", "voice": "ending_010.mp3.enc"},
            {"text": "けれど、彼が口にした言葉は、まだ胸の奥でざわついている。", "voice": "ending_011.mp3.enc"},
        ],
        [
            {"text": "私は博士の助手で、一緒にその生物兵器の研究をしていた。", 
             "voice": "ending_012.mp3.enc", 
             "bg": "assets/sprites/ending_bg4.png"},
            {"text": "彼はそう言った。", "voice": "ending_013.mp3.enc"},
            {"text": "私の名前は“ユイ・ミナセ”で、研究施設にいたはずだ、と。", "voice": "ending_014.mp3.enc"},
        ],
        [
            {"text": "ただ……そのどれもが、まるで他人の話みたいだった。", "voice": "ending_015.mp3.enc"},
            {"text": "自分の名前すら、いまだ腑に落ちない。", "voice": "ending_016.mp3.enc"},
        ],
        [
            {"text": "それにしても……、", 
             "voice": "ending_017.mp3.enc", 
             "bg": "assets/sprites/ending_bg5.png"},
            {"text": "生物兵器の割に、走って逃げ切れる程度だなんて……。", 
             "voice": "ending_018.mp3.enc", 
             "bg": "assets/sprites/ending_bg6.png"},
            {"text": "大した事ないな。", "voice": "ending_019.mp3.enc"},
        ],
        [
            {"text": "……いや、軽く考えてはいけないのかもしれない。", 
             "voice": "ending_020.mp3.enc", 
             "bg": "assets/sprites/ending_bg7.png"},
            {"text": "今はもう、とにかく遠くへ離れたい。", "voice": "ending_021.mp3.enc"},
            {"text": "博士は合流するっていってたけど……、", "voice": "ending_022.mp3.enc"},
            {"text": "もう、このまま街まで出てしまおうか……。", "voice": "ending_023.mp3.enc"},
        ],                                                
    ]
    scenario2_pages: List[List[Union[str, Dict[str, Any]]]] = [
        [
            {"text": "博士と名乗った白衣の男は、建物の陰に身を潜めていた。", 
             "voice": "ending_024.mp3.enc", 
             "bg": "assets/sprites/ending_bg8.png"},
            {"text": "そこに数人の白衣の男女が駆け寄ってきた。", "voice": "ending_025.mp3.enc"},
            {"text": "皆息を荒げながらも、その目は怒りと焦燥に満ちている", "voice": "ending_026.mp3.enc"},
        ],
        [
            {"text": "「見つけたぞ！こんなところにいたのか！」", 
             "voice": "ending_027.mp3.enc", 
             "bg": "assets/sprites/ending_bg9.png"},
            {"text": "そのうちの一人が男の襟首をつかみ上げるようにして叫んだ。", "voice": "ending_028.mp3.enc"},
        ],
        [
            {"text": "別の研究員が続けざまに声を荒げる。", 
             "voice": "ending_029.mp3.enc", 
             "bg": "assets/sprites/ending_bg10.png"},
            {"text": "「お前、まさか――あの被験体を逃がしたのか!?", "voice": "ending_030.mp3.enc"},
            {"text": "　どうしてそんなことを……！」", "voice": "ending_031.mp3.enc"},
        ],
        [
            {"text": "男――博士は肩を震わせ、かすかに笑った。", 
             "voice": "ending_032.mp3.enc", 
             "bg": "assets/sprites/ending_bg11.png"},
            {"text": "「逃がした？", "voice": "ending_033.mp3.enc"},
            {"text": "　ふふ……あれは“解き放たれた”んだよ。」", "voice": "ending_034.mp3.enc"},
        ],
        [
            {"text": "「いったいどこへやった！」", 
             "voice": "ending_035.mp3.enc", 
             "bg": "assets/sprites/ending_bg12.png"},
            {"text": "研究員の怒号が夜気を震わせる。", "voice": "ending_036.mp3.enc"},
            {"text": "博士はその目を細め、口の端を吊り上げた。", "voice": "ending_037.mp3.enc"},
            {"text": "「……地下道を抜けて、街に向かっているだろうな。」", "voice": "ending_038.mp3.enc"},            
        ],
        [
            {"text": "その言葉に一人が青ざめる。", 
             "voice": "ending_039.mp3.enc"},
            {"text": "「しかし……あの地下通路で脱出は不可能だ！", 
             "voice": "ending_040.mp3.enc", 
             "bg": "assets/sprites/ending_bg6.png"},
            {"text": "あそこには“被験体13号”が幽閉されていたはずだぞ……！」", "voice": "ending_041.mp3.enc"},
        ],
        [
            {"text": "博士は唇を歪め、狂気を帯びた笑いを漏らした。", 
             "voice": "ending_042.mp3.enc", 
             "bg": "assets/sprites/ending_bg13.png"},
            {"text": "「ははっ！あんなポンコツに止められるものか！！", "voice": "ending_043.mp3.enc"},
            {"text": "　“ユイ・ミナセ”は私の最高傑作だ！", "voice": "ending_044.mp3.enc"},
            {"text": "　誰にも止められんぞ！」", "voice": "ending_045.mp3.enc"},
        ], 
        [
            {"text": "「くそっ……軍部に連絡だ！我々も追うぞ！」", 
             "voice": "ending_046.mp3.enc", 
             "bg": "assets/sprites/ending_bg14.png",
             "bgm": "アスファルトの上を走る2.mp3.enc"},
            {"text": "叫ぶと、研究員たちは慌ただしく走り去っていった。", "voice": "ending_047.mp3.enc",
            "bgm_stop": True, "bgm_fade_ms": 600},
            {"text": "残された博士は、まだ笑い続けていた。", "voice": "ending_048.mp3.enc"},
            {"text": "その笑い声は、夜の闇の中でいつまでも響いていた。", "voice": "ending_049.mp3.enc"},
        ],         
    ]

    # 並べ替え自在なセグメント配列
    segments: list[Union[MovieSegment, ScriptSegment, EndRollSegment]] = [
        # ▼各ムービーに音声（audio_path）を設定
        #   - .mp3 と .mp3.enc どちらでもOK（存在するほうを置いてください）
        # ムービー１
        MovieSegment(
            video_path="assets/movies/ending_01.mp4",
            audio_path="assets/sounds/bgm/土の上を走る.mp3", 
            allow_skip=True
        ),     
        # シナリオ１
        ScriptSegment(
            pages=scenario1_pages,
            bg_path="assets/sprites/ending_bg1.png",
            share_dialogue_controller=True,
            sound_manager=sound_manager,        
        ), 
        # ムービー２
        MovieSegment(
            video_path="assets/movies/ending_02.mp4",
            audio_path="assets/sounds/bgm/異次元空間.mp3",
            allow_skip=True
        ),     
        # シナリオ２
        ScriptSegment(
            pages=scenario2_pages,
            bg_path="assets/sprites/ending_bg8.png",
            share_dialogue_controller=True,
            sound_manager=sound_manager,        
        ), 
        # ムービー３
        MovieSegment(
            video_path="assets/movies/ending_03.mp4",
            audio_path="assets/sounds/bgm/恐怖.mp3",
            allow_skip=True
        ),     
        # エンドロール
        EndRollSegment(credits=[
            "",
            "", 
            "",
            "────────────────",                         
            "     EXPERIMENT PROTOCOL",
            "────────────────",
            "",  
            "",
            "",                       
            "Producer / Director",
            "  AglaoDev-jp, ChatGPT (AI)",
            "Programming",
            "  AglaoDev-jp, ChatGPT (AI)",
            "Art / Design",
            "  AglaoDev-jp, ChatGPT (AI)",
            "",
            "",
            "Music",
            "Free BGM from DOVA-SYNDROME",
            "Tracks Used:",
            "うしろからなにかが近づいてくる -  東雄アモ ",
            "Inside the Dying Room  -  松浦洋介",
            "私の部屋  -  Heitaro Ashibe",
            "",
            "",
            "Sound Effects",
            "効果音ラボ",
            "",
            "",            
            "Voice Creation",
            "  CoeFont（コエフォント）",
            "  Voiced by https://CoeFont.cloud",
            "  Standard Plan Used", 
            "", 
            "",                         
            "Voice Cast",
            "”ユイ・ミナセ” あかね大佐*",
            "”博士” Canel（CV: 森川智之）",
            "”ナレーションなど” さのすけ（中低音ボイス）",                              
            ""
            "",            
            "Movie scenes",
            "Sora / Sora 2 by OpenAI",
            "",
            "",            
            "Fonts",
            "Noto Sans JP",
            "© 2014–2025 Google LLC",
            "SIL Open Font License 1.1",
            "",
            "",
            "Programming Language",
            "Python 3.12.5",
            "© 2001 Python Software Foundation",
            "PSF License Version 2.",
            "",
            "",
            "External Libraries",
            "Pygame",
            "© 2000–2024 Pygame developers",
            "LGPL v2.1 License.",
            "",
            "NumPy",
            "© 2005–2025 NumPy Developers",
            "BSD 3-Clause License "
            "(NumPy License)",
            "",
            "OpenCV",
            "© 2000–2025 OpenCV Foundation",
            "Apache License 2.0",
            "",
            "",
            "Encryption",
            "  cryptography",
            "    Copyright (c) Individual contributors.",
            "    All rights reserved.",
            "",
            "  OpenSSL 3.4.0",
            "    © 1998–2025 The OpenSSL Project Authors",
            "    © 1995–1998 Eric A. Young / Tim J. Hudson",
            "    All rights reserved.",
            "",
            "",
            "Obfuscation",
            "  Cython",
            "    © 2007–2025 The Cython Project Developers",        
            "",
            "",            
            "Executable Build Tool",
            "PyInstaller",
            "© 2010–2023 PyInstaller Development Team",
            "© 2005–2009 Giovanni Bajo",
            "© 2002 McMillan Enterprises, Inc.",
            "",
            "",
            "Standard Modules",
            "os, pathlib, sys",
            "copy, math, json",
            "dataclasses, typing",
            "time, datetime",
            "traceback, io",
            "collections.deque, collections.abc",
            "",
            "",
            "Editor",
            "Visual Studio Code (VSC)",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "Thank you for playing!",
            "© 2025 AglaoDev-jp",            
            "── The Experiment continues ──",
        ],
            # ▼▼▼ BGM（暗号化可）ここに置くだけ ▼▼▼
            bgm_path="assets/sounds/bgm/Inside_the_Dying_Room.mp3",   # .mp3 でもOK
            bgm_volume=0.65,
            bgm_fade_ms=1200
        ),            
    ]

    # 実行（各セグメントは build() で run(screen) を持つシーンに変換してから共通ランナーに渡す）
    for seg in segments:
        # ★ カットシーン直前に足音や環境SEをミュート（念のため）
        if sound_manager is not None and hasattr(sound_manager, "hush_effects_for_cutscene"):
            try:
                sound_manager.hush_effects_for_cutscene(fade_ms=120)
            except Exception:
                pass

        if isinstance(seg, ScriptSegment):
            scene = seg.build(base_dir, shared_ctrl)  # シナリオは共有コントローラを渡す
        elif isinstance(seg, MovieSegment):
            scene = seg.build(base_dir)
        else:  # EndRollSegment
            scene = seg.build(base_dir)

        # run_scene は scene.run(screen) を呼ぶ薄いヘルパ。（例外共通化など将来拡張前提）
        run_scene(scene, screen)


