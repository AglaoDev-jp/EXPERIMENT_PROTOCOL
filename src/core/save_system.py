# core/save_system.py
# -*- coding: utf-8 -*-
"""
セーブ／ロード中核モジュール（JSON保存）
- スロット制（slot1/slot2/slot3）
- アトミックライト（.tmp → 置換、.bak 退避）
- セーブバージョン（将来の互換性準備）
- 保存対象：プレイヤー座標/向き、現在マップ、インベントリ、進行フラグ、プレイ時間 等

【重要方針】
- FLAGS は型を固定（set/list/dict）。JSON→ランタイムで tuple 正規化も行う。
- gs.state は永続化しない。ロード後に puzzles_progress から点滅/途中進行を再構築。
- 「X壁の復元」と「スイッチ見た目（未点灯↔*_lit）」は“原本ベースライン”から**参照付け替えのみ**で実施。
- メニュー経由のロードでも一度だけ再構築が走るよう、apply_snapshot() 内でフック。
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Tuple, Set, Optional
from datetime import datetime
import json
import os
import sys
import time
import math
from copy import deepcopy

import core.game_state as gs
from core.maps import MAPS

# =========================
# 基本設定
# =========================
GAME_NAME = "RayHorror"
SAVE_VERSION = 1
SAVE_SLOTS = ("slot1", "slot2", "slot3")

ALIASES = {
    "quick": "slot1",
    "quick1": "slot1",
    "quick_save": "slot1",
}

def _normalize_slot(s: str) -> str:
    if not s:
        return "slot1"
    s = s.lower()
    return ALIASES.get(s, s)


# =========================
# 保存先ディレクトリ
# =========================
def is_frozen_build() -> bool:
    """PyInstaller 実行形態か？"""
    return getattr(sys, "frozen", False)

def _primary_save_dir() -> Path:
    """【最優先】保存先＝スクリプト/実行ファイルと同じディレクトリ。"""
    if is_frozen_build():
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(sys.argv[0]).resolve().parent
    return base

def _fallback_save_dir() -> Path:
    """書込不可時のフォールバック（ユーザホーム配下）。"""
    return Path.home() / f"{GAME_NAME}_fallback_saves"

def get_save_root_dir() -> Path:
    primary = _primary_save_dir()
    try:
        primary.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    # 簡易書込テスト
    try:
        t = primary / ".write_test.tmp"
        with t.open("w", encoding="utf-8") as f:
            f.write("ok")
        t.unlink(missing_ok=True)
        return primary
    except Exception:
        fb = _fallback_save_dir()
        fb.mkdir(parents=True, exist_ok=True)
        return fb

def slot_path(slot: str) -> Path:
    slot = _normalize_slot(slot)
    return get_save_root_dir() / f"{slot}.json"


# =========================
# 表示（なければ print）
# =========================
def _toast(msg: str, *, ms: Optional[int] = None) -> None:
    """
    UIトーストに届く場合は、呼び出し毎の表示時間(ms)を指定して表示。
    届かない場合はフォールバックで gs.state['__toast_queue'] に積んで、次フレームでUIへ。
    """
    try:
        t = getattr(gs, "toast", None)
        if t and hasattr(t, "show"):
            try:
                # ToastManager.show(msg, ms=None) を想定
                t.show(str(msg), ms=ms)
                return
            except TypeError:
                # 互換保険: ms 引数が無い古い Toast 実装でも落とさない
                t.show(str(msg))
                return
    except Exception:
        pass

    # --- フォールバック：ゲームループ側で必ず拾えるように ---
    try:
        if not hasattr(gs, "state") or not isinstance(gs.state, dict):
            gs.state = {}
        q = gs.state.setdefault("__toast_queue", [])
        q.append(str(msg))
    except Exception:
        pass

    # デバッグ保険
    print(str(msg))

# =========================
# ユーティリティ（型/数値）
# =========================
def _safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default)

def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default

def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        return 0.0 if (math.isnan(x) or math.isinf(x)) else x
    except Exception:
        return default

# =========================
# FLAGS ベースライン（型固定）
# =========================
def _reset_flags_baseline() -> None:
    if not hasattr(gs, "FLAGS") or not isinstance(gs.FLAGS, dict):
        gs.FLAGS = {}
    gs.FLAGS["doors_opened"]      = set()
    gs.FLAGS["switches_pressed"]  = set()
    gs.FLAGS["puzzles_solved"]    = []      # ★ list[tuple] で保持
    gs.FLAGS["picked_items"]      = set()
    gs.FLAGS["chests_looted"]     = set()
    gs.FLAGS["trees_chopped"]     = set()
    gs.FLAGS["visited_maps"]      = set()
    gs.FLAGS["fog_cleared"]       = set()
    gs.FLAGS["videos_played"]     = set()
    gs.FLAGS["puzzles_progress"]  = {}      # ★ dict[str, list[str]]
    gs.FLAGS["triggers_fired"]    = set() # ★近接トリガ（動画/追跡者/エンディング等）の発火済みIDも毎回リセット


# =========================
# 抽出/適用（プレイヤー/マップ/所持品/フラグ/時間）
# =========================
def extract_player_state() -> Dict[str, Any]:
    x = _safe_getattr(gs, "player_x", None)
    y = _safe_getattr(gs, "player_y", None)
    a = _safe_getattr(gs, "player_angle", None)
    if x is None and hasattr(gs, "PLAYER") and isinstance(gs.PLAYER, dict):
        x = gs.PLAYER.get("x")
        y = gs.PLAYER.get("y")
        a = gs.PLAYER.get("angle")
    return {"x": _to_float(x, 1.5), "y": _to_float(y, 1.5), "angle": _to_float(a, 0.0)}

def apply_player_state(data: Dict[str, Any]) -> None:
    x = _to_float(data.get("x", 1.5))
    y = _to_float(data.get("y", 1.5))
    a = _to_float(data.get("angle", 0.0))
    if hasattr(gs, "player_x"): gs.player_x = x
    if hasattr(gs, "player_y"): gs.player_y = y
    if hasattr(gs, "player_angle"): gs.player_angle = a
    if hasattr(gs, "PLAYER") and isinstance(gs.PLAYER, dict):
        gs.PLAYER["x"] = x; gs.PLAYER["y"] = y; gs.PLAYER["angle"] = a

def extract_current_map_id() -> str:
    m = _safe_getattr(gs, "current_map_id", None)
    if m is None and hasattr(gs, "WORLD") and isinstance(gs.WORLD, dict):
        m = gs.WORLD.get("map_id")
    return m or "forest_1"

def apply_current_map_id(map_id: str) -> None:
    if hasattr(gs, "set_map"):
        try:
            gs.set_map(map_id)
            return
        except Exception:
            pass
    if hasattr(gs, "current_map_id"):
        gs.current_map_id = map_id

def extract_inventory() -> Dict[str, int]:
    inv = _safe_getattr(gs, "INVENTORY", None)
    if inv is None:
        inv = _safe_getattr(gs, "inventory", {})
    out: Dict[str, int] = {}
    if isinstance(inv, dict):
        for k, v in inv.items():
            out[str(k)] = _to_int(v, 1)
    return out

def apply_inventory(inv: Dict[str, int]) -> None:
    target: Dict[str, int] = {}
    for k, v in (inv or {}).items():
        target[str(k)] = _to_int(v, 1)
    if hasattr(gs, "INVENTORY"):
        gs.INVENTORY.clear(); gs.INVENTORY.update(target)
    elif hasattr(gs, "inventory"):
        gs.inventory.clear(); gs.inventory.update(target)

def extract_event_flags() -> Dict[str, List]:
    """set/tuple → list へ変換しつつ抽出。puzzles_progress は dict をそのまま（値は list）。"""
    out: Dict[str, List] = {}
    for name in [
        "doors_opened", "switches_pressed", "puzzles_solved",
        "picked_items", "chests_looted", "trees_chopped",
        "visited_maps", "fog_cleared", "videos_played",
    ]:
        # ★重要：永続進行は必ず FLAGS を真実のソースとする（ランタイム属性より優先）
        val = None
        if hasattr(gs, "FLAGS") and isinstance(gs.FLAGS, dict):
            val = gs.FLAGS.get(name)
        if val is None:
            # 互換のため、最後にランタイム属性を見る（ある場合のみ）
            val = _safe_getattr(gs, name, None)
        if val is not None:
            if isinstance(val, (set, tuple)):
                out[name] = list(val)
            elif isinstance(val, list):
                out[name] = val[:]
    pp = None
    if hasattr(gs, "FLAGS") and isinstance(gs.FLAGS, dict):
        pp = gs.FLAGS.get("puzzles_progress")
    if isinstance(pp, dict):
        out["puzzles_progress"] = {str(k): list(v) for k, v in pp.items()}
    return out

def apply_event_flags(flags: Dict[str, List]) -> None:
    """
    進行フラグ適用。JSON で崩れた tuple を復元し、FLAGS の型へ合わせる。
    - puzzles_solved は最終的に list[tuple] として扱いやすくしておく。
    """
    if not flags:
        return

    if not hasattr(gs, "FLAGS") or not isinstance(gs.FLAGS, dict):
        gs.FLAGS = {}

    def _tuple_normalize(seq: List) -> List:
        out = []
        for e in (seq or []):
            if isinstance(e, (list, tuple)):
                try:
                    out.append(tuple(e))
                except Exception:
                    out.append(e)
            else:
                out.append(e)
        return out

    for k, v in (flags or {}).items():
        needs_tuple = k in {"doors_opened", "trees_chopped", "puzzles_solved", "picked_items", "videos_played"}
        vv = _tuple_normalize(v) if needs_tuple else (v or [])
        is_set_expected = isinstance(gs.FLAGS.get(k), set)
        try:
            gs.FLAGS[k] = set(vv) if is_set_expected else list(vv)
        except TypeError:
            vv_norm = _tuple_normalize(vv)
            gs.FLAGS[k] = set(vv_norm) if is_set_expected else list(vv_norm)

    # 個別属性としても持っている場合を同期
    for k, v in (flags or {}).items():
        if hasattr(gs, k):
            cur = getattr(gs, k)
            needs_tuple = k in {"doors_opened","trees_chopped","puzzles_solved","picked_items","videos_played"}
            vv = _tuple_normalize(v) if needs_tuple else (v or [])
            try:
                setattr(gs, k, set(vv) if isinstance(cur, set) else list(vv))
            except Exception:
                setattr(gs, k, list(vv))

    # puzzles_solved は list[tuple] に矯正
    ps = flags.get("puzzles_solved")
    if isinstance(ps, (list, set)):
        gs.FLAGS["puzzles_solved"] = [tuple(x) for x in list(ps)]
    else:
        gs.FLAGS["puzzles_solved"] = []

    # puzzles_progress は dict[str, list[str]]
    pp = flags.get("puzzles_progress")
    if isinstance(pp, dict):
        gs.FLAGS["puzzles_progress"] = {str(k): list(v or []) for k, v in pp.items()}
    else:
        gs.FLAGS["puzzles_progress"] = {}


# =========================
# 原本ベースライン
# =========================
_LAYOUT_BASELINES: Dict[str, List[str]] = {}     # map_id -> layout 原本行配列
_SPECIAL_BASELINES: Dict[str, Dict[str, dict]] = {}  # map_id -> special 原本（dictのみ）

def _ensure_layout_baseline(map_id: str) -> None:
    """MAPS[map_id]['_layout_base'] があれば優先、無ければ現行 layout を原本として保存（毎回上書き）。"""
    try:
        from core.maps import MAPS
        if not map_id or map_id not in MAPS:
            return
        mp = MAPS[map_id]
        base_rows = mp.get("_layout_base") or mp.get("layout") or []
        _LAYOUT_BASELINES[map_id] = [row[:] for row in base_rows]
    except Exception:
        pass

def remember_special_baseline_for_map(map_id: str) -> None:
    """
    現ロード済み textures.special を“未点灯ベースライン”として保持（dict かつ 'arr' のみ）。
    冪等・何度呼んでも上書き。
    """
    try:
        ct = getattr(gs, "current_textures", None)
        if not isinstance(ct, dict):
            return
        spec = ct.get("special") or {}
        baseline: Dict[str, dict] = {}
        if isinstance(spec, dict):
            for k, v in spec.items():
                if isinstance(v, dict) and "arr" in v:
                    baseline[k] = deepcopy(v)
        _SPECIAL_BASELINES[map_id] = baseline
    except Exception:
        pass

def _get_current_puzzle_id(map_id: str) -> str:
    """マップから現在のパズルIDを動的取得（無ければ 'switch_A'）。"""
    try:
        from core.maps import MAPS
        mp = MAPS.get(map_id, {})
        pid = ((mp.get("puzzle") or {}).get("id")) or "switch_A"
        return str(pid)
    except Exception:
        return "switch_A"


# =========================
# ランタイム状態（非永続）の再構築
# =========================
def _reset_runtime_visuals_after_load() -> None:
    """ロード直後、ランタイム表示用 state をクリア（残留防止）。"""
    if not hasattr(gs, "state") or not isinstance(gs.state, dict):
        gs.state = {}
    st = gs.state
    for k in ("switch_blink_active", "switch_progress", "switch_solved", "switch_applied"):
        st.pop(k, None)

def _rehydrate_switch_visuals_from_flags() -> None:
    """
    FLAGS['puzzles_progress'] → state['switch_progress'/'switch_blink_active'] を復元。
    解決済みなら消灯。
    """
    if not hasattr(gs, "state") or not isinstance(gs.state, dict):
        gs.state = {}
    st = gs.state
    f  = getattr(gs, "FLAGS", {})

    cur_map_id = getattr(gs, "current_map_id", "")
    pid = _get_current_puzzle_id(cur_map_id)
    if not pid:
        return

    solved_pairs = {tuple(x) for x in (f.get("puzzles_solved", []) or [])}
    if (cur_map_id, pid) in solved_pairs:
        st["switch_progress"] = []
        st["switch_blink_active"] = set()
        st["switch_solved"] = True
        st["switch_applied"] = True
        return

    pp = f.get("puzzles_progress") or {}
    seq: List[str] = list(pp.get(f"{cur_map_id}:{pid}", []))
    st["switch_progress"] = seq
    st["switch_blink_active"] = set(seq)
    st["switch_solved"] = False
    st["switch_applied"] = False


# =========================
# レイアウト/X壁 再構成
# =========================
def _rebuild_barriers_from_flags(map_id: str) -> None:
    """
    1) 原本レイアウトへ完全復元 → 2) 解決済みなら opens/unlock_barriers を '.' に。
    """
    try:
        from core.maps import MAPS
        if not map_id or map_id not in MAPS:
            return

        # 原本を都度同期（“開放残留”を絶対に持ち越さない）
        _ensure_layout_baseline(map_id)
        mp = MAPS[map_id]
        base = _LAYOUT_BASELINES.get(map_id, [])  # List[str]
        mp["layout"] = [row[:] for row in base]   # 完全復元

        # クリア判定
        pid = _get_current_puzzle_id(map_id)
        solved = {tuple(x) for x in (getattr(gs, "FLAGS", {}).get("puzzles_solved", []) or [])}
        if (map_id, pid) not in solved:
            return  # 未解決なら原本のまま

        # 開放座標を '.' に
        puzzle = (mp.get("puzzle") or {})
        opens = (puzzle.get("opens") or []) + (puzzle.get("unlock_barriers") or [])
        new_rows: List[str] = []
        for y, row in enumerate(mp["layout"]):
            rlist = list(row)
            for (tx, ty) in opens:
                if ty == y and 0 <= tx < len(rlist):
                    rlist[tx] = '.'
            new_rows.append("".join(rlist))
        mp["layout"] = new_rows
    except Exception:
        return
    
# =========================
# ドア開放の最終適用（doors_opened）
# =========================
def _apply_doors_opened_from_flags(map_id: str) -> None:
    """
    FLAGS['doors_opened'] に記録された座標を、現在のレイアウトへ反映して
    'D'（または壁）を walkable な '.' に置換する。
    - セーブ時には (map_id, x, y) のタプルを保存している想定。
    - JSON→ランタイムで list→tuple の正規化は apply_event_flags() が実施済み。
    """
    try:
        from core.maps import MAPS
        if not map_id or map_id not in MAPS:
            return
        opened = getattr(gs, "FLAGS", {}).get("doors_opened", set()) or set()
        # list の混入に備えてタプル化（安全側）
        opened = {tuple(e) for e in opened}
        # 対象マップの座標だけを抽出
        targets = {(tx, ty) for (mid, tx, ty) in opened if mid == map_id}
        if not targets:
            return

        mp = MAPS[map_id]
        rows = mp.get("layout") or []
        if not rows:
            return

        # 行ごとに文字列をリスト化 → 対象座標を '.' に置換 → 連結
        h = len(rows)
        w = len(rows[0]) if h > 0 else 0
        new_rows = []
        for y, row in enumerate(rows):
            rlist = list(row)
            for (tx, ty) in targets:
                if ty == y and 0 <= tx < w:
                    rlist[tx] = '.'  # ★ ドア（または壁）を「通行可能」に固定する
            new_rows.append("".join(rlist))
        mp["layout"] = new_rows
    except Exception:
        # ロード処理を止めないために握りつぶし（ログのみでも可）
        return
    
# =========================
# 霧の最終適用
# =========================
def _apply_fog_from_flags(map_id: str) -> None:
    """
    霧フラグ（FLAGS['fog_cleared']）に基づき、現在レイアウトから霧タイルを除去する。
    - セーブ適用の最終段（X↔'.' 再構成の後）で呼ぶことにより、
      “原本への巻き戻しで霧が復活する”現象を防ぐ。
    - 置換対象: 'F' / 'f' → '.'
    - もし霧解除と同時に守護者なども消す仕様なら、'M' → '.' の行を有効化してください。
    """
    try:
        from core.maps import MAPS
        if not map_id or map_id not in MAPS:
            return
        flags = getattr(gs, "FLAGS", {}) or {}
        cleared = flags.get("fog_cleared") or set()
        # fog_cleared は set が想定（apply_event_flags で型整備済み）
        if map_id not in cleared:
            return

        mp = MAPS[map_id]
        rows = mp.get("layout") or []
        new_rows = []
        for row in rows:
            r = row.replace('F', '.').replace('f', '.')
            # 守護者も同時に消す仕様なら下行のコメントを外す:
            # r = r.replace('M', '.')
            new_rows.append(r)
        mp["layout"] = new_rows
    except Exception:
        # 霧適用で落ちないようにガード
        return

# 推定で fog フラグを補完
def _infer_and_fix_fog_flag_for_current_map() -> None:
    """
    現行レイアウトと原本(_layout_base)の差から、fog_cleared の抜け落ちを補完する。
    - 原本に 'F'/'f' があり、現行には無い → fog_cleared に現在マップIDを追加
    """
    try:
        from core.maps import MAPS
        mid = getattr(gs, "current_map_id", "")
        if not mid or mid not in MAPS:
            return
        mp = MAPS[mid]
        base_rows = mp.get("_layout_base") or mp.get("layout") or []
        cur_rows  = mp.get("layout") or []

        base_has_fog = any(('F' in r) or ('f' in r) for r in base_rows)
        cur_has_fog  = any(('F' in r) or ('f' in r) for r in cur_rows)

        if base_has_fog and not cur_has_fog:
            flags = getattr(gs, "FLAGS", None)
            if not isinstance(flags, dict):
                gs.FLAGS = {}
                flags = gs.FLAGS
            s = flags.setdefault("fog_cleared", set())
            if isinstance(s, set):
                s.add(mid)
            else:
                # 型が崩れていた場合も救済
                flags["fog_cleared"] = set(list(s) if isinstance(s, list) else []) | {mid}
    except Exception:
        pass

# =========================
# スイッチ見た目（未点灯↔*_lit）再構成
# =========================
def _apply_switch_lit_from_flags(map_id: str) -> None:
    """
    未解決→ 未点灯へ戻す。解決済→ *_lit の参照に差し替え。
    固定キー（a/b/c/d）前提をやめ、special 内の「*_lit」ペアを自動検出。
    """
    try:
        ct = getattr(gs, "current_textures", None)
        if not isinstance(ct, dict):
            return
        spec: Dict[str, Any] = ct.get("special") or {}
        base_rt = _SPECIAL_BASELINES.get(map_id, {})

        pid = _get_current_puzzle_id(map_id)
        solved = {tuple(x) for x in (getattr(gs, "FLAGS", {}).get("puzzles_solved", []) or [])}
        is_cleared = (map_id, pid) in solved

        # 「*_lit」ペアのベース名を動的抽出
        bases: Set[str] = set()
        if isinstance(spec, dict):
            for k in spec.keys():
                if isinstance(k, str):
                    if k.endswith("_lit") and len(k) > 4:
                        bases.add(k[:-4])
                    elif (k + "_lit") in spec:
                        bases.add(k)
        if isinstance(base_rt, dict):
            for k in base_rt.keys():
                if k.endswith("_lit") and len(k) > 4:
                    bases.add(k[:-4])
                elif (k + "_lit") in base_rt:
                    bases.add(k)

        # ベースごとに参照付け替え（画像再ロード禁止）
        for base in bases:
            target_key = f"{base}_lit" if is_cleared else base
            src = spec.get(target_key)
            if not (isinstance(src, dict) and "arr" in src):
                src = base_rt.get(target_key) or base_rt.get(base)
            if isinstance(src, dict) and "arr" in src:
                spec[base] = src
        ct["special"] = spec
    except Exception:
        return


# =========================
# スナップショット生成/適用
# =========================
def extract_playtime_sec() -> int:
    return _to_int(_safe_getattr(gs, "playtime_sec", 0), 0)

def apply_playtime_sec(sec: int) -> None:
    if hasattr(gs, "playtime_sec"):
        gs.playtime_sec = _to_int(sec, 0)

def build_snapshot(meta_comment: Optional[str] = None) -> Dict[str, Any]:
    return {
        "version": SAVE_VERSION,
        "saved_at": int(time.time()),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "comment": meta_comment or "",
        "map": {"id": extract_current_map_id()},
        "player": extract_player_state(),
        "inventory": extract_inventory(),
        "flags": extract_event_flags(),
        "systems": {"playtime_sec": extract_playtime_sec()},
    }

def apply_snapshot(snap: dict) -> None:
    """
    適用順序（厳守）：
      0) FLAGSのベース初期化（型固定）
      1) 進行フラグ適用（list⇄set/tuple 正規化）
      2) マップ切替（可能なら force_reload）
      3) プレイヤー座標・向き
      4) インベントリ
      5) システム（playtime_sec）
      6) ランタイム表示の一時状態クリア（state のスイッチ関連を消す）
      7) puzzles_progress → 点滅/途中進行の再構築（stateへ）
      8) 壁(X↔'.')の再構成（原本から復元→解決済みだけ '.'）
      9) special の見た目適用（未解決=未点灯 / 解決済=*_lit 参照）
    """
    if not isinstance(snap, dict):
        raise ValueError("Invalid snapshot")

    # 0) FLAGS 初期化
    _reset_flags_baseline()

    # 0.5) ドア開閉のランタイムキャッシュをクリア
    #      - セーブデータに含まれない opened_doors が残っていると、
    #        「セーブ前のプレイで一度開けたドア」がロード後も開いている扱いになり、
    #        実際には閉じているのに『ここは既に開いている。』と表示されてしまうため。
    try:
        if hasattr(gs, "opened_doors"):
            gs.opened_doors.clear()  # type: ignore[attr-defined]
    except Exception:
        pass
    
    # 1) 進行フラグ適用
    flags = snap.get("flags", {}) or {}
    apply_event_flags(flags)

    # 2) マップ切替（可能なら force_reload）
    map_id = snap.get("map", {}).get("id") or getattr(gs, "current_map_id", "")
    if hasattr(gs, "set_map") and map_id:
        try:
            gs.set_map(map_id, force_reload=True)  # type: ignore[arg-type]
        except TypeError:
            gs.set_map(map_id)  # type: ignore[arg-type]

    # --- アセット再構築（霧/守人/スイッチ見た目 等を含む）を強制的に呼ぶ ---
    # 1) まず従来どおり game_state 経由（互換）
    called = False
    try:
        if hasattr(gs, "load_current_map_assets"):
            gs.load_current_map_assets()
            called = True
    except Exception:
        pass

    # 2) タイトル直行ロード対策: __main__ / main から関数を探して呼ぶ
    if not called:
        try:
            import sys
            loader = None
            m = sys.modules.get("__main__")
            if m and hasattr(m, "load_current_map_assets"):
                loader = getattr(m, "load_current_map_assets")
            else:
                # 直接 main を import（循環を避けるため try/except）
                import main as _main
                if hasattr(_main, "load_current_map_assets"):
                    loader = getattr(_main, "load_current_map_assets")
            if callable(loader):
                loader()  # ← ここで _apply_fog_state_for_map まで一式が走る
                called = True
        except Exception:
            pass

    # 3) それでも呼べなかった場合の“最後の保険”として霧だけ同期
    if not called:
        try:
            # クリア済みなら 'F'/'f' を '.' に置換（layout のみ）
            from core.maps import MAPS
            mid = getattr(gs, "current_map_id", "") or map_id
            if mid and mid in MAPS:
                cur_map = MAPS[mid]
                cleared = getattr(gs, "FLAGS", {}).get("fog_cleared", set()) or set()
                if mid in cleared:
                    cur_map["layout"] = [
                        (row.replace('F', '.').replace('f', '.')) for row in cur_map.get("layout", [])
                    ]
        except Exception:
            pass

    # ★ ここで “霧フラグの推定補完” を一度だけ（最終的な並び替えの前に）
    _infer_and_fix_fog_flag_for_current_map()

    # 3〜5) プレイヤー/インベントリ/システム
    pl = snap.get("player", {}) or {}
    inv = snap.get("inventory", {}) or {}
    sys = snap.get("systems", {}) or {}
    apply_player_state(pl)
    apply_inventory(inv)
    apply_playtime_sec(sys.get("playtime_sec", 0))
 
    # 5.5) ★ ロード直後の“確定スポーン”を 1 フレーム遅延で適用するための予約を積む
    #      - 一部の初期スクリプト/自動ワープが、ロード直後に位置やマップを上書きするのを防ぐ
    try:
        if not hasattr(gs, "state") or not isinstance(gs.state, dict):
            gs.state = {}
        gs.state["__pending_load_spawn"] = {
            "map": map_id,
            # 現在値を使う（apply_player_state 直後なので最新）
            "x": float(getattr(gs, "player_x", 0.0)),
            "y": float(getattr(gs, "player_y", 0.0)),
            "angle": float(getattr(gs, "player_angle", 0.0)),
        }
        # ロード直後の“自動ワープ”を数フレームだけ抑止（イベントの暴発を防ぐ）
        cur = gs.state.get("__suppress_warp_frames", 0)
        gs.state["__suppress_warp_frames"] = max(cur, 2)
    except Exception:
        pass

    # 6) ランタイム一時状態のクリア
    _reset_runtime_visuals_after_load()
    # 7) 点滅/途中進行の再構築
    _rehydrate_switch_visuals_from_flags()
    # スナップショット
    mid = map_id or getattr(gs, "current_map_id", "")
    # 8) X↔'.' 再構成（原本へ戻してから適用）
    _rebuild_barriers_from_flags(getattr(gs, "current_map_id", ""))
    # 8.5) ★ ドア開放の反映（SAVEに記録された個別のドア開放を '.' に固定）
    _apply_doors_opened_from_flags(getattr(gs, "current_map_id", ""))
    # 9) special の見た目復元（参照付け替えのみ・動的キー対応）
    _apply_switch_lit_from_flags(getattr(gs, "current_map_id", ""))


    # 10) 霧・倒木など“最終レイヤ”の適用（main 側のラッパーがあれば使う）
    try:
        import sys
        fn = None
        m = sys.modules.get("__main__")
        if m and hasattr(m, "apply_visual_pipeline_final"):
            fn = getattr(m, "apply_visual_pipeline_final")
        else:
            import main as _main
            if hasattr(_main, "apply_visual_pipeline_final"):
                fn = getattr(_main, "apply_visual_pipeline_final")
        if callable(fn):
            fn(map_id)  # ← ここで fog/trees 一式が当たる
    except Exception:
        # 保険：最低限 fog だけはローカル置換でも当てる（既に入っていればOK）
        _apply_fog_from_flags(map_id)  

# =========================
# ファイル I/O
# =========================
def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    bak = path.with_suffix(".json.bak")
    if path.exists():
        try:
            path.replace(bak)
        except Exception:
            pass
    tmp.replace(path)

def save_game(slot: str = "slot1",
              meta_comment: Optional[str] = None,
              *,
              notify: bool = True,
              notify_ms: Optional[int] = None) -> bool:
    slot_norm = _normalize_slot(slot)
    if slot_norm not in SAVE_SLOTS:
        if notify: _toast(f"[SAVE] 不正なスロット名: {slot}", ms=notify_ms)
        return False
    if getattr(gs, "is_cutscene", False):
        if notify: _toast("カットシーン中はセーブできません。", ms=notify_ms)
        return False
    
    # --- セーブ禁止エリア（no_save）をチェック -------------------------
    try:
        cur_map_id = getattr(gs, "current_map_id", "")
        if cur_map_id and isinstance(MAPS.get(cur_map_id), dict):
            if MAPS[cur_map_id].get("no_save"):
                # UIトーストに明確な理由を出す（メニュー側notify=Falseでもこちらで出せる）
                if notify: _toast("このエリアではセーブできません（ダンジョン内）。", ms=notify_ms)
                return False
    except Exception:
        # 失敗してもセーブ処理自体は継続可能だが、ここでは許可しない
        if notify: _toast("現在地の判定に失敗しました。セーブを中止します。", ms=notify_ms)
        return False
    
    path = slot_path(slot_norm)
    snap = build_snapshot(meta_comment=meta_comment)
    try:
        _atomic_write_json(path, snap)
        if notify: _toast("セーブしました。", ms=notify_ms)
        return True
    except Exception as e:
        try:
            fb_dir = _fallback_save_dir()
            fb_dir.mkdir(parents=True, exist_ok=True)
            fb_path = fb_dir / path.name
            _atomic_write_json(fb_path, snap)
            if notify: _toast("セーブしました。", ms=notify_ms)
            return True
        except Exception as e2:
            if notify: _toast(f"セーブ失敗: {e} / fallback: {e2}", ms=notify_ms)
            return False

def load_game(slot: str = "slot1",
              *,
              notify: bool = True,
              notify_ms: Optional[int] = None) -> bool:
    """指定スロットからロード。成功なら True。成功時は『ロードしました。』のみ表示。"""
    slot_norm = _normalize_slot(slot)
    if slot_norm not in SAVE_SLOTS:
        if notify: _toast(f"[LOAD] 不正なスロット名: {slot}", ms=notify_ms)
        return False

    primary = slot_path(slot_norm)
    candidates = [primary, _fallback_save_dir() / primary.name]
    found_any = False
    last_err = None
    success_path = None
    for p in candidates:
        if not p.exists():
            continue
        found_any = True
        try:
            with p.open("r", encoding="utf-8") as f:
                snap = json.load(f)
            apply_snapshot(snap)
            success_path = p
            break
        except Exception as e:
            last_err = (e, p)
            continue
    if success_path is not None:
        if notify: _toast("ロードしました。", ms=notify_ms)
        return True
    if notify:
        if found_any and last_err is not None:
            e, p = last_err
            _toast(f"ロード失敗: {e} ({p})", ms=notify_ms)
        else:
            _toast("指定スロットにセーブデータが見つかりません。", ms=notify_ms)
    return False

def delete_save(slot: str) -> bool:
    slot_norm = _normalize_slot(slot)
    if slot_norm not in SAVE_SLOTS:
        _toast(f"[DELETE] 不正なスロット名: {slot}")
        return False
    ok = False
    for p in [slot_path(slot_norm), _fallback_save_dir() / f"{slot_norm}.json"]:
        try:
            if p.exists():
                p.unlink()
                _toast(f"削除しました: {p}")
                ok = True
        except Exception as e:
            _toast(f"削除失敗: {e} ({p})")
    if not ok:
        _toast("指定スロットのファイルがありません。")
    return ok

def save_exists(slot: str) -> bool:
    slot_norm = _normalize_slot(slot)
    p = slot_path(slot_norm)
    return p.exists() or (_fallback_save_dir() / p.name).exists()

def _fmt_hms(total_sec: int) -> str:
    total_sec = max(0, int(total_sec))
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def list_saves() -> List[Dict[str, Any]]:
    """UI向けセーブ一覧。破損ファイルでも最低限の情報を返す。"""
    result: List[Dict[str, Any]] = []
    for s in SAVE_SLOTS:
        info: Dict[str, Any] = {"slot": s, "exists": False}
        for p in [slot_path(s), _fallback_save_dir() / f"{s}.json"]:
            if p.exists():
                info["exists"] = True
                try:
                    with p.open("r", encoding="utf-8") as f:
                        snap = json.load(f)
                    info["map_id"] = ((snap.get("map") or {}).get("id")) or ""
                    ts_str = snap.get("timestamp")
                    if not ts_str:
                        epoch = snap.get("saved_at", int(p.stat().st_mtime))
                        ts_str = datetime.fromtimestamp(int(epoch)).strftime("%Y-%m-%d %H:%M:%S")
                    info["timestamp"] = ts_str
                    info["saved_at"] = snap.get("saved_at", int(p.stat().st_mtime))
                    play_sec = ((snap.get("systems") or {}).get("playtime_sec")) or 0
                    info["playtime"] = _fmt_hms(int(play_sec))
                    info["comment"] = snap.get("comment", "")
                    inv = snap.get("inventory", {}) or {}
                    info["items"] = sum(int(v) for v in inv.values() if isinstance(v, int))
                    info["path"] = str(p)
                except Exception:
                    info["timestamp"] = "-"
                    info["playtime"] = "00:00:00"
                    info["path"] = str(p)
                break
        result.append(info)
    return result
