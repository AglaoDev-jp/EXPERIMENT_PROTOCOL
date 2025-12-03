# scenes/intro_event.py
# -*- coding: utf-8 -*-
"""
一枚絵＋テキスト“導入イベント”シーン（行送り＋ページ送り＋タイプライター＋オート/スキップ対応）

【機能】
- タイピング：日本語向けに句読点で“間”を少し追加
- 行送り：行末で ▶（Enter待ち）
- ページ送り：ページ末で 📄（Enterで次ページ）
- 最終行：Enterでフェードアウトして終了→本編へ
- オート/スキップ：共通モジュール core/dialogue_flow.py と連携
  - A：オート切替（行/ページ末で自動で先へ）
  - S：スキップ切替（即時全表示＆自動で最後まで）
  - Ctrl：押している間だけ高速（タイプ速度を乗算で短縮）
  - Esc：全スキップの確認ダイアログ（はい→即終了）

【前提】
- core/dialogue_flow.py が存在する場合はそちらを使用（推奨）
- 万一未導入でも、内部の簡易コントローラで最低限は動作（フォールバック）
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Union, Dict, Any
import pygame

# --- 既存プロジェクトの共通部品 ---
from core.config import WIDTH, HEIGHT
from core.asset_utils import load_or_placeholder
from core.fonts import render_text
from core.transitions import fade_in, fade_out

# --- オート/スキップの共通コントローラ（存在すれば使う） ---
_HAS_DIALOGUE_FLOW = True
try:
    from core.dialogue_flow import (
        DialogueConfig, DialogueController,
        KEY_NEXT, KEY_AUTO_TOGGLE, KEY_SKIP_TOGGLE, KEY_FAST_HELD, KEY_SKIP_ALL,
    )
except Exception:
    _HAS_DIALOGUE_FLOW = False
    # ---- フォールバック（最低限の代替。細かな挙動は簡略化） ----
    KEY_NEXT = "NEXT"
    KEY_AUTO_TOGGLE = "AUTO_TOGGLE"
    KEY_SKIP_TOGGLE = "SKIP_TOGGLE"
    KEY_FAST_HELD = "FAST_HELD"
    KEY_SKIP_ALL = "SKIP_ALL"

    class DialogueConfig:
        def __init__(self,
                     type_ms_per_char=22,
                     punct_pause_ms=None,
                     auto_enabled_default=False,
                     auto_line_delay_ms=700,
                     auto_page_delay_ms=900,
                     fast_multiplier=0.33,
                     skip_toggle_sticky=True):
            self.type_ms_per_char = type_ms_per_char
            self.punct_pause_ms = punct_pause_ms or {
                "。": 120, "、": 80, "，": 80, ",": 80, ".": 100,
                "！": 120, "!": 120, "？": 130, "?": 130,
                "…": 120, "―": 100, "—": 100, "」": 80,
            }
            self.auto_enabled_default = auto_enabled_default
            self.auto_line_delay_ms = auto_line_delay_ms
            self.auto_page_delay_ms = auto_page_delay_ms
            self.fast_multiplier = fast_multiplier
            self.skip_toggle_sticky = skip_toggle_sticky

    class _State:
        def __init__(self, cfg: DialogueConfig):
            self.is_auto = cfg.auto_enabled_default
            self.is_skip = False
            self.fast_held = False
            self.next_tick_ms = 0
            self.auto_wait_until_ms = 0

    class DialogueController:
        """超簡易版：本家と同じメソッド名を持つ互換ラッパ"""
        def __init__(self, cfg: DialogueConfig):
            self.cfg = cfg
            self.st = _State(cfg)

        def on_key(self, action_name: str, pressed: bool = True):
            if action_name == KEY_AUTO_TOGGLE and pressed:
                self.st.is_auto = not self.st.is_auto
            elif action_name == KEY_SKIP_TOGGLE and pressed:
                self.st.is_skip = not self.st.is_skip
            elif action_name == KEY_FAST_HELD:
                self.st.fast_held = pressed
            elif action_name == KEY_SKIP_ALL and pressed:
                self.st.is_skip = True

        def plan_next_char(self, now_ms: int, is_line_done: bool, last_char: Optional[str]) -> int:
            if is_line_done:
                return now_ms
            base = self.cfg.type_ms_per_char
            if self.st.is_skip:
                base = 0
            elif self.st.fast_held:
                base = int(base * self.cfg.fast_multiplier)
            pause = self.cfg.punct_pause_ms.get(last_char, 0) if last_char else 0
            return now_ms + max(0, base + pause)

        def request_advance(self, now_ms: int, is_line_done: bool, is_page_end: bool, is_script_end: bool, next_request: bool) -> Optional[str]:
            if self.st.is_skip:
                if not is_line_done: return "REVEAL_LINE"
                if not is_page_end:  return "NEXT_LINE"
                if not is_script_end:return "NEXT_PAGE"
                return "END_SCENE"
            if next_request:
                if not is_line_done: return "REVEAL_LINE"
                if not is_page_end:  return "NEXT_LINE"
                if not is_script_end:return "NEXT_PAGE"
                return "END_SCENE"
            if self.st.is_auto and self.st.auto_wait_until_ms and now_ms >= self.st.auto_wait_until_ms:
                if not is_page_end:
                    self.st.auto_wait_until_ms = 0
                    return "NEXT_LINE"
                if not is_script_end:
                    self.st.auto_wait_until_ms = 0
                    return "NEXT_PAGE"
                return "END_SCENE"
            return None

        def arm_auto_wait(self, now_ms: int, is_page_end: bool):
            if not self.st.is_auto or self.st.is_skip:
                self.st.auto_wait_until_ms = 0
                return
            delay = self.cfg.auto_page_delay_ms if is_page_end else self.cfg.auto_line_delay_ms
            self.st.auto_wait_until_ms = now_ms + max(0, delay)

# ------------------------------------------------------------
# ★ スクリプト（ページ単位で配列化。各ページは複数“行”を持つ）
#    自動改行はしません。長い文は手動で分けてください。
# 文字列だけでもOK、行ごと制御を入れたい場合は dict を使う:
# 行dictで使えるキー:
# - text (必須): 行テキスト
# - bgm: "xxx.mp3" / "xxx.mp3.enc" （assets/sounds/bgm/配下）
# - bgm_stop: True ならBGM停止（bgm_fade_ms と併用可　例: "bgm_stop": True）
# - bgm_fade_ms: フェード停止ミリ秒
# - se: SoundManagerに事前登録された SEキー名（例: "switch_ok"）
# - voice: "voice_file.mp3" / ".enc"（assets/sounds/voice/配下）
# - bg: 背景差し替えパス（例: "assets/sprites/forest_close.png"）
# ------------------------------------------------------------
INTRO_SCRIPT = [
    [
        { "text": "……冷たい土の感触で、私は目を覚ました。", "voice": "voice_intro_001.mp3.enc"},
        { "text": "湿った空気の中に、草と土の匂いが混じっている。", "voice": "voice_intro_002.mp3.enc" },
        { "text": "ここは……どこ？　私は……誰？", "voice": "voice_intro_003.mp3.enc" },
        { "text": "記憶が、霧の中に沈んでいるように掴めない。", "voice": "voice_intro_004.mp3.enc"}
    ],
    [
        { "text": "立ち上がろうとした瞬間、鋭い痛みが全身を走った。", "voice": "voice_intro_005.mp3.enc" },
        { "text": "腕にも足にも、擦り傷や青あざがいくつもある。", "voice": "voice_intro_006.mp3.enc" },
        { "text": "どうして……？　私は、何をしていたんだろう。", "voice": "voice_intro_007.mp3.enc" },
        { "text": "誰かに襲われた？　それとも、逃げていた……？", "voice": "voice_intro_008.mp3.enc" }
    ],
    [
        { "text": "見渡す限り、夜の森。", "voice": "voice_intro_009.mp3.enc" },
        { "text": "月明かりが木々の隙間を照らし、霧が地面を這っている。", "voice": "voice_intro_010.mp3.enc" },
        { "text": "風が止み、世界が静止したように感じた、そのとき——", "voice": "voice_intro_011.mp3.enc" }
    ],
    [
        { "text": "…………！！", 
         "voice": "ゴブリンの鳴き声3.mp3.enc" ,
         "bg_color": [0, 0, 0] # 画面を黒で塗りつぶし
        },
    ],
    [
        { "text": "うなり声！？", 
         "voice": "voice_intro_012.mp3.enc",
         "bgm": "異次元空間.mp3.enc"},
        { "text": "耳を疑った。濁った音がどこかで響く。", "voice": "voice_intro_013.mp3.enc" },
        { "text": "動物……？　それとも、人……？", "voice": "voice_intro_014.mp3.enc" },
        { "text": "背筋が粟立ち、思わず呼吸を止めた。", "voice": "voice_intro_015.mp3.enc" }
    ],
    [
        { "text": "ここに留まってはいけない……そんな予感がした。", "voice": "voice_intro_016.mp3.enc" },
        { "text": "ふらつきながらも、私は歩き出した。", 
         "voice": "voice_intro_017.mp3.enc" ,
         "bg": "assets/sprites/intro_forest_bg.png"
        },
        { "text": "どこへ向かうのかもわからないまま、足を前へと進める。", "voice": "voice_intro_018.mp3.enc" },
        { "text": "止まってしまえば、二度と朝を迎えられない気がして……。", 
         "voice": "voice_intro_019.mp3.enc" ,
         "bgm_stop": True, "bgm_fade_ms": 600}
    ]
]

# ------------------------------------------------------------
# 表示パラメータ（お好みで調整OK）
# ------------------------------------------------------------
FONT_SIZE = 20               # 本文フォントサイズ
LINE_GAP = 4                 # 行間（px）
PANEL_MARGIN = 30            # 画面端からのパネル余白（px）
PANEL_ALPHA = (0, 0, 0, 170) # パネルの半透明色（RGBA）
PANEL_RADIUS = 12            # パネル角丸

HINT_BLINK_MS = 900          # 点滅周期（ms）
ENTER_HINT_NEXT = "Enter：つづける"
ENTER_HINT_PAGE = "Enter：次のページ"
ENTER_HINT_LAST = "Enter：はじめる"
# ヒントの描画方法を切り替えられるようにする（将来アイコン差し替えにも対応）
# "text"  : 既存どおり文字（render_text）
# "image" : 画像（enter_next.png 等）に切替可
HINT_RENDER_MODE = "text"

# ヒントの表示位置：
# "panel" : 従来どおりパネル内右下（※本文に被りやすい）
# "below" : パネルの外（画面右下）→ 本文と重ならないので推奨
HINT_POSITION = "below"

# パネル外に出すときの余白（px）
HINT_MARGIN_OUTER_X = 16
HINT_MARGIN_OUTER_Y = 14

# 画像モード用のプレース（必要に応じて実ファイルに置換）
HINT_IMG_PATHS = {
    "NEXT": "assets/sprites/ui/enter_next.png",
    "PAGE": "assets/sprites/ui/enter_page.png",
    "LAST": "assets/sprites/ui/enter_start.png",
}

# 状態バッジの色（AUTO / SKIP / FAST 表示）
BADGE_BG = (0, 0, 0, 140)
BADGE_OUTLINE = (255, 255, 255, 40)

class IntroEventScene:
    """
    一行ずつ → ページ末で📄 → 最終行で終了。
    DialogueController を受け取り、全シーンで共通の“読み進め”を使い回せます。
    """
    def __init__(self,
                 base_dir: Path,
                 bg_path: Optional[str] = None,
                 dialogue_ctrl: Optional[DialogueController] = None,
                 sound_manager=None):
        # 背景（無ければプレースホルダ）
        self.bg = load_or_placeholder(
            base_dir,
            bg_path or "assets/sprites/intro_forest_bg.png",
            size=(WIDTH, HEIGHT),
            shape="rect",
            label="INTRO",
        )
        # ★背景色（None のときは画像を使う）
        #   - bg_color が指定された行で (R,G,B) をセット
        #   - 画像に戻す行で bg_color を None に戻す
        self.bg_color = None  # type: Optional[tuple[int, int, int]]        
        # 音まわり（任意）
        self.sm = sound_manager
        # カットシーンに入る直前に足音や単発SEを静音（存在すれば）
        try:
            if self.sm is not None and hasattr(self.sm, "hush_effects_for_cutscene"):
                self.sm.hush_effects_for_cutscene(fade_ms=120)
        except Exception:
            pass

        # Esc で「全部スキップ」したあと、
        # 残りの行では BGM/SE/VOICE を一切鳴らさないためのフラグ。
        # True の間は行頭サイドエフェクトを“サイレント処理”に切り替えます。
        self._skip_all_silent: bool = False

        # パネル矩形（画面下部）
        self.panel_rect = self._make_panel_rect()

        # スクリプト状態
        self.pages: List[List[Union[str, Dict[str, Any]]]] = INTRO_SCRIPT
        self.page_idx = 0
        self.line_idx = 0
        self.char_idx = 0
        self.finished = False
        # 行頭で一度だけ指示を反映したかどうか
        self._line_side_effect_applied = False

        # コントローラ：渡されなければ（モジュールがあれば）標準設定で生成
        if dialogue_ctrl is not None:
            self.ctrl = dialogue_ctrl
        else:
            cfg = DialogueConfig(
                type_ms_per_char=22,
                auto_enabled_default=False,
                auto_line_delay_ms=700,
                auto_page_delay_ms=900,
                fast_multiplier=0.33,
            )
            self.ctrl = DialogueController(cfg)

        # 初期のタイプ時刻
        self.ctrl.st.next_tick_ms = 0

    # ---------- レイアウト ----------
    def _make_panel_rect(self) -> pygame.Rect:
        w = WIDTH - PANEL_MARGIN * 2
        h = int(HEIGHT * 0.38)
        x = PANEL_MARGIN
        y = HEIGHT - h - PANEL_MARGIN
        return pygame.Rect(x, y, w, h)

    def _line_height(self) -> int:
        surf = render_text("あ", size=FONT_SIZE, color=(255, 255, 255), outline=True, outline_px=2)
        return surf.get_height()

    # ---------- 状態問い合わせ ----------
    def _current_line_raw(self) -> Union[str, Dict[str, Any]]:
        return self.pages[self.page_idx][self.line_idx]

    def _current_line_text(self) -> str:
        ln = self._current_line_raw()
        if isinstance(ln, dict):
            return str(ln.get("text", ""))
        return str(ln)

    def _at_line_end(self) -> bool:
        return self.char_idx >= len(self._current_line_text())

    def _at_page_end(self) -> bool:
        return self.line_idx >= len(self.pages[self.page_idx]) - 1

    def _at_script_end(self) -> bool:
        return (self.page_idx >= len(self.pages) - 1) and self._at_page_end() and self._at_line_end()

    # ---------- 行頭のサイドエフェクト適用 ----------
    def _apply_line_side_effects_if_needed(self) -> None:
        """
        行レンダリング開始時（最初の1文字を出す直前）に一度だけ適用。
        BGM/SE/VOICE/背景差し替えなどの指示を処理します。
        """
        if self._line_side_effect_applied:
            return

        # ★ Esc / S スキップでサイレントモードに入っている場合は、
        #    この行の BGM/SE/VOICE/背景変更などを何も実行せずに抜ける。
        #    ただし「この行は処理済み」というフラグだけは立てておく。
        if self._skip_all_silent:
            self._line_side_effect_applied = True
            return

        raw = self._current_line_raw()
        if not isinstance(raw, dict):
            self._line_side_effect_applied = True
            return

        # Esc で「全部スキップ」したあとは、
        # 残りの行の BGM/SE/VOICE を一切発火させたくないので、
        # 背景なども含めてここで何もせず return します。
        # （ただし「この行は処理済み」というフラグだけは立てておく）
        if getattr(self, "_skip_all_silent", False):
            self._line_side_effect_applied = True
            return
        
        raw = self._current_line_raw()
        if not isinstance(raw, dict):
            self._line_side_effect_applied = True
            return

        # ★ 背景色の変更（bg_color があれば優先して色塗りモードに入る）
        #   - 例: "bg_color": [0, 0, 0] で画面真っ黒
        #   - この行以降は self.bg_color が有効になる
        if "bg_color" in raw:
            col = raw.get("bg_color")
            try:
                # list / tuple から (R,G,B) を取り出す
                if isinstance(col, (list, tuple)) and len(col) >= 3:
                    r, g, b = int(col[0]), int(col[1]), int(col[2])
                    self.bg_color = (r, g, b)
                else:
                    # フォーマットがおかしい場合は色指定を無効化
                    self.bg_color = None
            except Exception:
                self.bg_color = None

        # 背景差し替え（画像）
        bg_path = raw.get("bg")
        if bg_path:
            try:
                self.bg = load_or_placeholder(
                    Path("."),
                    bg_path,
                    size=(WIDTH, HEIGHT),
                    shape="rect",
                    label="INTRO",
                )
                # ★画像を指定された行では、背景色モードは解除して画像に戻す
                self.bg_color = None
            except Exception:
                pass

        # BGM制御
        if self.sm is not None:
            try:
                if raw.get("bgm_stop"):
                    fade_ms = int(raw.get("bgm_fade_ms", 0))
                    if fade_ms > 0 and hasattr(self.sm, "fadeout_bgm"):
                        self.sm.fadeout_bgm(ms=fade_ms)
                    elif hasattr(self.sm, "stop_bgm"):
                        self.sm.stop_bgm()
                elif "bgm" in raw and raw["bgm"]:
                    self.sm.play_bgm(str(raw["bgm"]))
            except Exception:
                pass
            # 効果音
            try:
                if "se" in raw and raw["se"]:
                    self.sm.play_se(str(raw["se"]))
            except Exception:
                pass
            # ボイス
            try:
                if "voice" in raw and raw["voice"]:
                    self.sm.play_voice(str(raw["voice"]))
            except Exception:
                pass
            
            self._line_side_effect_applied = True

    def _mute_all_sounds_for_skip(self) -> None:
        """スキップ開始時に現在のサウンドをすべて止めるヘルパー。"""
        # pygame 側の全チャンネルを停止
        try:
            pygame.mixer.stop()
        except Exception:
            pass

        # SoundManager 経由の制御（あれば）
        if self.sm is None:
            return

        # 効果音
        try:
            if hasattr(self.sm, "stop_all_se"):
                self.sm.stop_all_se()
        except Exception:
            pass

        # BGM
        try:
            if hasattr(self.sm, "stop_bgm"):
                self.sm.stop_bgm()
        except Exception:
            pass

        # ボイス
        try:
            if hasattr(self.sm, "stop_voice"):
                self.sm.stop_voice()
        except Exception:
            pass

    # ---------- イベント（入力）処理 ----------
    def _handle_event(self, ev) -> bool:
        """
        pygameイベントを“論理入力”に変換してコントローラに通知。
        戻り値 True：NEXT入力（進め要求）が発生
        """
        # ▼ キーが押されたとき
        if ev.type == pygame.KEYDOWN:
            # Enter / Space → NEXT
            if ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                return True  # NEXT

            # オート切替（A）
            if ev.key == pygame.K_a:
                self.ctrl.on_key(KEY_AUTO_TOGGLE)

            # スキップ切替（S）
            if ev.key == pygame.K_s:
                # 押下前の状態を覚えておく
                was_skip = self.ctrl.st.is_skip
                self.ctrl.on_key(KEY_SKIP_TOGGLE)

                # OFF → ON になった瞬間にサイレントスキップへ
                if (not was_skip) and self.ctrl.st.is_skip:
                    # 以降の行頭サイドエフェクトを無効化
                    self._skip_all_silent = True
                    # 現在鳴っているサウンドもすべて止める
                    self._mute_all_sounds_for_skip()

                # ON → OFF（スキップ解除）になったときは、
                # ここから先の行ではふつうに音を鳴らしたいので元に戻す
                elif was_skip and (not self.ctrl.st.is_skip):
                    # サイレントモード解除
                    self._skip_all_silent = False
                    # 「この行はもう副作用を適用済み」というフラグをリセット。
                    # 次のフレームで _apply_line_side_effects_if_needed() が
                    # 改めて BGM/SE/VOICE を適用できるようにする。
                    self._line_side_effect_applied = False

            # 高速（Ctrl）：keydownでON
            if ev.key in (pygame.K_LCTRL, pygame.K_RCTRL):
                self.ctrl.on_key(KEY_FAST_HELD, pressed=True)

            # 全スキップ（Esc）：確認のうえ確定なら SKIP_ALL
            if ev.key == pygame.K_ESCAPE:
                if self._confirm_skip():
                    # Esc もサイレントスキップに統一
                    self._skip_all_silent = True
                    self._mute_all_sounds_for_skip()
                    self.ctrl.on_key(KEY_SKIP_ALL, pressed=True)
                    # 以降の制御は controller に委ねる

        # ▼ キーが離されたとき
        elif ev.type == pygame.KEYUP:
            if ev.key in (pygame.K_LCTRL, pygame.K_RCTRL):
                self.ctrl.on_key(KEY_FAST_HELD, pressed=False)

        # ▼ マウス左クリック → NEXT
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            return True  # NEXT

        return False

    # ---------- タイプ進行 ----------
    def _tick_typing(self):
        """コントローラの計画に従って、1文字ずつ進める。"""
        if self._at_line_end():
            return
        now = pygame.time.get_ticks()
        if now < getattr(self.ctrl.st, "next_tick_ms", 0):
            return

        # 1文字進行
        self.char_idx += 1

        # 次の予定時刻を計画（句読点の“間”など）
        s_text = self._current_line_text()  # ★ dict/str両対応
        last = s_text[self.char_idx - 1] if self.char_idx > 0 and len(s_text) > 0 else None
        self.ctrl.st.next_tick_ms = self.ctrl.plan_next_char(now_ms=now, is_line_done=False, last_char=last)

        # 行を出し切った直後：
        #   ・手動進行の場合 → 今までどおり arm_auto_wait() を呼んでも害はない
        #   ・オート進行の場合 → ボイスとの連携のため run() 側で予約したい
        if self._at_line_end():
            # オートONのときは run() 側の _update_auto_wait_for_voice() で
            # 「ボイス再生の終了を待ってから予約」するので、ここでは予約しない。
            if not getattr(self.ctrl.st, "is_auto", False):
                self.ctrl.arm_auto_wait(now_ms=now, is_page_end=self._at_page_end())

    # ---------- 進行アクション適用 ----------
    def _apply_action(self, action: Optional[str]):
        """
        controller.request_advance() の戻り値アクションを実際の状態に反映。
        """
        if not action:
            return
        now = pygame.time.get_ticks()

        if action == "REVEAL_LINE":
            self.char_idx = len(self._current_line_text())  # ★ dict/str 両対応
            # “出し切った”のでオート予約
            self.ctrl.arm_auto_wait(now_ms=now, is_page_end=self._at_page_end())

        elif action == "NEXT_LINE":
            if not self._at_page_end():
                self.line_idx += 1
                self.char_idx = 0
                self._line_side_effect_applied = False
                self.ctrl.st.next_tick_ms = now  # すぐタイプ再開
                self._line_side_effect_applied = False  # ★ 次の行で行頭副作用をもう一度

        elif action == "NEXT_PAGE":
            if self.page_idx < len(self.pages) - 1:
                self.page_idx += 1
                self.line_idx = 0
                self.char_idx = 0
                self._line_side_effect_applied = False
                self.ctrl.st.next_tick_ms = now
                self._line_side_effect_applied = False  # ★ ページ先頭行でも適用させる

        elif action == "END_SCENE":
            self.finished = True

    # ---------- スキップ確認 ----------
    def _confirm_skip(self) -> bool:
        # 半透明オーバレイ
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen = pygame.display.get_surface()
        screen.blit(overlay, (0, 0))

        # ダイアログ
        box = pygame.Rect(0, 0, 420, 140); box.center = (WIDTH // 2, HEIGHT // 2)
        pygame.draw.rect(screen, (0, 0, 0, 210), box, border_radius=12)
        pygame.draw.rect(screen, (255, 255, 255, 40), box, 1, border_radius=12)

        t1 = render_text("このイベントをスキップしますか？", size=20, color=(255, 255, 255), outline=True, outline_px=2)
        t2 = render_text("Y：はい    N：いいえ", size=18, color=(255, 255, 255), outline=True, outline_px=2)
        screen.blit(t1, (box.x + 20, box.y + 24))
        screen.blit(t2, (box.x + 20, box.y + 82))
        pygame.display.flip()

        # ブロッキングで Y/N 待ち
        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); raise SystemExit
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_y:
                        return True
                    if ev.key in (pygame.K_n, pygame.K_ESCAPE):
                        return False
            pygame.time.delay(10)

    # ---------- 描画 ----------
    def _draw_background(self, screen: pygame.Surface):
        # ★ 背景色が指定されている間は、画面全体をその色で塗る
        if self.bg_color is not None:
            # 画面全体を (R,G,B) で塗りつぶし
            screen.fill(self.bg_color)
        else:
            # 通常どおり、背景画像を拡大して描画
            screen.blit(
                pygame.transform.smoothscale(self.bg, (WIDTH, HEIGHT)),
                (0, 0)
            )

    def _draw_state_badges(self, screen: pygame.Surface):
        """
        AUTO / SKIP / FAST の状態バッジ。

        ※ 以前は panel 内に描画していたが、
           テキストとかぶる & 上方向に余白が取りづらいので、
           画面（screen）に直接描画する形に変更する。

           ・self.panel_rect の「右上」あたりに配置
           ・パネルより少し上に出すことで文字と重ならない
        """
        labels = []
        if getattr(self.ctrl.st, "is_auto", False):
            labels.append("[AUTO]")
        if getattr(self.ctrl.st, "is_skip", False):
            labels.append("[SKIP]")
        if getattr(self.ctrl.st, "fast_held", False):
            labels.append("[FAST]")
        if not labels:
            return

        # バッジのテキスト部分
        txt = " ".join(labels)
        surf = render_text(
            txt,
            size=14,
            color=(255, 255, 255),
            outline=True,
            outline_px=2,
        )

        # バッジ用の余白
        pad = 6
        w, h = surf.get_width() + pad * 2, surf.get_height() + pad * 2

        # 透過付きのバッジ本体
        badge = pygame.Surface((w, h), pygame.SRCALPHA)

        # 背景矩形（角丸）
        pygame.draw.rect(
            badge, BADGE_BG,
            (0, 0, w, h),
            border_radius=8,
        )
        # 枠線
        pygame.draw.rect(
            badge, BADGE_OUTLINE,
            (0, 0, w, h),
            1,
            border_radius=8,
        )

        # テキストを内部に配置
        badge.blit(surf, (pad, pad))

        # ---------------------------------------------------
        #  ★ パネルの「右上」＋少し上にずらして画面に描画する
        #     → テキストとはかぶらず、かつ見切れない
        # ---------------------------------------------------
        # 右端はパネルの右端に合わせる
        x = self.panel_rect.right - w - 3
        # Y は「パネル上端より少し上」に配置
        y = self.panel_rect.top - h + 8

        # 万が一パネルがかなり上に来たときでも、画面外に出ないようにクランプ
        if y < 4:
            y = 4

        # 画面に直接ブリットする
        screen.blit(badge, (x, y))


    def _draw_panel(self, screen: pygame.Surface):
        panel = pygame.Surface(self.panel_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, PANEL_ALPHA, panel.get_rect(), border_radius=PANEL_RADIUS)
        pygame.draw.rect(panel, (255, 255, 255, 50), panel.get_rect(), 1, border_radius=PANEL_RADIUS)

        # 1行ずつ描画。今の行は“char_idx”まで、前の行は全表示。
        x_pad, y_pad = 20, 16
        x, y = x_pad, y_pad
        lh = self._line_height()

        lines = self.pages[self.page_idx]
        for i, raw in enumerate(lines):
            if i > 0:
                y += LINE_GAP
            # 表示テキストの決定
            # ★ dict/str 両対応で表示テキストを取り出す
            full_text = raw.get("text", "") if isinstance(raw, dict) else str(raw)
            # 表示テキストの決定（既読＝全表示、現在行＝char_idx まで、未読＝空）
            if i < self.line_idx:
                draw_text = full_text
            elif i == self.line_idx:
                draw_text = full_text[:self.char_idx] # タイプ中
            else:
                draw_text = "" # まだ
            if draw_text:
                surf = render_text(draw_text, size=FONT_SIZE, color=(255, 255, 255), outline=True, outline_px=2)
                panel.blit(surf, (x, y))
            y += lh

        # ヒント（点滅）
        t = pygame.time.get_ticks()
        blink_on = (t // (HINT_BLINK_MS // 2)) % 2 == 0

        # ★オートモード中は文字送りヒントを表示しない
        #   （プレイヤー操作不要なので、Enter案内は邪魔になるため）
        if getattr(self.ctrl.st, "is_auto", False):
            blink_on = False        

        # --- 置換：ヒントを作って描画（パネル内 or パネル外の2モード） ---
        if blink_on:
            hint_kind = None
            if self._at_script_end():
                hint_kind = "LAST"
            elif self._at_line_end():
                hint_kind = "PAGE" if self._at_page_end() else "NEXT"

            if hint_kind:
                # 1) ヒント用サーフェスを用意（文字 or 画像）
                if HINT_RENDER_MODE == "image":
                    # 画像ヒント：存在しない場合でも load_or_placeholder で代替
                    img_path = HINT_IMG_PATHS[hint_kind]
                    hint = load_or_placeholder(
                        Path("."),  # base_dirは不要（相対扱い）。必要なら self.base_dir を持たせる
                        img_path,
                        size=None,   # 原寸を使いたい場合は None
                        shape="rect",
                        label="HINT",
                    )
                else:
                    # テキストヒント（従来）
                    text_map = {
                        "NEXT": ENTER_HINT_NEXT,
                        "PAGE": ENTER_HINT_PAGE,
                        "LAST": ENTER_HINT_LAST,
                    }
                    hint = render_text(text_map[hint_kind], size=18, color=(255, 255, 255), outline=True, outline_px=2)

                # 2) ブリット位置を決定
                if HINT_POSITION == "panel":
                    # 従来：パネル内右下（※本文と重なる可能性あり）
                    panel.blit(
                        hint,
                        (
                            panel.get_width() - hint.get_width() - 16,
                            panel.get_height() - hint.get_height() - 12,
                        ),
                    )
                else:
                    # パネル外（画面右下）→ 本文と被らない
                    hx = WIDTH - hint.get_width() - HINT_MARGIN_OUTER_X
                    hy = HEIGHT - hint.get_height() - HINT_MARGIN_OUTER_Y

                    # 1) 先にパネルを画面に貼る
                    screen.blit(panel, self.panel_rect.topleft)

                    # 2) 状態バッジ（AUTO / SKIP / FAST）を、
                    #    パネルの少し上に画面へ直接描画
                    self._draw_state_badges(screen)

                    # 3) その上からヒントを画面右下に描画
                    screen.blit(hint, (hx, hy))

                    # ※ display.get_surface() への再ブリットは通常不要なので削除してOK
                    # pygame.display.get_surface().blit(screen, (0, 0))

                    return  # ここで合成完了

        # 1) 先にパネルを画面へ貼る
        screen.blit(panel, self.panel_rect.topleft)

        # 2) 状態バッジ（AUTO / SKIP / FAST）を、
        #    パネルの少し上に画面へ直接描画
        self._draw_state_badges(screen)

    # ---------- ボイスとオートの連携ヘルパー ----------

    def _is_voice_playing(self) -> bool:
        """
        SoundManager に is_voice_playing() があればそれを使って、
        現在ボイスが鳴っているかどうかを返す。
        なければ常に False（= 旧来どおりの挙動）として扱う。
        """
        if self.sm is None:
            return False
        try:
            if hasattr(self.sm, "is_voice_playing"):
                # True/False を期待。None などでも bool(...) で False になる。
                return bool(self.sm.is_voice_playing())
        except Exception:
            # 例外が出てもゲーム進行は止めたくないので握りつぶす
            pass
        return False

    def _update_auto_wait_for_voice(self, now_ms: int) -> None:
        """
        オートモード中、
        「行を出し切ったあと、ボイスが鳴り終わるまでは待つ」
        というための“待機予約”を行う。

        ・オートOFFやスキップ中は何もしない。
        ・行を出し切っていなければ何もしない。
        ・すでに auto_wait_until_ms が入っているなら何もしない。
        ・ボイスがまだ鳴っているなら、“予約を遅らせるだけ”で何もしない。
        ・ボイスが鳴っていなければ、このタイミングで arm_auto_wait() を呼ぶ。
        """
        st = getattr(self.ctrl, "st", None)
        if st is None:
            return

        # オートONかつスキップOFFのときだけ対象
        if not st.is_auto or st.is_skip:
            return

        # まだ行を出し切っていない → そもそもオート進行の条件を満たしていない
        if not self._at_line_end():
            return

        # すでに「いつ進めるか」が予約済みなら触らない
        if st.auto_wait_until_ms:
            return

        # ここまで来た時点で：
        # ・オートON
        # ・行は出し切り済み
        # ・自動進行の予約はまだ入っていない
        # → あとは「ボイスが鳴っているかどうか」で分岐
        if self._is_voice_playing():
            # まだボイス再生中：このフレームでは何もしない。
            # → 次のフレーム以降で「ボイスが止まった」タイミングで予約される。
            return

        # ボイスが鳴っていない（もともと無い or 再生が終わった）ので、
        # ここで初めて “次に自動で進む時刻” を予約する。
        # is_page_end=True なら auto_page_delay_ms が使われる。
        is_page_end = self._at_page_end()
        self.ctrl.arm_auto_wait(now_ms=now_ms, is_page_end=is_page_end)

    # ---------- ランナー ----------
    def run(self, screen: pygame.Surface):
        clock = pygame.time.Clock()
        draw = lambda: (self._draw_background(screen), self._draw_panel(screen))

        # フェードイン
        fade_in(screen, 600, draw_under=draw)

        # 初回のタイプ時刻をセット
        self.ctrl.st.next_tick_ms = pygame.time.get_ticks()

        while not self.finished:
            next_request = False
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); raise SystemExit

                # ★ F11: フルスクリーン切り替え
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F11:
                    try:
                        # SDL にフルスクリーンのトグルを依頼
                        pygame.display.toggle_fullscreen()
                        # 念のため、現在の display Surface を取り直す
                        screen = pygame.display.get_surface()
                    except Exception as e:
                        print(f"[IntroEvent] fullscreen toggle failed: {e}")
                    # このイベントはここで処理済みなので、_handle_event には渡さない
                    continue

                # ▼ それ以外のキー／マウスは、今まで通り _handle_event に任せる
                if self._handle_event(ev):
                    next_request = True

            now = pygame.time.get_ticks()

            # 進行アクション（ユーザー入力/オート/スキップを統合判定）
            action = self.ctrl.request_advance(
                now_ms=now,
                is_line_done=self._at_line_end(),
                is_page_end=self._at_page_end() and self._at_line_end(),
                is_script_end=self._at_script_end(),
                next_request=next_request,
            )
            self._apply_action(action)
            self._apply_line_side_effects_if_needed()

            # オートモードのボイス待ちなど
            self._update_auto_wait_for_voice(now_ms=now)

            # タイプを進める
            self._tick_typing()

            # 描画
            self._draw_background(screen)
            self._draw_panel(screen)
            pygame.display.flip()
            clock.tick(60)

        # フェードアウト → 本編へ
        fade_out(screen, 600, draw_under=draw)

"""
======================================================================
IntroEvent 用テキスト定義メモ（スクリプトの書き方まとめ）
======================================================================

