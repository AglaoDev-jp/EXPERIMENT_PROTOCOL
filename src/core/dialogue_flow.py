# core/dialogue_flow.py
# -*- coding: utf-8 -*-
"""
イベントシーン共通の“読み進め制御（オート/スキップ/タイプ速度）”モジュール

設計方針：
- Scene側は「現在の行が全部出たか」「ページ末か」などの状態だけ提供。
- 本モジュールがユーザー入力＆時間経過を解釈して「進め/全表示/次ページ/終了」を返す。
- どのシーンでも同じインターフェースで使える（モジュール注入）。
"""

from __future__ import annotations
from dataclasses import dataclass

# ---- キーバインド（pygameのキーコードに依存しない“論理名”） ----
# 具体的な pygame.KEYDOWN の値はシーン側で判定し、下記に変換して渡すと疎結合になる。
KEY_NEXT = "NEXT"       # Enter / Space / 左クリック
KEY_SKIP_TOGGLE = "SKIP_TOGGLE"   # Ctrl or S など任意
KEY_AUTO_TOGGLE = "AUTO_TOGGLE"   # A など任意
KEY_FAST_HELD = "FAST_HELD"       # Ctrl を押し続けるなど
KEY_SKIP_ALL = "SKIP_ALL"         # Esc→確認後のスキップ確定 など

@dataclass
class DialogueConfig:
    # タイピング速度
    type_ms_per_char: int = 22
    # 句読点ポーズ（日本語向け）
    punct_pause_ms: dict[str, int] = None
    # オートモード関連
    auto_enabled_default: bool = False
    auto_line_delay_ms: int = 700     # 行が出終わってから次行に進むまでの待機
    auto_page_delay_ms: int = 900     # ページ末の待機
    # スキップ関連
    fast_multiplier: float = 0.33     # FAST_HELD中は表示間隔をこれ倍に（小さいほど速い）
    skip_toggle_sticky: bool = True   # True: トグル式 / False: 長押しのみ

    def __post_init__(self):
        if self.punct_pause_ms is None:
            self.punct_pause_ms = {
                "。": 120, "、": 80, "，": 80, ",": 80, ".": 100,
                "！": 120, "!": 120, "？": 130, "?": 130,
                "…": 120, "―": 100, "—": 100, "」": 80,
            }

@dataclass
class DialogueState:
    # ランタイム状態
    is_auto: bool = False
    is_skip: bool = False          # トグルスキップ（即表示＆自動進行）
    fast_held: bool = False        # 一時的な高速（押している間だけ速く）
    # 時刻管理（ms）
    next_tick_ms: int = 0          # 次の1文字が出る時刻
    auto_wait_until_ms: int = 0    # 次の自動進行の時刻

class DialogueController:
    """
    シーンからは以下を呼ぶ：
      - on_key(action_name) : キー入力を通知
      - plan_next_char(now_ms, is_line_done, last_char) : 次の文字までの待機を決める
      - request_advance(now_ms, is_line_done, is_page_end, is_script_end) : ユーザ入力/自動進行の結果として進行アクションを返す

    戻り値（アクション）：
      - "REVEAL_LINE"  : 現在行を即時全表示
      - "NEXT_LINE"    : 行送り
      - "NEXT_PAGE"    : ページ送り
      - "END_SCENE"    : シーン終了
      - None           : 何もしない
    """
    def __init__(self, cfg: DialogueConfig):
        self.cfg = cfg
        self.st = DialogueState(is_auto=cfg.auto_enabled_default)

    # ---- 入力処理 ----
    def on_key(self, action_name: str, pressed: bool = True):
        if action_name == KEY_AUTO_TOGGLE and pressed:
            self.st.is_auto = not self.st.is_auto
        elif action_name == KEY_SKIP_TOGGLE and pressed and self.cfg.skip_toggle_sticky:
            self.st.is_skip = not self.st.is_skip
        elif action_name == KEY_FAST_HELD:
            self.st.fast_held = pressed
        elif action_name == KEY_SKIP_ALL and pressed:
            # “全部スキップ”はシーン側で確認ダイアログを出してから呼んでください
            self.st.is_skip = True

    # ---- タイプ速度計画 ----
    def plan_next_char(self, now_ms: int, is_line_done: bool, last_char: str | None) -> int:
        """
        次の文字が出る時刻(ms)を返す。line_done ならそのまま now_ms。
        """
        if is_line_done:
            return now_ms  # 行が終わっているなら即時（次の進行判断は request_advance 側）

        base = self.cfg.type_ms_per_char
        # スキップ時は最速、FASTは倍率で加速
        if self.st.is_skip:
            base = 0
        elif self.st.fast_held:
            base = int(base * self.cfg.fast_multiplier)

        pause = 0
        if last_char:
            pause = self.cfg.punct_pause_ms.get(last_char, 0)

        return now_ms + max(0, base + pause)

    # ---- 進行アクション決定 ----
    def request_advance(self, now_ms: int, is_line_done: bool, is_page_end: bool, is_script_end: bool, next_request: bool) -> str | None:
        """
        next_request: ユーザーの“進め”入力があったか（Enter/Space/Click）
        """
        # スキップONなら：行→ページ→終了まで自動で一直線
        if self.st.is_skip:
            if not is_line_done:
                return "REVEAL_LINE"
            if not is_page_end:
                return "NEXT_LINE"
            if not is_script_end:
                return "NEXT_PAGE"
            return "END_SCENE"

        # 手動入力があった場合
        if next_request:
            if not is_line_done:
                return "REVEAL_LINE"
            if not is_page_end:
                return "NEXT_LINE"
            if not is_script_end:
                return "NEXT_PAGE"
            return "END_SCENE"

        # オートモード
        if self.st.is_auto:
            # auto_wait_until_ms を超えたら進める
            if self.st.auto_wait_until_ms and now_ms >= self.st.auto_wait_until_ms:
                if not is_page_end:
                    self.st.auto_wait_until_ms = 0
                    return "NEXT_LINE"
                if not is_script_end:
                    self.st.auto_wait_until_ms = 0
                    return "NEXT_PAGE"
                return "END_SCENE"
        return None

    def arm_auto_wait(self, now_ms: int, is_page_end: bool):
        """
        行やページを“出し切った直後”に呼び出し、次の自動進行時刻を予約する。
        """
        if not self.st.is_auto or self.st.is_skip:
            self.st.auto_wait_until_ms = 0
            return
        delay = self.cfg.auto_page_delay_ms if is_page_end else self.cfg.auto_line_delay_ms
        self.st.auto_wait_until_ms = now_ms + max(0, delay)
