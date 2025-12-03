from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional
import pygame

# ✅ 既存の“共通イベントUI”をそのまま再利用します
#    - タイプライター / AUTO / SKIP / FAST（Ctrl）/ Enterヒント / バッジ表示 / 行ごとの BGM/SE/VOICE/bg
from scenes.intro_event import IntroEventScene  # 共通UI本体（ここに寄せて統一）  :contentReference[oaicite:3]{index=3}
from scenes.scene_manager import run_scene, make_dialogue_controller

# （任意）足音を確実に止めるために SoundManager API を使います
try:
    from core.sound_manager import SoundManager
except Exception:
    SoundManager = None  # 型注釈用のフォールバック

# ------------------------------------------------------------
# ドクターイベント専用スクリプト（IntroEventScene の書式に合わせる）
#   - 各行は str でも dict でもOK。dict ならBGM/SE/VOICE/bg 指示が可能。
#   - ここを差し替えるだけで演出や音の連動を柔軟に制御できます。
# ------------------------------------------------------------

DOCTOR_SCRIPT: list[list[dict[str, object]]] = [

    [
        {"text": "建物の入口の前までたどり着いた。", "voice": "voice_lab_front_001.mp3.enc"},
        {"text": "その時、中から白衣の男がよろめくように飛び出してきた。",  "voice": "voice_lab_front_002.mp3.enc"},
        {"text": "何かから全力で逃げてきたみたいだった。", "voice": "voice_lab_front_003.mp3.enc"},
        {"text": "よろめき、息を荒げている。", "voice": "voice_lab_front_004.mp3.enc"},
    ],
    [
        {"text": "男は私を見た途端、ぎょっと目を見開いた。",
         "voice": "voice_lab_front_005.mp3.enc",
         "bg": "assets/sprites/lab_front_doctor_shock_close_02.png"},
        {"text": "その驚きはほんの一瞬で、すぐに必死の色へと変わった。", "voice": "voice_lab_front_006.mp3.enc"},

    ],
    [
        {"text": "「……ユ、ユイ！　……生きていたのか……！」",
         "voice": "voice_lab_front_007.mp3.enc",
         "bg": "assets/sprites/lab_front_doctor_closeup_03.png"},

    ],
    [
        {"text": "ユイ。", "voice": "voice_lab_front_008.mp3.enc"},
        {"text": "彼は私にむかってそう呼んだ",  "voice": "voice_lab_front_009.mp3.enc"},
        {"text": "……これが私の名前？", "voice": "voice_lab_front_010.mp3.enc"},
    ],
    [
        {"text": "「待って……あなた、私を知ってるの？",  "voice": "voice_lab_front_011.mp3.enc",
         "bg": "assets/sprites/lab_front_doctor_hurry_06.png"},
        {"text": " ここはどこ？ 私は……いったい誰なの……？」",    "voice": "voice_lab_front_012.mp3.enc"},
        {"text": "言葉がこぼれた瞬間、男の表情が変わった。",    "voice": "voice_lab_front_013.mp3.enc"},
        {"text": "驚きや焦りが混じった、複雑な表情。",        "voice": "voice_lab_front_014.mp3.enc"},
    ],
    [
        {"text": "「……そうだな、",               "voice": "voice_lab_front_015.mp3.enc"},
        {"text": "　そう、君は記憶が混濁しているんだ。",            "voice": "voice_lab_front_016.mp3.enc"},
        {"text": "　事故の、衝撃でな……。」",    "voice": "voice_lab_front_017.mp3.enc"},

    ],
    [
        {"text": "「いいか、落ち着いて聞いてくれ。",               "voice": "voice_lab_front_018.mp3.enc"},
        {"text": "　君は――私の助手だ。",            "voice": "voice_lab_front_019.mp3.enc"},
        {"text": "　“ユイ・ミナセ”。",    "voice": "voice_lab_front_020.mp3.enc"},
        {"text": "　この研究所で一緒に……研究をしていた。」",    "voice": "voice_lab_front_021.mp3.enc"},
    ],
    [
        {"text": "“ユイ・ミナセ”。",               "voice": "voice_lab_front_022.mp3.enc"},
        {"text": "これが、私の名前なの？",            "voice": "voice_lab_front_023.mp3.enc"},
        {"text": "まだ頭がぼんやりする……。",    "voice": "voice_lab_front_024.mp3.enc"},
        {"text": "男は息を整えながら続けた。",    "voice": "voice_lab_front_025.mp3.enc"},
    ],
    [
        {"text": "「事故で吹き飛ばされて、行方不明だった。",        "voice": "voice_lab_front_026.mp3.enc"},
        {"text": "記憶が混乱しているのも当然だ……。",        "voice": "voice_lab_front_027.mp3.enc"},
        {"text": "しかし今はとにかく状況が逼迫している。」",        "voice": "voice_lab_front_028.mp3.enc"},        
    ],
    [
        {"text": "博士は話しながらも落ち着きなく周囲を見回している。",
        "voice": "voice_lab_front_029.mp3.enc",
         "bg": "assets/sprites/lab_front_doctor_lookback_04.png"},
        {"text": "なにかに怯えているようだ。",        "voice": "voice_lab_front_030.mp3.enc"},        
    ],
    [
        {"text": "「事故の混乱で、生物兵器“被験体13号”が逃走したんだ！",
        "voice": "voice_lab_front_031.mp3.enc",
         "bg": "assets/sprites/lab_interior_broken_door_warning_08.png"},
        {"text": "　あれは非常に危険だ……",     "voice": "voice_lab_front_032.mp3.enc"},
        {"text": "　もう我々ではどうすることもできない。」",       "voice": "voice_lab_front_033.mp3.enc"},
    ],
    [
        {"text": "「非常通路が研究所の奥にある。",
        "voice": "voice_lab_front_034.mp3.enc",
         "bg": "assets/sprites/lab_interior_shadow_hallway_05.png"},
        {"text": "　そこからならこの森を抜けられる。",     "voice": "voice_lab_front_035.mp3.enc"},
        {"text": "　ユイ、君はそこへ向かうんだ。いいな？", "voice": "voice_lab_front_036.mp3.enc"},
        {"text": "　私も軍部に連絡したら急いで合流する！」",     "voice": "voice_lab_front_037.mp3.enc"},
    ],
    [
        {"text": "逃げろと言われても、急展開すぎて頭が追いつかない。",
         "voice": "voice_lab_front_038.mp3.enc",
         "bg": "assets/sprites/lab_front_to_forest_view_07.png"},
        {"text": "だが、この場に留まる方が危険だ。",   "voice": "voice_lab_front_039.mp3.enc"},
        {"text": "白衣の男の必死な様子から、それは痛いほど分かった。",       "voice": "voice_lab_front_040.mp3.enc"},
    ],
    [
        {"text": "この状況で選択肢なんてなかった。",          "voice": "voice_lab_front_041.mp3.enc"},
        {"text": "私はただ、言われるままに頷いた。",                   "voice": "voice_lab_front_042.mp3.enc"},
    ],
]