■ 1. 全体の構造
----------------------------------------------------------------------
INTRO_SCRIPT は、

    INTRO_SCRIPT: List[Page]
    Page        : List[Line]
    Line        : str または dict

という入れ子構造になっています。

    INTRO_SCRIPT = [
        [   # 1ページ目
            { "text": "……冷たい土の感触で、私は目を覚ました。" },
            { "text": "湿った空気の中に、草と土の匂いが混じっている。" },
        ],
        [   # 2ページ目
            { "text": "立ち上がろうとした瞬間、鋭い痛みが全身を走った。" },
            "腕にも足にも、擦り傷や青あざがいくつもある。",
        ],
        # …以下同様
    ]

- Page（[]で囲まれたかたまり）ごとに「ページ送り」されます。
- Line は 1 行分のテキストとその行頭での演出指示です。
- Line が str の場合は「{"text": 文字列}」として扱われます。


■ 2. Line(dict) で使える主なキー一覧
----------------------------------------------------------------------
dict で 1 行を書くと、テキストに加えて各種演出を指定できます。

    {
        "text": "テキスト本文",
        "voice": "voice_intro_001.mp3",
        "bgm": "intro_theme.mp3.enc",
        "bgm_stop": True,
        "bgm_fade_ms": 600,
        "se": "switch_ng.wav",
        "bg": "assets/sprites/intro_forest_bg.png",
        "bg_color": [0, 0, 0],
    }

