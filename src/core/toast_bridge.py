# core/toast_bridge.py
# -*- coding: utf-8 -*-
"""
トースト表示の集約モジュール（Façade）
- どの場面でも「ここだけ」経由でトーストを出すことで迷子をなくす
- save_system._toast() のフォールバックキュー(__toast_queue)も毎フレーム吸い上げてUIへ流す
- マップ定義の prompt / solved_toast といった“文言由来”の表示もここに統一

使い方の基本ルール：
1) 起動直後・シーン切替直後・ロード直前に bind_toast(...) を必ず呼ぶ
2) 画面ループ毎フレームで drain_queue() を呼ぶ（MenuScene でも！）
3) 表示は show(...) を経由（ms 指定で表示時間も都度調整可能）
4) マップ由来の文言は show_trigger_prompt(...) / show_puzzle_solved(...) などを使用
"""

from __future__ import annotations
from typing import Optional, Dict, Any
import core.game_state as gs

# ------------------------------------------------------------
# 1) UIトーストとの橋渡し（起動直後/シーン切替直後/ロード前などで必ず呼ぶ）
# ------------------------------------------------------------
def bind_toast(toast_manager) -> None:
    """
    save_system.py や他モジュールが参照する gs.toast を、最新の UI ToastManager に更新する。
    """
    gs.toast = toast_manager

# ------------------------------------------------------------
# 2) 表示API（これだけ使えばOK）: 呼び出し毎に表示時間を変えられる
# ------------------------------------------------------------
def show(msg: str, ms: Optional[int] = None) -> None:
    """
    トーストを表示する“唯一の入り口”。
    - UI（gs.toast）があれば UI に出す
    - UI未接続でも __toast_queue に積む（次フレームの drain_queue() で必ず表示へ流れる）
    - ms: 個別の表示時間（ミリ秒・Noneなら ToastManager のデフォルト）
    """
    try:
        t = getattr(gs, "toast", None)
        if t and hasattr(t, "show"):
            t.show(str(msg), ms=ms)  # UI へ（ToastManager.show(msg, ms=None)想定）
            return
    except Exception:
        pass

    # UIが無い/描画前でも、フォールバック・キューに積んでおく
    try:
        if not hasattr(gs, "state") or not isinstance(gs.state, dict):
            gs.state = {}
        q = gs.state.setdefault("__toast_queue", [])
        q.append(str(msg))
    except Exception:
        pass

    # 最後の保険（ログ確認用）
    print(str(msg))

# ------------------------------------------------------------
# 3) フォールバック・キューのドレイン（毎フレーム1回必ず呼ぶ！）
# ------------------------------------------------------------
def drain_queue() -> None:
    """
    save_system._toast() 等が __toast_queue に積んだ文言を UI に流す。
    MenuScene のような“別ループ”でも取りこぼしが出ないよう、各シーンで毎フレーム呼ぶこと。
    """
    try:
        st = getattr(gs, "state", {})
        if not isinstance(st, dict):
            return
        q = st.get("__toast_queue", [])
        if not q:
            return
        t = getattr(gs, "toast", None)
        while q:
            m = q.pop(0)
            if t and hasattr(t, "show"):
                t.show(str(m))
            else:
                print(str(m))
    except Exception:
        pass

# ------------------------------------------------------------
# 4) マップ定義（prompt / solved_toast）由来の表示を統一
# ------------------------------------------------------------
def show_trigger_prompt(trigger_def: Dict[str, Any], default_ms: int = 2500) -> None:
    """
    MAPS['xxx']['triggers'][i]['prompt'] を表示（存在すれば）
    """
    msg = (trigger_def or {}).get("prompt")
    if msg:
        show(str(msg), ms=default_ms)

def show_puzzle_solved(map_id: str, default_ms: int = 2500) -> None:
    """
    MAPS[map_id]['puzzle']['solved_toast'] を表示（存在すれば）
    """
    try:
        from core.maps import MAPS  # 遅延importで循環回避
        solved = ((MAPS.get(map_id, {}) or {}).get("puzzle", {}) or {}).get("solved_toast")
        if solved:
            show(str(solved), ms=default_ms)
    except Exception:
        pass

def show_footrev_solved(map_id: str, default_ms: int = 2500) -> None:
    """
    MAPS[map_id]['footrev']['on_solve_toast'] を表示（存在すれば）
    """
    try:
        from core.maps import MAPS
        solved = ((MAPS.get(map_id, {}) or {}).get("footrev", {}) or {}).get("on_solve_toast")
        if solved:
            show(str(solved), ms=default_ms)
    except Exception:
        pass