class DoctorEventScene(IntroEventScene):
    """
    ✅ ドクター遭遇イベント（UI/挙動は IntroEventScene と完全同一）
    - `IntroEventScene` を継承し、`self.pages` にドクター用スクリプトを設定するだけ。
    - 必要なら専用背景（bg_path）やBGM開始などをここで追加。
    """
    def __init__(
        self,
        base_dir: Path,
        *,
        dialogue_ctrl=None,
        sound_manager=None,
        bg_path: Optional[str] = "assets/sprites/lab_front_doctor_stumble_01.png",  # 必要に応じて差し替え
        pages: Optional[List[List[Dict[str, Any] | str]]] = None,
    ):
        # --- 共通UIの初期化（タイプ描画/AUTO/SKIP/ヒント/バッジ等すべて有効化） ---
        super().__init__(
            base_dir=base_dir,
            bg_path=bg_path,
            dialogue_ctrl=dialogue_ctrl,
            sound_manager=sound_manager,
        )
        # このイベント専用のページ（台本）に差し替え
        self.pages = pages or DOCTOR_SCRIPT
        self._skip_all_silent = False  # Esc 全スキップ後は音を鳴らさないフラグ
        
        # ☆ 足音ループが残っているケースの保険：開始時に静音＋足音停止（存在すれば）
        try:
            if self.sm is not None:
                if hasattr(self.sm, "hush_effects_for_cutscene"):
                    self.sm.hush_effects_for_cutscene(fade_ms=160)
                if hasattr(self.sm, "stop_loop"):
                    self.sm.stop_loop(name="footstep", fade_ms=80)
        except Exception:
            pass


def run_doctor_event(screen: pygame.Surface, base_dir: Path, *, sound_manager=None) -> Dict[str, bool]:
    """
    既存呼び出し互換のラッパ関数。
    - UI/挙動は IntroEventScene と同一。
    - 戻り値: {"played_to_end": bool}（Escの全スキップ等で中断したら False）
    """
    # 既存フローと同様：コントローラは共通ファクトリから生成し、挙動を統一
    ctrl = make_dialogue_controller()
    scene = DoctorEventScene(
        base_dir=base_dir,
        dialogue_ctrl=ctrl,
        sound_manager=sound_manager,  # ← ★必ず注入：SE/BGM連動の要（startup.pyと同じ思想）  :contentReference[oaicite:4]{index=4}
    )
    # 共通ランナーで実行（フェードや入力ループはシーン側に集約）
    run_scene(scene, screen)
    # SKIPで最後まで読んでいない場合を検出（IntroEventSceneの状態を参照）
    played_to_end = not getattr(getattr(scene, "ctrl", None), "st", object()).__dict__.get("is_skip", False)
    return {"played_to_end": bool(played_to_end)}