▼ 必須（に相当する）キー
- text: str
    1 行分の本文テキスト。
    Line が str の場合は自動的に text として扱われます。

▼ サウンド系
- voice: str
    行の先頭で「ボイス」を 1 回だけ再生します。
    - 実際の再生は SoundManager.play_voice() 経由で行われます。
    - パスの解決は SoundManager 側の実装に依存します。

- bgm: str
    行の先頭で BGM を再生開始します。
    - 実際の再生は SoundManager.play_bgm() 経由です。
    - すでに BGM が鳴っている場合は、SoundManager の実装に従って
      切り替え／上書きなどが行われます。

- bgm_stop: bool
    True の場合、「いま鳴っている BGM を停止」します。
    - fade 用に bgm_fade_ms と組み合わせて使います。

- bgm_fade_ms: int
    bgm_stop と併用した場合、指定ミリ秒でフェードアウトします。
    - 例: {"bgm_stop": True, "bgm_fade_ms": 600}

- se: str
    行の先頭で効果音を 1 回だけ再生します。
    - 実際の再生は SoundManager.play_se() 経由です。

▼ 画面演出系
- bg: str
    行の先頭で背景画像を差し替えます。

    例:
        { "text": "耳を疑った。低く、濁った音がどこかで響く。",
          "bg": "assets/sprites/intro_forest_close.png" }

    - 以降の行では、新しい背景が継続して表示されます。
    - 後述の bg_color が有効になっていた場合、
      bg を指定した行で「背景色モード」は解除され、
      再び画像背景モードに戻ります。

- bg_color: List[int] | Tuple[int, int, int]
    画面全体を単色で塗りつぶす「背景色モード」に切り替えます。

    例:
        {
            "text": "…………！！",
            "voice": "ゴブリンの鳴き声3.mp3",
            "bg_color": [0, 0, 0]   # 画面を真っ黒に
        }

    - [R, G, B] 形式で指定します（0–255）。
    - この行の描画以降、bg_color が設定された状態が続き、
      背景は画像ではなく「単色塗りつぶし」になります。
    - 次に bg（背景画像）を指定した行が来ると、
      self.bg_color は None に戻り、通常の背景画像描画に戻ります。


■ 3. 「画面真っ黒 → 画像に戻す」実用例
----------------------------------------------------------------------
今回よく使うパターンの具体例です。

▼ 1) ゴブリンの鳴き声で画面を真っ黒に

    [
        { "text": "見渡す限り、夜の森。", "voice": "voice_intro_009.mp3" },
        { "text": "月明かりが木々の隙間を照らし、霧が地面を這っている。", "voice": "voice_intro_010.mp3" },
        { "text": "風が止み、世界が静止したように感じた、そのとき——", "voice": "voice_intro_011.mp3" }
    ],
    [
        {
            "text": "…………！！",
            "voice": "ゴブリンの鳴き声3.mp3",
            "bg_color": [0, 0, 0]   # ここで画面を真っ黒に
        },
    ],

▼ 2) その後の行で別の背景画像に戻す

    [
        { "text": "ここに留まってはいけない……そんな予感がした。", "voice": "voice_intro_016.mp3" },
        {
            "text": "ふらつきながらも、私は歩き出した。",
            "voice": "voice_intro_017.mp3",
            "bg": "assets/sprites/intro_forest_path.png"  # 新しい背景画像に切り替え
        },
        { "text": "どこへ向かうのかもわからないまま、足を前へと進める。", "voice": "voice_intro_018.mp3" },
        { "text": "止まってしまえば、二度と朝を迎えられない気がして……。", "voice": "voice_intro_019.mp3" }
    ]

- これで「一瞬だけ画面を真っ黒 → その後、別カットの背景画像に戻る」
  という流れを自然に表現できます。
- bg_color は黒以外でも指定可能なので、
  暗めの赤フラッシュなども表現できます。

    例:
        {
            "text": "警告音が頭の中で鳴り響いた。",
            "voice": "voice_alert.mp3",
            "bg_color": [160, 0, 0]   # 暗い赤でフラッシュ
        }


■ 4. プレイヤー操作（キー操作）の簡単なメモ
----------------------------------------------------------------------
IntroEventScene.run() 中では、ざっくり次のような操作ができます。

- Enter
    - 文字送り（1 行の途中 → 全文表示 → 次の行 → 次のページ）
    - ページ末では「次のページへ進む」動作になります。

- A キー
    - オートモードの ON / OFF 切り替え。
    - ON のときは、行末およびページ末で自動的に待ち時間をはさんで
      次へ進みます（auto_line_delay_ms / auto_page_delay_ms）。

- S キー
    - スキップモードの ON / OFF 切り替え。
    - ON にすると、テキストを一気に終端まで進めます。
    - 途中で S を押して OFF に戻すと、そこで通常モードに復帰します。
    - スキップ中はサウンドを鳴らさずに進める実装になっています。

このファイルのテキスト定義部分を書き換えるときは、

    1) INTRO_SCRIPT の構造（ページの配列 → 行の配列）
    2) 上記のキーで必要な演出だけを行に足していく
    3) 背景画像（bg）と背景色（bg_color）の優先順位
       - bg_color が有効な間は単色塗り
       - bg を指定した行で画像に復帰

というポイントを意識しておくと、安全に拡張できます。
"""
