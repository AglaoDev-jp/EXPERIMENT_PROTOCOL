# main.py
"""
Copyright © 2025 AglaoDev-jp

---

Code by AglaoDev-jp © 2025  
Licensed under the MIT License.

Images by AglaoDev-jp © 2025  
Licensed under the Creative Commons Attribution 4.0 International (CC BY 4.0).

Scenario by AglaoDev-jp © 2025  
Licensed under the Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0).

---

## Fonts

This game uses the “Noto Sans JP” font family (NotoSansJP-Regular.otf).

© 2014–2025 Google LLC  
Licensed under the SIL Open Font License, Version 1.1  
https://scripts.sil.org/OFL

---

## External Libraries

- pygame  
  © 2000–2024 Pygame developers  
  Licensed under the LGPL v2.1 License  
  https://www.pygame.org/docs/license.html

- NumPy  
  © 2005–2025 NumPy Developers. All rights reserved.  
  Licensed under the BSD 3-Clause License (NumPy License)  
  https://numpy.org

- OpenCV 4.10.0  
  © 2000–2025 OpenCV Foundation and contributors  
  Licensed under the Apache License, Version 2.0  
  https://opencv.org

- cryptography  
  © 2013–2025 The cryptography developers  
  Licensed under the Apache License 2.0 or the BSD 3-Clause License  
  https://github.com/pyca/cryptography/blob/main/LICENSE

  This software includes cryptographic components from OpenSSL 3.4.0 (22 Oct 2024),
  distributed under the Apache License 2.0  
  © 1998–2025 The OpenSSL Project Authors  
  © 1995–1998 Eric A. Young, Tim J. Hudson  
  All rights reserved.

- Cython  
  © 2007–2025 The Cython Project Developers  
  Licensed under the Apache License 2.0

---

Special thanks to all developers and contributors who made these libraries possible.

---

*This file was created and refined with support from OpenAI’s conversational AI, ChatGPT.*

"""


from pathlib import Path
import sys
import pygame
import math
import numpy as np
import os
import copy
import re
from typing import Optional
from cryptography.fernet import Fernet

DEV_MODE = os.getenv("DEV_MODE", "0") == "1"  # 環境変数 DEV_MODE=1 の時だけ開発機能ON
# --- DEV_MODE 使い方 ------------------------------------------------------
# ・トグル: Ctrl+F3（DEV_MODE=1 のときだけ）
# ・PowerShell: $env:DEV_MODE=1; py ./main.py
# ・CMD      : set DEV_MODE=1 && py main.py
# ・Bash     : DEV_MODE=1 python main.py
# ・VS Code  : .vscode/launch.json の "env": {"DEV_MODE":"1"}
# まずcd　でファイルを参照
# cd "C:\...\...\"
# そのあと
# $env:DEV_MODE=1; py .\main.py
# みたいな感じ
# -------------------------------------------------------------------------

SHOW_DEBUG_OVERLAY = True                    # 初期状態は非表示

# --- プロジェクトのルート設定 ---
BASE_DIR = Path(__file__).resolve().parent

# --- 各種モジュール読み込み ---
from core.config import WIDTH, HEIGHT, FOV, NUM_RAYS, MAX_DEPTH, TILE, PLAYER_SPEED, DELTA_ANGLE
from core.maps import MAPS
import core.game_state as game_state
from core.texture_loader import load_textures
from core.interactions import (
    try_pickup_item,
    try_open_door,
    try_press_switch,
    try_chop_tree,
    try_offer_guardian,
    try_use_exit,
    _front_tile,
    make_entity_key,
    TREE_HITS_REQUIRED
)
from core.tile_types import TILE_TYPES
from core.ui import ToastManager, draw_label, blit_pill_label_midtop, begin_world_toasts, flush_world_toasts
from scenes.menu import MenuScene
from core.items import get_sprite_meta, display_name
from core.fonts import render_text  # 縁取り/影つき文字の生成に使う

from core.asset_utils import (
    load_or_placeholder,
    make_wall_placeholder_surface,
    make_floor_placeholder_array,
    make_ceiling_placeholder_array,
)
from core.transitions import fade_in, fade_out
from scenes.intro_event import IntroEventScene
from scenes.startup import run_startup_sequence
from scenes.doctor_event import run_doctor_event
from collections import deque
from collections.abc import Callable
from core.player import handle_movement, handle_rotation
from core.save_system import (
    save_game,
    load_game,
    remember_special_baseline_for_map,
    _rebuild_barriers_from_flags,
    _apply_switch_lit_from_flags,
    _rehydrate_switch_visuals_from_flags,
)
from core.cinematics import (
    has_played as cin_has_played,
    mark_played as cin_mark_played,
    can_fire as cin_can_fire,
    arm_cooldown as cin_arm_cd,
    enqueue_video as cin_enqueue,
    process_queue as cin_process_queue,
    play_video_blocking as cin_play_blocking,
    trigger_proximity_movie_once as cin_trigger_once,
    run_doctor_gate_sequence as cin_run_doctor_gate,
)
from core.enemies import Chaser
from scenes.ending_event import run_ending_sequence

from core.sound_manager import SoundManager

# タスクバーのタイトル用の定数（Pygame初期化のあと）
GAME_TITLE: str = "Experiment Protocol ─ The Experiment continues ─"

PROX_MOVIES_ENABLED = False  # 近接ムービー（霧/川/大木）の自動再生を一時停止

# main.py のグローバル付近
if not hasattr(game_state, "current_enemies"):
    game_state.current_enemies = []  # 今のマップに存在する敵インスタンス一覧

# 敵の生成・更新
game_state.FLAGS.setdefault("videos_played", set())

# インベントリ（dict）が無い環境でも壊れないように保証
if not hasattr(game_state, "inventory") or not isinstance(getattr(game_state, "inventory"), dict):
    game_state.inventory = {}

CHASER_SAFE_MS = 3000        # スポーン直後は3秒は捕獲しない
CHASER_CATCH_COOLDOWN = 1500 # 捕獲後1.5秒は再捕獲しない
CHASER_CATCH_RADIUS = 18.0   # 既存値に合わせる（必要なら調整）
CHASER_WAKE_DELAY_MS = 700     # ★ 追跡者が動き始めるまでの“待ち”を新設

# --- 起動時に一度だけ「原本レイアウト」を確保 --------------------------------
# ・文字列は不変なので、行リストのシャローコピーでOK
# ・setdefaultで“二重実行時の上書き”を防止（ホットリロード対策）

for _mid, _m in MAPS.items():
    _m.setdefault("_layout_base", _m["layout"][:])
    # extures の原本を丸ごと保持（deepcopy）
    _m.setdefault("_textures_base", copy.deepcopy(_m.get("textures") or {}))

def _get_footprint_base():
    """
    風見鶏アイコン（forward/back）のどちらかが存在すればそれを採用。
    どちらも無ければプレースホルダを生成する。
    ※ 以前は png 変数を連続代入しており、先に設定したパスが即座に上書きされていました。
    """
    global _FOOT_BASE
    if _FOOT_BASE is None:
        try:
            base_dir = Path(__file__).resolve().parent
            candidates = [
                base_dir / "assets" / "sprites" / "weathercock.png",
                base_dir / "assets" / "sprites" / "weathercock_back.png",
            ]
            for p in candidates:
                if p.exists():
                    _FOOT_BASE = pygame.image.load(str(p)).convert_alpha()
                    break
            else:
                _FOOT_BASE = _make_footprint_surface(48)
        except Exception:
            _FOOT_BASE = _make_footprint_surface(48)
    return _FOOT_BASE

# --- マップ資産の同期フック -----------------------------------------------
if not hasattr(game_state, "_last_loaded_map_id"):
    game_state._last_loaded_map_id = None

def ensure_current_map_assets_synced(*, force: bool = False) -> None:
    """
    ・current_map_id が直前にロードしたマップと異なる/force=True のときに再ロード。
    ・マップ遷移やカットシーン内で map_id を変えた場合でも、確実に見た目を更新。
    """
    cur = getattr(game_state, "current_map_id", None)
    if force or (cur != game_state._last_loaded_map_id):
        load_current_map_assets()  # ← 内部で sprites まで構築済み
        game_state._last_loaded_map_id = cur

# -------------------------------------------------------------------------

# -------------------------------
# --- デバッグ用ユーティリティ ---
# -------------------------------

def tick_auto_events_and_debug():
    # ここで現在状態を一発ログ（forest_end 限定）
    if game_state.current_map_id == "forest_end":
        played = _has_played_video("forest_end", DOCTOR_EVENT_ID)
        print("[DBG] forest_end:",
              "played=", played,
              "can_fire=", _can_fire_cinematic(),
              "is_cutscene=", getattr(game_state, "is_cutscene", False),
              "cooldown_until=", getattr(game_state, "cinematic_cooldown_ms", 0),
              "now=", pygame.time.get_ticks())

    # 近接ムービー系（必要に応じて追加/削除OK）
    maybe_run_doctor_gate_once()
    _process_cinematic_queue()

def _debug_dump_lab_gate():
    if game_state.current_map_id != "forest_end": 
        return
    played = _has_played_video("forest_end", DOCTOR_EVENT_ID)
    print("[DBG] forest_end gate:",
          "played=", played,
          "can_fire=", _can_fire_cinematic(),
          "is_cutscene=", getattr(game_state, "is_cutscene", False),
          "cooldown_until=", getattr(game_state, "cinematic_cooldown_ms", 0),
          "now=", pygame.time.get_ticks())

# --- オプショナル取込み（未整備でも動くようフォールバック） -------------------
# 1) アイテム正規化：core.items.normalize_item_entry があれば使う、無ければローカル実装にフォールバック
try:
    from core.items import normalize_item_entry as _normalize_item_entry_external
except Exception:
    _normalize_item_entry_external = None

def _normalize_item_entry_fallback(it: dict) -> dict:
    """
    旧/新アイテム定義を統一形式に整えるフォールバック。
    - 旧式: {"id","type","tile","picked"}
    - 新式: {"id","kind","name","pos"}
    """
    if "tile" in it and "type" in it:
        return {
            "id": it.get("id", ""),
            "type": it["type"],
            "tile": tuple(it["tile"]),
            "picked": bool(it.get("picked", False)),
        }
    kind = it.get("kind")
    if kind == "tool" and it.get("id", "").startswith("axe"):
        type_name = "axe"
    elif kind == "offering":
        type_name = "spirit_orb"
    elif kind == "key":
        # --- 鍵の種別を id から推定する（"key_lab_*" は key_lab 扱い） ---
        iid = it.get("id", "")
        if iid.startswith("key_lab"):
            type_name = "key_lab"      # ← ラボ鍵は正しく key_lab へ
        elif iid.startswith("key_forest"):
            type_name = "key_forest"
        else:
            # 既定は従来互換で森鍵扱い（必要に応じて拡張可）
            type_name = "key_forest"
    else:
        type_name = it.get("id", "misc")
    return {
        "id": it.get("id", ""),
        "type": type_name,
        "tile": tuple(it.get("pos", (0, 0))),
        "picked": bool(it.get("picked", False)),
    }

# 実際に使う入り口（外部があればそちら優先）
normalize_item_entry = _normalize_item_entry_external or _normalize_item_entry_fallback

# 2) マップ健診：core.maps.run_maps_health_check があれば使う
try:
    from core.maps import run_maps_health_check as _run_maps_health_check
except Exception:
    _run_maps_health_check = None

# 3) ミニマップ色：core.config.MINIMAP_COLORS があれば使う
try:
    from core.config import MINIMAP_COLORS as MMC
except Exception:
    MMC = {
        "wall":     (40, 160, 60, 255),
        "floor":    (220, 220, 220, 80),
        "exit":     (235, 205, 40, 220),   # '>' 進む
        "entrance": (90, 210, 255, 220),   # '<' 戻る
        "border":   (0, 0, 0, 180),
    }

# 起動時マップチェック：マップは矩形か？
def _assert_rectangular(map_id: str, map_def: dict):
    layout = map_def["layout"]
    w0 = len(layout[0])
    for y, row in enumerate(layout):
        if len(row) != w0:
            # 問題行の中身も併記（デバッグ短縮）
            raise ValueError(
                f"[{map_id}] Map layout is not rectangular at row {y}: expected {w0}, got {len(row)} -> {row!r}"
            )

# 旧式の簡易矩形検査（run_maps_health_check が別にあればそちらで包括チェック）
if _run_maps_health_check is None:
    for mid, m in MAPS.items():
        _assert_rectangular(mid, m)

# 壁/床/天井が無い時は自動でプレースホルダーに置換
def _ensure_placeholder_textures_for_current_map():
    """
    壁/床/天井テクスチャが無い場合でも落ちないように、
    手描きプレースホルダーを自動充填する安全ネット。
    ただし、マップ定義で floor/ceiling に None が明示されている場合は
    「描かない」意図として尊重してプレースホルダーを入れない。
    """
    cur_map = MAPS.get(game_state.current_map_id, {})
    tex = game_state.current_textures

    # 実際の指定は cur_map["textures"][...] に入っている
    tex_cfg = (cur_map.get("textures") or {})

    def wants_none(field: str) -> bool:
        """textures セクションで None が明示されているか？"""
        return (field in tex_cfg) and (tex_cfg[field] is None)

    # 壁：常に何かは必要なので、無ければプレースホルダーで埋める
    if not isinstance(tex.get("wall"), pygame.Surface):
        tex["wall"] = make_wall_placeholder_surface(TILE)

    # 床（(TILE,TILE,3) ndarray）
    if wants_none("floor"):
        tex["floor_arr"] = None
    elif tex.get("floor_arr") is None:
        tex["floor_arr"] = make_floor_placeholder_array(TILE)

    # 天井（None 指定なら描かない）
    if wants_none("ceiling"):
        tex["ceiling_arr"] = None
    elif tex.get("ceiling_arr") is None:
        tex["ceiling_arr"] = make_ceiling_placeholder_array(TILE)

    # 安全 壁の特殊記号辞書が None だと参照時に落ちるので空dictを保証
    tex.setdefault("wall_special", {})
    tex.setdefault("special", {})

def _count_char(layout, ch):
    """マップlayout中に含まれる文字chの個数を数える"""
    return sum(r.count(ch) for r in layout)

def build_tile_grid(layout: list[str]) -> np.ndarray:
    """
    ★ マップの文字レイアウトを数値(ASCII)配列に変換してキャッシュ。
    例: '.' -> ord('.')、'a' -> ord('a')
    """
    h = len(layout)
    w = len(layout[0]) if h else 0
    arr = np.empty((h, w), dtype=np.uint8)
    for j, row in enumerate(layout):
        # 行長は矩形前提（起動時に検査済み）
        arr[j, :] = np.frombuffer(row.encode('ascii'), dtype=np.uint8)
    return arr

def _merge_textures_from_base(cur_map: dict) -> dict:
    """cur_map['textures'] を _textures_base で補完（special を必ず復元）"""
    base = cur_map.get("_textures_base") or {}
    cur  = cur_map.get("textures") or {}

    merged = dict(base)  # 基本は原本

    # 単体キー（壁/床/天井）は“現在の指定”を優先
    for k in ("wall", "floor", "ceiling"):
        if k in cur:
            merged[k] = cur[k]

    # dictキーは deep-merge（base に無い 'w','B' などが消えないように）
    for k in ("wall_special", "special"):
        merged[k] = dict(base.get(k) or {})
        merged[k].update(cur.get(k) or {})

    return merged

def load_current_map_assets():
    """
    ロード時に “原本 textures” と現在の定義をマージしてから読み込む。
    - merged_mapdef を必ず用意（マージ失敗時はフォールバック）
    - テクスチャは 1 回だけロード
    - special のプレースホルダと自己修復を実施
    - ロード直後に「未点灯ベースライン記録 → X↔'.' 再構成 → lit/未点灯 参照付け替え」を一度だけ実行
    - 霧/守人など他の再構成も冪等に適用
    """
    # 現在マップ
    cur_map_id = game_state.current_map_id
    cur_map = MAPS[cur_map_id]

    # --- 安全なマージ処理：必ず merged_mapdef を定義する ---
    try:
        merged_mapdef = dict(cur_map)
    except Exception:
        merged_mapdef = {}

    # textures を原本で補完（失敗時は現行の textures をそのまま使用）
    try:
        merged_tex = _merge_textures_from_base(cur_map)
    except Exception:
        merged_tex = cur_map.get("textures", {}) or {}
    merged_mapdef["textures"] = merged_tex

    # --- テクスチャを 1 回だけロード ---
    game_state.current_textures = load_textures(BASE_DIR, merged_mapdef)

    # DEV モード時は special キーを表示（任意のデバッグ出力）
    if DEV_MODE:
        spec_keys = list((game_state.current_textures.get("special") or {}).keys())
        print(f"[TEX] map={cur_map_id} special keys: {spec_keys}")

    # 欠品のプレースホルダ適用 & special の自己修復（“常に dict”を保証）
    _ensure_placeholder_textures_for_current_map()
    _ensure_special_ready_for_current_map()

    # --- ロード直後の“一度だけ”世界再構築（lazy importで安全に）---
    try:
        from core.save_system import (
            remember_special_baseline_for_map,
            _rebuild_barriers_from_flags,
            _apply_switch_lit_from_flags,
        )
        # ① 未点灯ベースラインを記録（lit ←→ 未点灯の参照切替の基準）
        remember_special_baseline_for_map(cur_map_id)
        # ② X↔'.' を原本から再構成（解除セーブ→未解除セーブの往復でも残留しない）
        _rebuild_barriers_from_flags(cur_map_id)
        # ③ スイッチ見た目：解決済みなら *_lit、未解決なら未点灯へ参照を戻す
        _apply_switch_lit_from_flags(cur_map_id)
    except Exception:
        # ここで失敗しても致命ではない（次のロード/遷移時に再試行される）
        pass

    # --- 霧や守人など、他の再構成（あるなら冪等に）---
    try:
        _apply_fog_state_for_map(cur_map_id)
        _apply_guardian_state_for_map(cur_map_id)
    except Exception:
        pass

    # タイルグリッド再構築
    game_state.current_tile_grid = build_tile_grid(cur_map["layout"])

    # アイテムの正規化＆スプライト準備
    normalize_and_spawn_items_for_map(cur_map_id)
    prepare_item_sprites_for_current_map(BASE_DIR)
    build_world_sprites_for_map(cur_map_id)

    # ★ マップ準備直後の“一度だけ”後処理フック（存在すれば）
    try:
        on_world_rebuild_for_current_map()
    except Exception:
        pass

# save_system.apply_snapshot からも呼べるように 1 回だけ外でエクスポート
game_state.load_current_map_assets = load_current_map_assets

def on_world_rebuild_for_current_map() -> None:
    """
    ロード直後／マップ切替直後／パズル解決直後など“イベント時だけ”呼ぶ。
    - 毎フレーム禁止（重い処理を避ける）
    手順:
      1) 障壁(X↔'.')復元と *_lit 参照付け替え
      2) 点滅等の見た目を FLAGS から再適用
      3) 任意のワールド再適用（fog/guardian/doors/trees の冪等アプライヤ）
      4) 最終描画パイプラインの適用
      5) 敵スポーン
      6) ★マップ環境音（ambience）の適用
    """
    try:
        # 1) 壁復元 & 2) lit/点滅の再適用
        from core.save_system import _rebuild_barriers_from_flags, _apply_switch_lit_from_flags
        _rebuild_barriers_from_flags(game_state.current_map_id)
        _apply_switch_lit_from_flags(game_state.current_map_id)
        _rehydrate_switch_visuals_from_flags()
    except Exception:
        pass
    # 3) fog / guardian / doors / trees などの冪等アプライ
    try:
        if hasattr(game_state, "refresh_world_state"):
            game_state.refresh_world_state()
    except Exception:
        pass
    # 4) 最終決定（タイル/スプライト整合の仕上げ）
    try:
        apply_visual_pipeline_final(game_state.current_map_id)
    except Exception:
        pass
    # 5) 敵スポーン
    try:
        build_enemies_for_current_map()
    except Exception:
        pass
    # 6) ★環境音の適用
    try:
        _apply_map_ambience()
    except Exception:
        # ここで失敗してもゲーム継続を優先
        pass

def _apply_map_ambience() -> None:
    """
    現在マップの 'ambience' を見て、ループSEを開始/停止する。
    - 例: MAPS[cur]["ambience"]["se_loop"] = "river_loop"
    - 指定がなければ環境音を停止する。
    """
    cur_id = getattr(game_state, "current_map_id", "")
    try:
        amb = (MAPS.get(cur_id, {}) or {}).get("ambience") or {}
        want_key = amb.get("se_loop")
        loop_name = "ambience"  # SoundManager の論理チャンネル名
        if want_key:
            # 未ロード警告（デバッグ用）
            if hasattr(sound_manager, "has_se") and not sound_manager.has_se(want_key):
                print(f"[AMBIENCE][WARN] SE not loaded: {want_key!r}  （ファイル名/拡張子 .mp3.enc を確認）")
            sound_manager.play_loop(name=loop_name, se_key=want_key, fade_ms=250)
        else:
            sound_manager.stop_loop(name=loop_name, fade_ms=300)
        print(f"[AMBIENCE] map={cur_id} -> {want_key or 'STOP'}")
    except Exception as e:
        print("[AMBIENCE][WARN]", e)

def build_enemies_for_current_map():
    game_state.current_enemies = []
    cur_id = game_state.current_map_id
    cur_map = MAPS.get(cur_id, {})
    tile = TILE

    # 互換1: "enemies": [{"kind":"chaser","pos":(x,y),"speed":...}, ...]
    use_count = 0
    for e in cur_map.get("enemies", []):
        if e.get("kind") != "chaser":
            continue
        tx, ty = e.get("pos", (0, 0))
        px, py = tx * tile + tile * 0.5, ty * tile + tile * 0.5
        speed = float(e.get("speed", 2.2))
        game_state.current_enemies.append(Chaser(spawn_px=(px, py), speed=speed))
        use_count += 1

    # 互換2: "chaser": {"enabled":True, "spawn":(x,y), "speed":...}
    ch_def = cur_map.get("chaser")
    if use_count == 0 and isinstance(ch_def, dict) and ch_def.get("enabled"):
        tx, ty = tuple(ch_def.get("spawn", (0, 0)))
        px, py = tx * tile + tile * 0.5, ty * tile + tile * 0.5
        speed = float(ch_def.get("speed", 2.2))
        game_state.current_enemies.append(Chaser(spawn_px=(px, py), speed=speed))

# ------------------------------------------------------------
# ビルボード投影して描画するヘルパ（フレーム画像を渡して描画）
# ------------------------------------------------------------
def draw_billboard_sprite(
    screen: pygame.Surface,
    frame: pygame.Surface,
    sprite_x: float, sprite_y: float,              # ワールド座標（ピクセル）
    base_world_size_px: float = None,              # ワールド上の見かけサイズ（px）。未指定なら TILE を使う
    fov_rad: float = None                          # FOV（ラジアン）。未指定なら 60度相当
) -> bool:
    """
    戻り値: 描画できたら True、culling などで描画しなかったら False
    """
    # ---- 各種デフォルト ----
    if base_world_size_px is None:
        base_world_size_px = TILE  # タイル1枚ぶんの見かけサイズで投影するのが分かりやすい
    if fov_rad is None:
        fov_rad = math.radians(60.0)  # エンジンの FOV に合わせてください（例: 60°）

    # ---- プレイヤー基準の相対ベクトル（ワールド座標系）----
    px, py = game_state.player_x, game_state.player_y
    dx = sprite_x - px
    dy = sprite_y - py

    # ---- カメラ座標系への回転（プレイヤー向き = +Z 前方と考える）----
    # 画面に対して前方を +Y としたいので、角度 -angle の回転を適用
    ang = game_state.player_angle
    # 回転行列 R(-ang) を適用
    cam_x =  math.cos(ang) * dx + math.sin(ang) * dy     # 右（+）/左（-）
    cam_y = -math.sin(ang) * dx + math.cos(ang) * dy     # 前（+）/後（-）

    # ---- 背面カリング（プレイヤーの後ろにあるなら描かない）----
    if cam_y <= 1.0:  # 1px 以内（ほぼゼロ距離/背面）は描かない
        return False

    # ---- 射影面までの距離（焦点距離）----
    # 理屈: tan(FOV/2) = (画面半幅) / 焦点距離 → 焦点距離 = 画面半幅 / tan(FOV/2)
    dist_to_plane = (WIDTH / 2) / math.tan(fov_rad / 2)

    # ---- スケール計算：距離に反比例して小さくなる ----
    # 画面上の見かけ高さ = 焦点距離 / Z * "ワールド基準サイズ"
    scale = dist_to_plane / cam_y
    screen_h = int(base_world_size_px * scale)
    screen_w = int(frame.get_width() * (screen_h / max(1, frame.get_height())))  # 縦基準でアスペクト維持

    if screen_h <= 0 or screen_w <= 0:
        return False  # ほぼ点なのでスキップ

    # ---- 画面上のX位置：カメラ右方向 cam_x を "scale" 倍して中央からのオフセットに ----
    screen_x_center = int(WIDTH / 2 + cam_x * scale)
    # スプライトは中央揃えにしたいので、左上座標を算出
    screen_left = screen_x_center - screen_w // 2
    screen_top  = int(HALF_HEIGHT - screen_h // 2)  # 地面/空ありの中央基準。床に立たせたいなら調整してOK

    # ---- 画面外フルオフならスキップ（軽いクリッピング）----
    if screen_left >= WIDTH or (screen_left + screen_w) <= 0:
        return False
    if screen_top >= HEIGHT or (screen_top + screen_h) <= 0:
        # 縦方向は上に飛び出すことも多いので、ここは厳密に切らなくてもOK
        pass

    # ---- スケールして描画 ----
    if (screen_w, screen_h) != frame.get_size():
        # 細部が気になるなら smoothscale、速度重視なら transform.scale
        frame_scaled = pygame.transform.smoothscale(frame, (screen_w, screen_h))
    else:
        frame_scaled = frame
    rect = frame_scaled.get_rect(topleft=(screen_left, screen_top))
    screen.blit(frame_scaled, rect)
    return True

# -------------------------------
# ユーティリティ
# -------------------------------

menu_scene = None  # None → 非表示 / MenuScene() → メニュー表示中

# このIDで「再生済み」を videos_played に記録。
DOCTOR_SEQ_ID = "doctor_seq_forest_end"
# videos_played で使う一意ID 互換性のため、同値にしておく
DOCTOR_EVENT_ID = DOCTOR_SEQ_ID 

# --- モジュール先頭などのグローバル ---
_last_special_built_for_map = None  # 直近にbuildしたmap_idを保持

# ===== 自動振り向き＆入力ロック用 定数 =====
TURN_ARC_MS = 450            # 何msかけて回転するか（450msくらいが“振り向き”感）
INPUT_LOCK_EXTRA_MS = 150    # 回転完了後に少しだけ追いロック（余韻）
# ※ 合計で 600ms 前後の入力無効になる想定

# === 追跡者ナビ用（軽量） ===
NAV_REPATH_MS = 300        # 再探索は0.3秒間隔
LOS_STEP_PX   = 8          # 視界チェックのサンプリング間隔(px)

# 追跡者ステートにウェイポイント等を足す（setdefault 群の近く）
st = game_state.state
st.setdefault("__nav", {"next_wp": None, "repath_at": 0})

st = game_state.state
# 既存 setdefault 群の近くに追加
st.setdefault("__input_lock_until", 0)   # この時刻まで移動・回転入力を無効化
st.setdefault("__turn_anim", {           # 自動回転アニメの状態
    "active": False,
    "start": 0,
    "dur": 0,
    "from": 0.0,
    "to": 0.0,
})

def _start_auto_turn_180_and_lock_input():
    """
    ムービー直後に呼ぶ：
    - 入力を一時ロック
    - プレイヤー角度を 180°へスムーズに補間（TURN_ARC_MS）
    """
    now = pygame.time.get_ticks()
    from_ang = game_state.player_angle
    to_ang   = (from_ang + math.pi) % (2*math.pi)

    game_state.state["__turn_anim"] = {
        "active": True,
        "start": now,
        "dur": TURN_ARC_MS,
        "from": from_ang,
        "to": to_ang,
    }
    game_state.state["__input_lock_until"] = now + TURN_ARC_MS + INPUT_LOCK_EXTRA_MS


# === 追跡者：背後スポーン（最小版） ========================================
def _spawn_chaser_behind(distance_px: float = 72.0) -> None:
    """
    プレイヤーの“背後”に追跡者を出現させる。
    ・位置の決定と state への書き込みのみを担当（※アニメ進行は update_chaser_anim() が一元管理）
    ・衝突しない足場を最大6回まで手前に寄せて探索
    """
    # --- 現在のマップ情報を取得 ---
    cur_map = MAPS[game_state.current_map_id]
    layout = cur_map["layout"]

    # --- 背後方向（プレイヤーの向き + 180°）を算出 ---
    ang = (game_state.player_angle + math.pi) % (2 * math.pi)
    dx, dy = math.cos(ang), math.sin(ang)

    # --- 背後の指定距離に仮スポーン座標を置く（ピクセル座標） ---
    sx = game_state.player_x + dx * distance_px
    sy = game_state.player_y + dy * distance_px

    # --- タイル上の通行可否を見つつ、壁なら少しずつ手前に寄せる（最大6回） ---
    #     通行可タイルの集合は必要に応じて調整してください（'.' = 床, 'E' = 出口など）
    PASSABLE = ('.', 'E', '<', '>', ' ')  # 必要なら拡張
    step = max(1.0, distance_px / 6.0)    # 1回の戻り量（px）
    for _ in range(6):
        tx, ty = int(sx // TILE), int(sy // TILE)
        if (0 <= ty < len(layout)) and (0 <= tx < len(layout[0])) and (layout[ty][tx] in PASSABLE):
            break
        # 壁などで不可なら、少し手前に戻す
        sx -= dx * step
        sy -= dy * step

    # --- マップの外に出ないように“ざっくり”クランプ（必要に応じて厳密化） ---
    sx = max(TILE * 0.5, min(sx, (len(layout[0]) - 0.5) * TILE))
    sy = max(TILE * 0.5, min(sy, (len(layout) - 0.5) * TILE))

    # --- 追跡者ステートを書き込む（描画・更新と揃える） ---
    st = game_state.state.setdefault("chaser", {})
    now_ms = pygame.time.get_ticks()
    st.update({
        "active": True,
        "map_id": game_state.current_map_id,
        "x": sx,
        "y": sy,
        "since_ms": now_ms,                      # 出現時刻
        "wake_at_ms": now_ms + CHASER_WAKE_DELAY_MS,  # 目覚め（稼働）開始の遅延
        "anim_frame": 0,                         # 旧設計互換用（使わなくてもOK）
    })

    # --- アニメ初期化（※進行は update_chaser_anim() が担当） ---
    #     グローバルの現在フレームと、最後に進めた時刻をリセット
    global CHASER_CUR_INDEX, CHASER_LAST_ADV_MS
    CHASER_CUR_INDEX = 0
    CHASER_LAST_ADV_MS = now_ms

    # --- スポーン直後の“捕獲無効”時間を設定（既存の定数を利用） ---
    game_state.state["__chaser_safe_until"] = now_ms + CHASER_SAFE_MS

    print("[CHASER] spawned behind player at (%.1f, %.1f)" % (sx, sy))

    st = game_state.state.setdefault("chaser", {})
    st.clear()  # ← ゴミを持ち越さない
    st["active"]  = True
    st["map_id"]  = game_state.current_map_id
    st["x"]       = float(sx)
    st["y"]       = float(sy)
    st["speed"]   = float(st.get("speed", 2.2))

    now_ms = pygame.time.get_ticks()

    # --- 起床待ち（最大でも 700ms） ---
    st["wake_at_ms"] = now_ms + 700

    # --- 捕獲の無敵時間（移動は許可・捕獲のみ禁止） ---
    st["__chaser_safe_until"] = now_ms + 900   # 0.9s 程度に短縮／確定

    # --- 捕獲のクールダウン（0 で開始） ---
    st["cooldown_until"] = 0
    st["__catch_lock_until"] = 0

    # --- 経路ヘルパ初期化（必要なら） ---
    st["repath_at"] = 0

# ========================================================================

def _los_clear(x0, y0, x1, y1) -> bool:
    """x0,y0→x1,y1 に壁が無ければ True（px座標で簡易サンプリング）"""
    dx, dy = x1 - x0, y1 - y0
    dist = max(1.0, math.hypot(dx, dy))
    steps = int(dist // LOS_STEP_PX)
    if steps <= 1:
        return True
    sx, sy = dx / steps, dy / steps
    cx, cy = x0, y0
    for _ in range(steps):
        if is_wall(cx, cy, radius=6):  # 半径は小さめに
            return False
        cx += sx; cy += sy
    return True

def _a_star_next_step(layout, start_tile, goal_tile):
    """layout から壁/床を判定して A*。返すのは “startの次の1タイル” or None。"""
    W, H = len(layout[0]), len(layout)
    def passable(tx, ty):
        if not (0 <= tx < W and 0 <= ty < H): return False
        return layout[ty][tx] in ('.','E','<','>',' ')
    sx, sy = start_tile
    gx, gy = goal_tile
    if (sx, sy) == (gx, gy):
        return None
    # オープン/クローズ（リストで十分）
    open_list = [(0, sx, sy, None)]
    came = {}  # (x,y)->parent
    g = {(sx, sy): 0}
    # 4近傍
    NB = [(1,0),(-1,0),(0,1),(0,-1)]
    while open_list:
        open_list.sort(key=lambda e: e[0])  # f最小
        _, x, y, _ = open_list.pop(0)
        if (x, y) == (gx, gy):
            # 逆辿りで startの次の1歩を返す
            path = [(x,y)]
            while (x,y) in came:
                x,y = came[(x,y)]
                path.append((x,y))
            path.reverse()
            return path[1] if len(path) >= 2 else None
        for dx,dy in NB:
            nx, ny = x+dx, y+dy
            if not passable(nx, ny): continue
            ng = g[(x,y)] + 1
            if ng < g.get((nx,ny), 1e9):
                g[(nx,ny)] = ng
                # ヒューリスティック：マンハッタン🗽
                h = abs(nx-gx) + abs(ny-gy)
                f = ng + h
                came[(nx,ny)] = (x,y)
                open_list.append((f, nx, ny, (x,y)))
    return None

def _ensure_special_ready_for_current_map(verbose: bool = False) -> None:
    """
    現在マップの special を一度だけ構築して
    game_state.current_textures['special'] に格納する。
    以降は同じマップでは何もしない（超重要）。
    """
    from core.maps import MAPS
    cur_map_id = getattr(game_state, "current_map_id", "")
    global _last_special_built_for_map
    if cur_map_id and cur_map_id == _last_special_built_for_map:
        return  # ← ここで早期return（重さの主因を断つ）

    mp = MAPS.get(cur_map_id, {})
    specials_source = ((mp.get("textures") or {}).get("special")) or {}

    # 画像のロードはこの1回だけ
    rebuilt = load_textures(BASE_DIR, {"textures": {"special": specials_source}}).get("special", {})

    if not isinstance(game_state.current_textures, dict):
        game_state.current_textures = {}
    # 万一文字列が混入しても弾く
    game_state.current_textures["special"] = {
        k: v for k, v in (rebuilt or {}).items() if isinstance(v, dict)
    }

    # “未点灯に戻すため”のランタイム・ベースラインを保存（a/b/c/d だけで十分）
    game_state.state.setdefault("_special_rt_baseline", {})[cur_map_id] = {
        k: game_state.current_textures["special"].get(k)
        for k in ("a", "b", "c", "d")
    }

    _last_special_built_for_map = cur_map_id
    if verbose:
        print(f"[special] built once for map={cur_map_id}")

def normalize_and_spawn_items_for_map(map_id: str) -> None:
    """
    MAPS[map_id]["items"] に
    - 新式: {"id","kind","name","pos"} 形式
    - 旧式: {"id","type","tile","picked"} 形式
    が混在してもOKにし、描画・拾得に必要な形式へ統一する。
    """
    m = MAPS[map_id]
    items = m.get("items", [])
    normalized = []
    for it in items:
        normalized.append(normalize_item_entry(it))
    # 正規化で置き換え
    m["items"] = normalized

def prepare_item_sprites_for_current_map(base_dir: Path) -> None:
    """
    現在マップに存在する item.type の画像をロードして
    game_state.current_textures["sprites"] に格納する。
    ★守人（guardian）はアイテムの有無に関わらず必ずロード。
    """
    sprites: dict[str, pygame.Surface] = {}
    # --- アイテム（ある分だけ） ---
    for raw in MAPS[game_state.current_map_id].get("items", []):
        it = normalize_item_entry(raw)
        key = it["type"]
        if key in sprites:
            continue
        meta = get_sprite_meta(key)
        rel = meta.get("file") or ""
        path = f"assets/sprites/{rel}" if rel and not rel.startswith("assets/") else rel

        short = "??"
        if key == "axe": short = "AX"
        elif key == "spirit_orb": short = "OR"
        elif key == "key_forest": short = "KY"

        surf = load_or_placeholder(base_dir, path or "", size=(64, 64), shape="circle", label=short)
        sprites[key] = surf

    # --- 固定スプライト（常時ロード） ---
    always = {
        "guardian": ("assets/textures/forest_guardian.png", "GU"),
        "fog":      ("assets/textures/forest_fog.png",      "FG"),
        "trunk":    ("assets/textures/forest_trunk.png",    "TR"),
    }
    for key, (path, label) in always.items():
        surf = load_or_placeholder(base_dir, path, size=(96, 96), shape="circle", label=label)
        sprites[key] = surf

    game_state.current_textures["sprites"] = sprites

def set_tile(layout, x, y, ch):
    """layout[y] の x 文字目を ch へ差し替える（文字列は不変なので作り直し）。"""
    row = layout[y]
    layout[y] = row[:x] + ch + row[x+1:]

def is_wall(x, y, radius=8):
    """
    ★ 壁衝突判定：縦横を正しく個別に判定（map_h/map_w）。
    x, y: プレイヤー中心座標（ピクセル）
    """
    layout = MAPS[game_state.current_map_id]["layout"]
    map_h = len(layout)
    for dx in [-radius, 0, radius]:
        for dy in [-radius, 0, radius]:
            tx = x + dx; ty = y + dy
            i = int(tx / TILE); j = int(ty / TILE)
            if 0 <= j < map_h and 0 <= i < len(layout[j]):
                ch = layout[j][i]
                walkable = TILE_TYPES.get(ch, {"walkable": False})["walkable"]
                if not walkable:
                    return True
            else:
                return True  # マップ外は壁扱い
    return False

def find_tile_pos(layout, symbol):
    for y, row in enumerate(layout):
        for x, ch in enumerate(row):
            if ch == symbol:
                return (x, y)
    return (1, 1)  # fallback

def blit_pill_label_midtop(
    surface: pygame.Surface,
    text: str,
    center_x: int,
    top_y: int,
    *,
    size: int = 16,
    text_color=(255, 255, 255),
    outline_color=(0, 0, 0),
    outline_px: int = 2,
    bg_rgba=(0, 0, 0, 170),
    pad_x: int = 8,
    pad_y: int = 4,
    radius: int = 6,
):
    """
    core/fonts.py の render_text() を用いて、
    アウトライン文字＋半透明の丸角ピル背景を描画（アンカー: midtop）。
    """
    # 文字（縁取りあり）を作成
    txt = render_text(
        text,
        size=size,
        color=text_color,
        shadow=False,           # 縁取りがあるので影は不要
        outline=True,
        outline_color=outline_color,
        outline_px=outline_px,
    )

    # ピル背景
    bg_w = txt.get_width() + pad_x * 2
    bg_h = txt.get_height() + pad_y * 2
    bg = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
    pygame.draw.rect(bg, bg_rgba, bg.get_rect(), border_radius=radius)
    bg.blit(txt, (pad_x, pad_y))

    # 位置（midtop基準）＆軽いクランプ
    x = int(center_x - bg_w // 2)
    y = int(top_y)
    x = max(0, min(x, surface.get_width() - bg_w))
    y = max(0, min(y, surface.get_height() - bg_h))
    surface.blit(bg, (x, y))

_GUIDE_COLORS = {"forward": (160, 230, 185, 220), "back": (235, 225, 160, 220)}# 前進＝淡緑、後退＝淡黄（PNGが無いときのプレースホルダー色）
_GUIDE_SURF_CACHE = {}   # キャッシュ {"forward": pygame.Surface, "back": pygame.Surface}

# =========================================================
# 風見鶏（マップ移動ガイド）アイコンのロード＆描画ヘルパ
# - “forward” : weathercock.png（進む方向の目印）
# - “back”    : weathercock_back.png（戻る方向の目印）
# - PNGが無い場合は、プレースホルダーの丸で代用
# ※ BASE_DIR を起点に assets/sprites/ を参照するので作業ディレクトリに非依存
# =========================================================

def _get_weathercock_surface(kind: str) -> pygame.Surface:
    """
    kind: "forward" or "back"
    1) 既にキャッシュ済みならそれを返す
    2) PNGを読めたら convert_alpha() 済みでキャッシュ
    3) 失敗したら色付き丸のプレースホルダーを生成してキャッシュ
    """
    if kind in _GUIDE_SURF_CACHE and _GUIDE_SURF_CACHE[kind]:
        return _GUIDE_SURF_CACHE[kind]

    # --- ファイル名の対応表 ---
    filename = "weathercock.png" if kind == "forward" else "weathercock_back.png"

    # BASE_DIR/assets/sprites/<filename>
    img_path = BASE_DIR / "assets" / "sprites" / filename

    surf: pygame.Surface | None = None
    try:
        if img_path.exists():
            img = pygame.image.load(str(img_path))
            # 画面生成後なら最適化（透過アルファ保持）
            if pygame.display.get_surface() is not None:
                img = img.convert_alpha()
            surf = img
    except Exception as e:
        print(f"[GUIDE] failed to load '{img_path}': {e}")

    if surf is None:
        # --- フォールバック（PNGが無い/読めない時）---
        # _GUIDE_COLORS は既存にある淡色（forward=淡緑 / back=淡黄）を使用
        rgba = _GUIDE_COLORS.get(kind, (200, 200, 200, 220))
        surf = pygame.Surface((48, 48), pygame.SRCALPHA)
        pygame.draw.circle(surf, rgba, (24, 24), 20)
        pygame.draw.circle(surf, (0, 0, 0, 180), (24, 24), 20, width=2)
        # 上向きの三角（簡易方位マーク）
        pygame.draw.polygon(
            surf, (255, 255, 255, 230),
            [(24, 6), (34, 24), (14, 24)]
        )

    _GUIDE_SURF_CACHE[kind] = surf
    return surf

def draw_weathercock_guides(screen: pygame.Surface, zbuf: list[float | None]) -> None:
    """
    現在マップに含まれる '>'（forward） と '<'（back） の座標へ、
    風見鶏アイコンをビルボード投影で描画する。
    - Zバッファで壁に隠れる列は描かない（透け防止）
    - 上下サイン波でゆっくり浮遊（他アイテムと同様の見た目）
    """
    cur_map = MAPS[game_state.current_map_id]
    pts_by_kind = _collect_guide_points_for_map_bi(cur_map)  # {"forward":[(px,py)..],"back":[..]}

    # プレイヤー基準
    px, py = game_state.player_x, game_state.player_y
    pa = game_state.player_angle

    # 遠い→近いで描く（奥から手前へ）と半透明重なりが自然
    candidates: list[tuple[str, float, float, float, float]] = []  # (kind, wx, wy, perp, diff)

    tan_half = math.tan(FOV * 0.5)
    fov_margin = 0.2

    for kind in ("forward", "back"):
        for (wx, wy) in pts_by_kind.get(kind, []):
            dx, dy = wx - px, wy - py
            dist = math.hypot(dx, dy)
            if dist < 1e-3:
                continue
            angle_to = math.atan2(dy, dx)
            diff = (angle_to - pa + math.pi) % (2 * math.pi) - math.pi
            if abs(diff) > (FOV * 0.5 + fov_margin):
                continue
            perp = dist * math.cos(diff)
            if perp <= 0:
                continue
            candidates.append((kind, wx, wy, perp, diff))

    # 遠い→近い（perp降順）
    candidates.sort(key=lambda t: t[3], reverse=True)

    # --- 浮遊アニメ（上下サイン波） ---
    # ・周期 1.6秒程度、振幅 6px（必要なら他アイテムに揃えてください）
    ticks = pygame.time.get_ticks()
    t = (ticks % 1600) / 1600.0 * (2 * math.pi)         # 0～2π
    bob_offset = int(math.sin(t) * 6)                   # -6 ～ +6

    for (kind, wx, wy, perp, diff) in candidates:
        base_surf = _get_weathercock_surface(kind)
        if base_surf is None:
            continue

        # --- 画面上のサイズ計算（壁と整合）---
        raw_h = (TILE * 500) / (perp + 1e-6)
        target_h = int(min(raw_h * 0.9, HEIGHT * 2))
        if target_h <= 1:
            continue
        aspect = base_surf.get_width() / max(1, base_surf.get_height())
        target_w = max(1, int(target_h * aspect))

        # 角度→スクリーンX
        sx_center = int((WIDTH / 2) * (1 + (math.tan(diff) / tan_half)))

        # 上下位置（中央基準に少し下寄せ＋浮遊）
        y_top  = (HEIGHT // 2) - (target_h // 2) + int(TILE * 0.2) + bob_offset

        # スケール済みキャッシュ
        cache_key = (f"weathercock_{kind}", target_h)
        scaled = game_state.sprite_scale_cache.get(cache_key)
        if scaled is None:
            scaled = pygame.transform.smoothscale(base_surf, (target_w, target_h))
            game_state.sprite_scale_cache[cache_key] = scaled

        # 画面外は軽くスキップ（横方向）
        x_left = sx_center - target_w // 2
        x_right = x_left + target_w
        if x_left >= WIDTH or x_right <= 0:
            continue

        # ======== ここから Zバッファによる遮蔽（透け防止）========
        # スプライトの列ごとに、該当スクリーンXの zbuf と perp を比較し、
        # 壁の方が手前（zbuf[x] < perp）ならその列は描かない。
        # ※ 1px幅で blit(area=...) するコストは低スプライト数なら許容範囲
        # ===========================================================
        src_rect_full = scaled.get_rect()
        # クリッピング（画面内に限定）
        draw_x0 = max(0, x_left)
        draw_x1 = min(WIDTH, x_right)

        # 1px 列ごとに描画
        for screen_x in range(draw_x0, draw_x1):
            # この列に対応するスプライト内X
            col_in_sprite = screen_x - x_left
            # Zバッファ：None（空き）や 0/負値 は「遮蔽なし」とみなす
            zb = zbuf[screen_x]
            if zb is not None and zb > 0 and zb < perp:
                # 壁が手前 → この列は描かない
                continue

            # 列（1px 幅）をブリット
            area = pygame.Rect(col_in_sprite, 0, 1, target_h)
            # 画面縦のクリッピング
            if y_top >= HEIGHT or (y_top + target_h) <= 0:
                continue
            screen.blit(scaled, (screen_x, y_top), area)

def _collect_guide_points_for_map_bi(cur_map: dict) -> dict[str, list[tuple[float,float]]]:
    """
    { "forward": [...], "back": [...] } を返す二方向版。
    - '>' を forward、'<' を back
    """
    layout = cur_map["layout"]
    result = {"forward": [], "back": []}
    for y, row in enumerate(layout):
        for x, ch in enumerate(row):
            if ch == '>':
                result["forward"].append((x*TILE + TILE*0.5, y*TILE + TILE*0.5))
            elif ch == '<':
                result["back"].append((x*TILE + TILE*0.5, y*TILE + TILE*0.5))
    return result

# === 守人など“固定物の見た目”をスプライトとして管理 ====================
if not hasattr(game_state, "world_sprites"):
    # { map_id: [ { "key":"guardian", "tile":(x,y) }, ... ] }
    game_state.world_sprites = {}

# --- 霧クリアの共通ユーティリティ ---
def clear_fog_all(layout: list[str], symbols: tuple[str, ...] = ('F', 'f')) -> tuple[int, int]:
    """
    霧タイル（デフォルト: 'F','f'）をマップ全体から床('.')へ一括置換します。
    戻り値: (置換前の個数合計, 置換後の個数合計)  ※デバッグログ用
    """
    # 事前カウント（デバッグ・検証）
    before = sum(r.count(s) for s in symbols for r in layout)

    # 高速・安全な全行置換
    # 文字列は不変なので1行ずつ新しい文字列を作って置換します。
    for y, row in enumerate(layout):
        for s in symbols:
            row = row.replace(s, '.')
        layout[y] = row

    # 事後カウント（正常なら 0 になります）
    after = sum(r.count(s) for s in symbols for r in layout)
    return before, after

def _apply_fog_state_for_map(map_id: str) -> None:
    """
    霧の現在状態を、(A) 原本レイアウト と (B) FLAGS['fog_cleared'] に基づいて layout に反映する。
    - クリア済み: 'F'/'f' を '.' に置換（= 霧なし）
    - 未クリア  : 原本に 'F'/'f' が立っているセルだけ、現行レイアウトに“霧を差し戻し”
    ※ ドア開閉など他の改変は触らない（安全に霧だけ同期）。
    """
    cur_map = MAPS[map_id]
    base_rows = cur_map.get("_layout_base")
    if not base_rows:
        return  # 念のため

    layout = cur_map["layout"]
    cleared = game_state.FLAGS.get("fog_cleared", set())

    # 1) クリア済み → 霧を消す（置換）
    if map_id in cleared:
        for y, row in enumerate(layout):
            # 行に霧があるときだけ置換（軽い最適化）
            if ('F' in row) or ('f' in row):
                layout[y] = row.replace('F', '.').replace('f', '.')
        return

    # 2) 未クリア → 原本の霧だけを現行に差し戻す（他の改変を壊さない）
    new_rows = []
    for y, row in enumerate(layout):
        base_row = base_rows[y]
        if ('F' not in base_row) and ('f' not in base_row):
            # 原本に霧がなければ現行行をそのまま採用
            new_rows.append(row)
            continue

        # 原本に霧がある座標だけ、現行に霧を戻す
        rlist = list(row)
        for x, ch_base in enumerate(base_row):
            if ch_base in ('F', 'f'):
                rlist[x] = ch_base
        new_rows.append(''.join(rlist))

    cur_map["layout"] = new_rows

def _apply_guardian_state_for_map(map_id: str) -> None:
    """
    守人 'M' の現在状態を (A) 原本レイアウト と (B) FLAGS['fog_cleared'] に基づいて layout に反映する。
    - 霧クリア済み: 'M' を '.' に置換（= 守人いない）
    - 未クリア    : 原本に 'M' が立っているセルだけ、現行レイアウトに “M を差し戻し”
    他の改変（ドア等）は触らない。
    """
    cur_map = MAPS[map_id]
    base_rows = cur_map.get("_layout_base")
    if not base_rows:
        return

    layout = cur_map["layout"]
    cleared = game_state.FLAGS.get("fog_cleared", set())

    if map_id in cleared:
        # 守人を消す（念のため行ごとに置換）
        for y, row in enumerate(layout):
            if 'M' in row:
                layout[y] = row.replace('M', '.')
        return

    # 未クリア: 原本に M がある座標だけ、現行に M を差し戻す
    new_rows = []
    for y, row in enumerate(layout):
        base_row = base_rows[y]
        if 'M' not in base_row:
            new_rows.append(row)
            continue
        rlist = list(row)
        for x, ch_base in enumerate(base_row):
            if ch_base == 'M':
                rlist[x] = 'M'
        new_rows.append(''.join(rlist))
    cur_map["layout"] = new_rows

def _apply_doors_state_for_map(map_id: str) -> None:
    """開いたドアを '.' にする（原本で壁の場所のみ安全に床へ）"""
    cur_map = MAPS[map_id]
    base_rows = cur_map.get("_layout_base") or cur_map["layout"][:]
    layout = cur_map["layout"]
    opened = game_state.FLAGS.get("doors_opened", set())

    # このマップのドア座標集合を抽出
    opened_here = {(m, x, y) for (m, x, y) in opened if m == map_id}
    if not opened_here:
        return

    new_rows = list(layout)
    for _m, x, y in opened_here:
        if 0 <= y < len(base_rows) and 0 <= x < len(base_rows[y]):
            # 原本が“壁相当”だったところだけ床化（安全）
            ch = base_rows[y][x]
            walkable = TILE_TYPES.get(ch, {"walkable": False})["walkable"]
            if not walkable:
                set_tile(new_rows, x, y, '.')
    cur_map["layout"] = new_rows

def _apply_trees_state_for_map(map_id: str) -> None:
    """
    倒した木（'O'）の周囲4方向で「連続する水 'w'」を探索し、
    “最も長いラン”に対して無条件で橋 'B' を敷設する。
    （従来の「水の先が床なら採用」条件を撤廃して頑健化）
    """
    cur_map = MAPS[map_id]
    layout = list(cur_map["layout"])
    chopped = game_state.FLAGS.get("trees_chopped", set())
    chopped_here = [(x, y) for (m, x, y) in chopped if m == map_id]
    if not chopped_here:
        return

    H = len(layout)
    W = len(layout[0]) if H else 0

    def _get(x, y):
        # 範囲外は「壁扱い」にしておくと処理が堅牢になる
        if 0 <= y < H and 0 <= x < W:
            return layout[y][x]
        return '#'

    def _set(x, y, ch):
        row = layout[y]
        layout[y] = row[:x] + ch + row[x+1:]

    for (x, y) in chopped_here:
        # 1) 倒木セルは床に（存在すれば）
        if _get(x, y) == 'O':
            _set(x, y, '.')

        # 2) 4方向の“水ラン”を調査（右・左・下・上）
        best_run = []
        best_dir = (0, 0)
        for dx, dy in ((1,0), (-1,0), (0,1), (0,-1)):
            cx, cy = x + dx, y + dy
            run = []
            while _get(cx, cy) == 'w':
                run.append((cx, cy))
                cx += dx; cy += dy
            if len(run) > len(best_run):
                best_run = run
                best_dir = (dx, dy)

        # 3) 最長ランに橋を敷設（ラン長が1以上ならOK）
        if best_run:
            for (bx, by) in best_run:
                _set(bx, by, 'B')
            if DEV_MODE:
                print(f"[TREE] bridge placed @ {map_id} from {(x,y)} dir={best_dir} len={len(best_run)}")
        else:
            # 近接に水が無い場合はメッセージ（設計上あり得る）
            if DEV_MODE:
                print(f"[TREE] no adjacent water to bridge @ {(x,y)} in {map_id}")

    cur_map["layout"] = layout

# スニペット（アプライヤ登録制）
APPLIERS = [
    _apply_fog_state_for_map,
    _apply_guardian_state_for_map,
    _apply_doors_state_for_map,
    _apply_trees_state_for_map,
]

def refresh_world_state():
    """全マップに “原本×フラグ” を適用して現行レイアウトを再合成"""
    for mid in MAPS.keys():
        for fn in APPLIERS:
            fn(mid)
    cur_map = MAPS[game_state.current_map_id]
    game_state.current_tile_grid = build_tile_grid(cur_map["layout"])
    # special の最終見た目を念のため同期
    try:
        _apply_switch_lit_from_flags(game_state.current_map_id)
    except Exception:
        pass
    game_state.refresh_world_state = refresh_world_state

def _check_map_triggers_at_current_tile():
    # === プロンプト多重発火と“遷移直後のEnter誤爆”対策 ===
    st = game_state.state
    # 1) すでにY/N表示中なら、ここでは再判定しない（ログ連打防止）
    if st.get("mode") == "map_confirm":
        return

    # 2) マップ遷移直後は、少しだけY/Nを出さない（キー誤爆防止）
    now = pygame.time.get_ticks()
    if now < st.get("__map_prompt_block_until", 0):
        return
    
def _check_proximity_triggers_from_map():
    """
    マップ/チェイサーブロック配下の proximity_triggers をマージして、近接発火させる正準版。
    近接条件: symbol_any / pos_tile / pos を順に判定。radius_px または radius_tile(タイル数)に対応。
    一度化: kind != 'video' は triggers_fired セットで抑止（動画はqueueに積む都合で別管理でもOK）。
    """
    cur_id = game_state.current_map_id
    cur_map = MAPS[cur_id]

    # トップレベル＋chaser配下をマージ
    trigs = list(cur_map.get("proximity_triggers") or [])
    ch_def = cur_map.get("chaser") or {}
    trigs += list(ch_def.get("proximity_triggers") or [])
    if not trigs:
        return

    px, py = game_state.player_x, game_state.player_y
    fired_set = game_state.FLAGS.setdefault("triggers_fired", set())

    def _near_symbol_any(sym_seq, r_px):
        return _player_near_any_symbol(tuple(sym_seq), float(r_px))

    def _near_pos_tile(tx, ty, r_px):
        cx, cy = _tile_center_px(tx, ty)
        dx, dy = (px - cx), (py - cy)
        return (dx*dx + dy*dy) <= (r_px * r_px)

    def _near_pos(tx, ty, r_px):
        cx, cy = _tile_center_px(tx, ty)   # タイル座標前提のため center を利用
        dx, dy = (px - cx), (py - cy)
        return (dx*dx + dy*dy) <= (r_px * r_px)

    for t in trigs:
        kind = t.get("kind", "video")  # 既定は video
        trig_name = t.get("id", "?")
        fired_key = f"{cur_id}:{kind}:{trig_name}"

        # --- 一度化制御（video以外は triggers_fired で管理）
        if kind != "video":
            if fired_key in game_state.FLAGS.setdefault("triggers_fired", set()):
                continue

        # --------- 近接判定（pos_tile / pos / symbol_any をサポート）---------
        near = False
        sym = t.get("symbol_any")
        if sym:
            r_px = float(t.get("radius_px", 96.0))
            near = _player_near_any_symbol(tuple(sym), r_px)

        if not near and ("pos_tile" in t):
            tx, ty = t.get("pos_tile", (0, 0))
            cx, cy = _tile_center_px(tx, ty)
            r_px = float(t.get("radius_px", t.get("radius_tile", 1.0) * TILE))
            dx, dy = (px - cx), (py - cy)
            near = (dx*dx + dy*dy) <= (r_px * r_px)

        if not near and ("pos" in t):
            tx, ty = t.get("pos", (0, 0))
            cx, cy = _tile_center_px(tx, ty)
            r_px = float(t.get("radius_px", t.get("radius_tile", 1.0) * TILE))
            dx, dy = (px - cx), (py - cy)
            near = (dx*dx + dy*dy) <= (r_px * r_px)

        if not near:
            continue

        # --------- 発火：種別ごと ---------
        if kind == "video":
            movie = t.get("movie") or ""
            if movie:
                # 相対指定なら assets/ を補う（安全側）
                if not movie.startswith("assets/"):
                    movie = "assets/" + movie
                play_inline_video(screen, BASE_DIR, movie, allow_skip=True, fade=False)
            # once_per_map 指定時は既存の「再生済み」管理に記録
            if t.get("once_per_map"):
                _mark_video_played(cur_id, trig_name)
            # 任意トースト
            if t.get("toast"):
                toast.show(t["toast"])
            continue

        # 追跡者スポーン
        if kind == "chaser_spawn":
            # 一度化
            game_state.FLAGS.setdefault("triggers_fired", set()).add(fired_key)

            # いま追跡BGMが鳴っていたかどうかを記録しておく
            ch_st = game_state.state.setdefault("chaser", {})
            had_chaser_bgm = bool(ch_st.get("__bgm_on"))

            # 1) （任意）ムービー
            mv = t.get("movie")
            if mv:
                if not mv.startswith("assets/"):
                    mv = "assets/" + mv
                # ここでムービー再生中に BGM がフェードアウトされる場合がある
                play_inline_video(screen, BASE_DIR, mv, allow_skip=True, fade=False)

                # ★ もしムービー前に追跡BGMが鳴っていたなら、
                #    フラグを一度リセットして「再スタート可能」にしておく。
                #    （ムービー内部でBGMが止まっても、__bgm_on が True のままだと
                #     _start_chaser_bgm_if_needed() が再生をスキップしてしまうため）
                if had_chaser_bgm:
                    ch_st["__bgm_on"] = False

            # 2) スポーン：プレイヤー正面 少し離れた所に出現
            _spawn_chaser_behind(distance_px=120.0)  # 間合いはお好みで

            # プレイヤーを 180 度振り向かせる
            game_state.player_angle = (game_state.player_angle + math.pi) % (2 * math.pi)

            # 3) （任意）トースト
            if t.get("toast"):
                toast.show(t["toast"])
            continue

# === 可視レイヤの最終適用ラッパー（冪等） =========================
def apply_visual_pipeline_final(map_id: str) -> None:
    """
    ワールド再構成の“最後に必ず1回だけ”呼ぶ。
    - X↔'.' の復元や *_lit の参照付け替え “後” に可視レイヤを上書きする。
    - 将来、足跡や毒沼などが増えてもここに追記するだけで順序事故を防げる。
    順序の意図:
      1) 倒木（trees_chopped）: 橋 'B' を敷設 → 壁復元に潰されないよう最後に当てる
      2) 霧（fog）            : 'F'/'f' を '.' に（見た目の最終勝ち）
      3) 守人（guardian）     : 'M' の消去など（※必要な場合）
      ※ ドア/スイッチは save_system 側で “復元→参照付け替え” 済み。
         ただし安全側で、ここでもドア反映を冪等適用して上書き事故を防ぐ。      
    """
    try:
        # ★セーフティ：ドア開放（FLAGS['doors_opened']）の再適用
        #  - 何度適用しても '.' への書き換えなので副作用はありません。
        from core.save_system import _apply_doors_opened_from_flags
        _apply_doors_opened_from_flags(map_id)
        # --- 可視レイヤの当て直し（何度呼んでも同じ結果） ---
        _apply_trees_state_for_map(map_id)      # 橋 'B' の敷設（trees_chopped を反映）
        _apply_fog_state_for_map(map_id)        # 霧の消去（fog_cleared を反映）
        _apply_guardian_state_for_map(map_id)   # 守人の消去

        # --- グリッド/スプライトの再構築（衝突＆見た目の整合） ---
        game_state.current_tile_grid = build_tile_grid(MAPS[map_id]["layout"])
        build_world_sprites_for_map(map_id)

    except Exception:
        # ゲーム停止を避けるため丸ごとガード
        pass

# ==============================
# 追跡者スプライト・ローダ
# ==============================

# グローバルに保持するフレーム
CHASER_FRAMES: list[pygame.Surface] = []
# アニメ速度（1秒あたりのコマ数）
CHASER_ANIM_FPS: int = 12

def _detect_base_dir() -> str:
    """
    BASE_DIR が既にグローバルにあるならそれを使い、
    無ければこのファイルの場所を基準とする安全なベースディレクトリを返す。
    """
    if "BASE_DIR" in globals():
        return globals()["BASE_DIR"]
    # __file__ が使える前提の安全策
    return os.path.dirname(os.path.abspath(__file__))

# ==============================
# 追跡者アニメーションの状態（グローバル）
# ==============================
CHASER_CUR_INDEX: int = 0               # 現在のフレーム番号
CHASER_LAST_ADV_MS: int = 0             # 最後にフレームを進めた時刻(ms)
CHASER_FRAME_DURATION: int = 0          # 1コマの表示時間(ms)

def init_chaser_anim_timing() -> None:
    """
    1コマの表示時間などのタイミングを初期化する。
    pygame.display.set_mode 後、load_chaser_frames 後に呼ぶと安全。
    """
    global CHASER_FRAME_DURATION, CHASER_LAST_ADV_MS, CHASER_CUR_INDEX
    # 1000ms / FPS = 1コマ当たりの時間
    CHASER_FRAME_DURATION = max(1, int(1000 / max(1, CHASER_ANIM_FPS)))
    CHASER_LAST_ADV_MS = pygame.time.get_ticks()
    CHASER_CUR_INDEX = 0

def update_chaser_anim() -> None:
    """
    追跡者アニメのフレームを進める（中央集権管理）。
    メインループの毎フレームで呼び出してください。
    """
    global CHASER_CUR_INDEX, CHASER_LAST_ADV_MS
    if not CHASER_FRAMES:
        return
    now = pygame.time.get_ticks()
    # 最後に進めてから frame_duration 経過していたら次フレームへ
    if now - CHASER_LAST_ADV_MS >= CHASER_FRAME_DURATION:
        CHASER_CUR_INDEX = (CHASER_CUR_INDEX + 1) % len(CHASER_FRAMES)
        CHASER_LAST_ADV_MS = now

def get_chaser_frame_current() -> pygame.Surface:
    if not CHASER_FRAMES:
        print("[CHASER][WARN] CHASER_FRAMES is empty at draw-time")
        surf = pygame.Surface((64, 64), pygame.SRCALPHA)
        pygame.draw.circle(surf, (220, 40, 40), (32, 32), 22)
        return surf
    return CHASER_FRAMES[CHASER_CUR_INDEX]

# =========================================================
# 【暫定対策】作業ディレクトリを BASE_DIR に固定する
# ※ 旧式の相対パス "assets/..." を一時的に救うため
# =========================================================
try:
    os.chdir(BASE_DIR)  # これで "assets/..." 参照がスクリプト直下を向く
    print(f"[WD] chdir to {BASE_DIR}")
except Exception as e:
    print(f"[WD] chdir failed: {e}")

CHASER_FRAMES: list[pygame.Surface] = []  

def load_chaser_frames(count: int = 6, base_dir: Optional[str] = None) -> None:
    """
    追跡者の歩行フレームをロード。
    【重要】CHASER_FRAMES を再代入せず、内容だけ更新します。
    """
    CHASER_FRAMES.clear()  # 既存リストを空にする（参照は保たれる）

    root = base_dir or _detect_base_dir()
    sprite_dir = os.path.join(root, "assets", "sprites", "chaser")
    display_ready = (pygame.display.get_surface() is not None)

    loaded = 0
    for i in range(count):
        path = os.path.join(sprite_dir, f"walk_{i}.png")
        print(f"[CHASER] load: {path}")
        if not os.path.exists(path):
            print(f"[WARN] missing chaser frame: {path}")
            continue
        try:
            img = pygame.image.load(path)
            if display_ready:
                img = img.convert_alpha()
            CHASER_FRAMES.append(img)   # ← 既存リストに詰める
            loaded += 1
        except Exception as e:
            print(f"[ERR] failed to load {path}: {e}")

    if not CHASER_FRAMES:
        print("[WARN] no chaser frames loaded. using red-circle fallback.")
        for _ in range(max(1, count)):
            surf = pygame.Surface((64, 64), pygame.SRCALPHA)
            pygame.draw.circle(surf, (220, 40, 40), (32, 32), 22)
            CHASER_FRAMES.append(surf)

    print(f"[CHASER] frames after load: {len(CHASER_FRAMES)} (requested {count}, loaded {loaded})")

# -------------------------------
# Pygame初期化
# -------------------------------
pygame.init()

# ウィンドウのタイトル（タスクバーに表示される文字列）を設定
# ※ 上で定義した GAME_TITLE をそのまま使います
pygame.display.set_caption(GAME_TITLE)

# フルスクリーン状態フラグ
# ・False … 通常ウィンドウ
# ・True  … フルスクリーン（論理解像度は WIDTH×HEIGHT のまま）
IS_FULLSCREEN: bool = False

# 最初は通常ウィンドウで画面を作成
screen = pygame.display.set_mode((WIDTH, HEIGHT))

# ウィンドウアイコンを変更する
try:
    icon_path = BASE_DIR / "assets" / "sprites" / "window_icon.png"
    if icon_path.exists():
        icon_surf = pygame.image.load(str(icon_path)).convert_alpha()
        pygame.display.set_icon(icon_surf)
except Exception as e:
    print(f"[WARN] failed to set window icon: {e}")

def post_convert_chaser_frames_alpha() -> None:
    """
    display 初期化後 or フルスクリーン切り替え後に、
    追跡者スプライトを現在の display に最適化し直す。

    ・pygame.display.toggle_fullscreen() は通常、
      Surface の再生成は行いませんが、
      もし内部フォーマットが変わった場合もカバーできるように
      念のため毎回 convert_alpha をかけ直しておきます。
    """
    if pygame.display.get_surface() is None:
        return

    global CHASER_FRAMES
    for i in range(len(CHASER_FRAMES)):
        # すでに SRCALPHA の Surface でも、convert_alpha で
        # 現在の display に最適化されます。
        CHASER_FRAMES[i] = CHASER_FRAMES[i].convert_alpha()

def toggle_fullscreen() -> bool:
    """
    フルスクリーンの ON/OFF を切り替える。

    ・pygame.display.toggle_fullscreen() を利用して、
      SDL 側にモード切り替えを任せます。
    ・WIDTH×HEIGHT の論理解像度はそのまま維持されます。
    ・戻り値は「切り替え後の状態」（True=フルスクリーン / False=ウィンドウ）。
    """
    global IS_FULLSCREEN

    try:
        # SDL にフルスクリーン切り替えを依頼
        # （ドライバや OS に応じて、アスペクト比維持＋黒帯 or 等倍拡大など
        #   よしなに調整されます）
        pygame.display.toggle_fullscreen()

        # SDL 側の状態を完全には信用できない環境もあるので、
        # 自前のフラグも反転させておく
        IS_FULLSCREEN = not IS_FULLSCREEN

        # display の内部状態が変わっている可能性を考えて、
        # 追跡者スプライトの convert_alpha をやり直す
        post_convert_chaser_frames_alpha()

        return IS_FULLSCREEN

    except pygame.error as e:
        # 何らかの理由で切り替えに失敗した場合は警告だけ出して、
        # ゲームは続行させる
        print(f"[WARN] failed to toggle fullscreen: {e}")
        return IS_FULLSCREEN

# --- サウンド初期化 ---
pygame.mixer.init()  # ★重要：これが無いとサウンドが鳴りません！詳しくはsound_manager.pyで
from core.sound_manager import SoundManager # 初期化の後にインポートこれ大事
# サウンドマネージャのインスタンスを作成
sound_manager = SoundManager(BASE_DIR / "assets" / "sounds")
print("[SE] loaded keys:", list(sound_manager.se.keys())[:20])
print("[SE] has tree_crash?:", sound_manager.has_se("tree_crash"))
# # お試しで直接音を鳴らす
# print("[SE] keys loaded:", list(sound_manager.se.keys()))  # => ["cursor","select",...]
# sound_manager.play_se("cursor")  # 起動直後にポンと鳴るはず（ボリューム確認にも有効）

# 画面作成の直後にフレームをロード
load_chaser_frames(count=6)  # 必要なら 8 や 10 に増やせます
post_convert_chaser_frames_alpha()   # 念のため最終変換
init_chaser_anim_timing()     # 1コマ時間の初期化
HALF_HEIGHT = HEIGHT // 2
clock = pygame.time.Clock()

# ★ 将来の最適化用：スケール済みSurfaceのキャッシュ（キー: (item_key, target_h_px)）
if not hasattr(game_state, "sprite_scale_cache"):
    game_state.sprite_scale_cache = {} 

# ★ アウトライン（縁取り）Surfaceのキャッシュ
#   キー: (item_key, target_h, outline_rgba)
if not hasattr(game_state, "sprite_outline_cache"):
    game_state.sprite_outline_cache = {}  

# === 守人など“固定物の見た目”をスプライトとして登録 =================
if not hasattr(game_state, "world_sprites"):
    # { map_id: [ { "key":"guardian", "tile":(x,y) }, ... ] }
    game_state.world_sprites = {}

# マップ定義の置き場所ミスを検出する簡易チェック（デバック用）
for mid, m in MAPS.items():
    tex = m.get("textures", {})
    if "wall_special" not in tex and "wall_special" in m:
        print(f"[WARN] {mid}: 'wall_special' は 'textures' の下に移してください。現在はトップレベルにあります。")

# （補助）save_system 側へトーストをブリッジするヘルパ
def _bridge_save_system_toast() -> None:
    """
    ToastManager が初期化された“後”に、save_system が参照できるよう
    game_state へブリッジする。
    """
    try:
        mgr = globals().get("toast") or globals().get("TOAST")
        if mgr is not None:
            game_state.toast = mgr
    except Exception:
        pass

# トーストの初期化（ここで必ず作成）
toast = ToastManager(default_ms=1200, size=20)

# =============================================================================
# WorldToastManager: タイル座標に紐づく“場所トースト”
#  - emit_label_for_tile(...) で「発火タイル」にラベルを貼る（見えなければ画面固定ピルへ）
#  - duration 経過で自動消滅
#  - ドア・スイッチ・アイテムの“その場で出るメッセージ”に最適
# =============================================================================
class WorldToastManager:
    """世界座標(タイル)に結びつくトースト。壁で隠れたら画面固定ピルにフォールバック。"""
    def __init__(self, default_ms: int = 1200):
        self.default_ms = int(default_ms)
        self._entries: list[dict] = []  # {map_id, tx, ty, text, until}

    def clear_tile(self, map_id: str, tile_xy: tuple[int, int]) -> None:
        """指定タイルに結びついた“場所トースト”を即時クリアする。"""
        tx, ty = int(tile_xy[0]), int(tile_xy[1])
        self._entries = [
            e for e in self._entries
            if not (e.get("map_id") == map_id and e.get("tx") == tx and e.get("ty") == ty)
        ]

    def show_at_tile(self, map_id: str, tile_xy: tuple[int,int], text: str, ms: int | None = None):
        dur = int(ms) if ms is not None else self.default_ms
        self._entries.append({
            "map_id": map_id,
            "tx": int(tile_xy[0]),
            "ty": int(tile_xy[1]),
            "text": text,
            "until": pygame.time.get_ticks() + dur,
        })

    def draw(self, screen: pygame.Surface, zbuf):
        """現在マップ上にある“場所トースト”を描画。見えなければ画面固定で出す。"""
        if not self._entries:
            return
        now = pygame.time.get_ticks()
        cur_map_id = game_state.current_map_id
        cur_map = MAPS[cur_map_id]
        layout = cur_map["layout"]

        alive: list[dict] = []
        for e in self._entries:
            if now > e["until"]:
                continue  # 期限切れで消滅
            if e["map_id"] != cur_map_id:
                alive.append(e)  # 別マップのものは保持（戻ってきた時に表示）
                continue
            tx, ty = e["tx"], e["ty"]
            text = e["text"]

            # 1) まず“世界貼り”：そのタイル位置に直接ラベルを貼る
            #    overlap_fracは見やすさ調整。ドア（壁）は少し大きめに(0.22)。
            drew = emit_label_for_tile(tx, ty, text, zbuf, overlap_frac=0.20)
            if not drew:
                # 2) 見えなかった（壁面などで遮蔽）→ 画面固定ピルで前面に出す（A案位置）
                blit_pill_label_midtop(screen, text, center_x=WIDTH//2, top_y=HEIGHT-86, size=16)

            alive.append(e)

        self._entries = alive

# インスタンス生成（下の描画フェーズで呼びます）
world_toast = WorldToastManager(default_ms=1200)

# save_system にブリッジ（ロード／メニュー経由どちらでも表示されるように）
_bridge_save_system_toast()

# save_system 以外（グローバル経由の発火など）も確実に UI へ出したいので、
# toast_bridge にも明示的に紐づけておく
from core import toast_bridge
toast_bridge.bind_toast(toast)

print(f"[INFO] DEV_MODE = {'ON' if DEV_MODE else 'OFF'}")
if DEV_MODE:
    toast.show("DEV_MODE: ON（Ctrl/⌘+F3 でデバッグ表示）")
# else:
#     toast.show("DEV_MODE: OFF（Ctrl/⌘+F3 は無効）")

# -----------------------------------------------------------------------------
# UI hint session (debounce) state
# - Prevent the same interaction label from sticking or re-appearing every frame
# - 同じヒントを出しっぱなし／踏むたびに点灯し続けるのを防ぐための小さな状態
# -----------------------------------------------------------------------------
_HINT_SESSION = {
    "key": None,           # (map_id, tx, ty, text) で一意化
    "until": 0,            # この時刻（ms）までは「表示期間」
    "inside": False,       # 近接中かどうか（離れたら False に戻す）
}

def _hint_session_should_draw(key: tuple[str,int,int,str]) -> bool:
    """Decide whether to draw an interaction hint this frame.
    同じ場所・同じ文言のヒントを、一度の接近で出しすぎないよう抑制します。"""
    now = pygame.time.get_ticks()
    cur_key = _HINT_SESSION.get("key")
    inside = _HINT_SESSION.get("inside", False)
    if key != cur_key or not inside:
        # 新規に近接した／いったん離れて再接近 → 表示を許可し、期限をセット
        _HINT_SESSION["key"] = key
        _HINT_SESSION["until"] = now + 1200   # 1.2s 程度が視認性と邪魔にならなさのバランス良
        _HINT_SESSION["inside"] = True
        return True
    # 近接継続中：期限が切れていたら表示しない（“出しっぱなし”回避）
    return now <= _HINT_SESSION.get("until", 0)

def _hint_session_left_proximity():
    """Call when no candidate is around (player moved away).
    候補がなくなった＝近接を抜けたらセッションをリセット。"""
    _HINT_SESSION["inside"] = False
    _HINT_SESSION["key"] = None
    _HINT_SESSION["until"] = 0

# --- フロア・天井描画用バッファ ---
floor_buffer = np.zeros((WIDTH, HEIGHT, 3), dtype=np.uint8)

def build_world_sprites_for_map(map_id: str) -> None:
    """
    マップのレイアウトから“固定オブジェクトの見た目”スプライトを登録する。
    - M : 守人 (guardian)   [非walkable / スプライト描画]
    - F : 霧   (fog)        [非walkable / スプライト描画]
    - O : 大木 (trunk)      [非walkable / スプライト描画]
    """
    m = MAPS[map_id]
    layout = m["layout"]
    entries = []

    for y, row in enumerate(layout):
        for x, ch in enumerate(row):
            if ch == 'M':
                entries.append({"key": "guardian", "tile": (x, y)})
            elif ch in ('F', 'f'):
                entries.append({"key": "fog", "tile": (x, y)})
            elif ch == 'O':
                entries.append({"key": "trunk", "tile": (x, y)})

    game_state.world_sprites[map_id] = entries

def draw_world_sprites(zbuffer: np.ndarray):
    """
    守人など“拾えない固定物”の見た目を、半透明対応のスプライトで描く。
    （当たり判定は 'M' のまま）

    追加の自己修復:
      - レイアウトに 'M' があるのに world_sprites が未構築/空なら即時再構築
      - guardian 画像が未ロードならスプライト読み込み処理を呼んで埋め直す
    """
    # --- : その場自己修復 -----------------------------------------------
    cur_id = game_state.current_map_id
    cur_map = MAPS[cur_id]
    # レイアウトに M/F/O が1つでもあるのに未構築なら再構築
    if not game_state.world_sprites.get(cur_id):
        if any(('M' in row) or ('F' in row) or ('O' in row) for row in cur_map["layout"]):
            build_world_sprites_for_map(cur_id)

    sprites_dict = game_state.current_textures.get("sprites", {})
    # 画像が無ければロード（必ずプレースホルダーが入る）
    need_keys = ("guardian", "fog", "trunk")
    if any(sprites_dict.get(k) is None for k in need_keys):
        prepare_item_sprites_for_current_map(BASE_DIR)
        sprites_dict = game_state.current_textures.get("sprites", {})

    # ------------------------------------------------------------------------

    arr = game_state.world_sprites.get(cur_id, [])
    if not arr:
        return

    px, py = game_state.player_x, game_state.player_y
    pa = game_state.player_angle
    tan_half_fov = math.tan(FOV * 0.5)

    cands = []
    for e in arr:
        tx, ty = e["tile"]
        wx, wy = tx * TILE + TILE * 0.5, ty * TILE + TILE * 0.5
        dx, dy = wx - px, wy - py
        dist = math.hypot(dx, dy)
        if dist < 1e-3:
            continue
        angle_to = math.atan2(dy, dx)
        diff = (angle_to - pa + math.pi) % (2 * math.pi) - math.pi
        if abs(diff) > (FOV * 0.5 + 0.2):
            continue
        perp = dist * math.cos(diff)
        if perp <= 0:
            continue
        cands.append((e, perp, diff))

    # 遠い→近い（奥から手前へ）
    cands.sort(key=lambda t: t[1], reverse=True)

    for e, perp, diff in cands:
        key = e.get("key", "guardian")
        base = sprites_dict.get(key)
        if base is None:
            continue

        meta = get_sprite_meta(key) or {}
        raw_h = (TILE * 500) / (perp + 1e-6)
        target_h = int(min(raw_h * float(meta.get("scale", 1.0)), HEIGHT * 2))
        if target_h <= 1:
            continue
        aspect = base.get_width() / max(1, base.get_height())
        target_w = max(1, int(target_h * aspect))
        y_offset = int(meta.get("y_offset_px", 0))

        # 画面X（-FOV..+FOV → 0..W）
        sx = int((WIDTH / 2) * (1 + (math.tan(diff) / tan_half_fov)))

        # ------- ここから “見た目アニメ” -------
        x_left = sx - target_w // 2
        y_top  = HALF_HEIGHT - (target_h // 2) + y_offset

        # 霧だけ、ふわふわ上下＋わずかな左右スway＋アルファの呼吸
        if key == "fog":
            t = pygame.time.get_ticks() * 0.001
            # タイル座標から位相を作って“同期ズレ”させる
            tx, ty = e["tile"]
            phase = (((tx * 73856093) ^ (ty * 19349663)) & 0xFFFF) / 65535.0 * 2 * math.pi

            # 上下：周期1.8s程度／高さの5〜7%くらい
            speed = (2 * math.pi) / 1.8
            amp   = max(2, int(target_h * 0.06))
            bob   = math.sin(t * speed + phase)              # -1..+1
            y_top -= int(bob * amp)

            # 左右：ごく小さく（幅の2%程度）
            sway = math.sin(t * speed * 0.7 + phase * 1.7)
            x_left += int(sway * max(1, target_w * 0.02))

            # アルファ：うっすら呼吸（120〜210）
            alpha = int(120 + 90 * (math.sin(t * 1.2 + phase * 0.6) + 1) * 0.5)

            scaled = pygame.transform.smoothscale(base, (target_w, target_h)).copy()
            # 透過の変化を乗算で適用
            scaled.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        else:
            # 守人・大木は従来どおり（静止）
            scaled = pygame.transform.smoothscale(base, (target_w, target_h))

        # ------- ここまで “見た目アニメ” -------

        # 画面外クリップ & Zバッファ
        x0 = max(0, x_left)
        x1 = min(WIDTH, x_left + target_w)
        for x in range(x0, x1):
            if perp < zbuffer[x] - 1e-4:
                sub = scaled.subsurface((x - x_left, 0, 1, target_h))
                screen.blit(sub, (x, y_top))

# -------------------------------
# 起動時の各種ロード（関数にまとめて明示）
# -------------------------------

# --- 初期ロード ---
# 診断（あれば）
if _run_maps_health_check:
    _run_maps_health_check(MAPS)

load_current_map_assets()

build_world_sprites_for_map(game_state.current_map_id) 

# ★ 起動シーケンス（タイトル/ムービー/イベント等）を一括実行
result = run_startup_sequence(screen, BASE_DIR, sound_manager=sound_manager)   # ← 返り値を受け取る
if result == "quit":
    pygame.quit()
    sys.exit(0)

# --- スイッチパズルの進行／点滅管理ステート ---
st = game_state.state
st.setdefault("switch_progress", [])         # いま押している順序（例: ['b','d']）
st.setdefault("switch_blink_active", set())  # 点滅対象のスイッチ集合（例: {'b','d'})
st.setdefault("switch_solved", False)        # クリア済み（封鎖解除済み）か
st.setdefault("last_tile_xy", None)
# --- 追跡者関連の安全制御 ---
st.setdefault("__chaser_safe_until", 0)      # スポーン直後の“捕獲無効”期間（ms）
st.setdefault("__chaser_cooldown_until", 0)  # 連続捕獲を防ぐクールダウン（ms）
st.setdefault("__caught_lock", False)        # 捕獲シーケンス中の再入防止

# マップ確認プロンプトのクールダウン用（ミリ秒の時刻を入れる）
st.setdefault("__map_prompt_block_until", 0)

# Eキーのデバウンス
last_use_ms = 0
USE_COOLDOWN = 250  # ms

PROMPT_COOLDOWN_MS = 800  # ms (好みで500〜1000に調整)

def check_map_triggers():
    """タイルをまたいだ瞬間に、旧/新どちらの方式でも発火させる。"""
    if game_state.state["mode"] != "normal":
        return

    # 直近で閉じたばかり等、クールダウン中は何もしない
    now = pygame.time.get_ticks()
    if now < game_state.state.get("__map_prompt_block_until", 0):
        return
    
    px = int(game_state.player_x // TILE)
    py = int(game_state.player_y // TILE)
    cur_id = game_state.current_map_id
    cur_map = MAPS[cur_id]
    layout = cur_map["layout"]

    # 範囲外は無視
    if not (0 <= py < len(layout) and 0 <= px < len(layout[0])):
        return

    tile = layout[py][px]
    tile_info = TILE_TYPES.get(tile, {"walkable": False, "event": None})
    event_id = tile_info.get("event")

    # --- 旧：triggers（安全に .get で空配列扱い）---
    def _has_played_cutscene(vp_raw, map_id: str, event_id: str) -> bool:
        # 1) Noneなら未再生
        if not vp_raw:
            return False
        # 2) listでもsetでも反復可能に
        try:
            iter(vp_raw)
        except Exception:
            return False
        # 3) まず「完全一致のタプル」を探す
        try:
            for e in vp_raw:
                # e が ('forest_end','doctor_gate') などのタプル/リスト
                if isinstance(e, (tuple, list)) and len(e) >= 2:
                    if str(e[0]) == str(map_id) and str(e[1]) == str(event_id):
                        return True
        except Exception:
            pass
        # 4) 互換：文字列単体として event_id が入っているケース
        try:
            if event_id in vp_raw:
                return True
        except Exception:
            pass
        return False
        
    for trig in cur_map.get("triggers", []):
        if trig.get("pos") == (px, py) and trig.get("event") == event_id:
            #   forest_end の「屋敷入り風見鶏」は
            #   ドクターゲートのイベントが終わっていない間は無効化する
            #   - DOCTOR_EVENT_ID は cinematics 側と共通のID
            if (
                cur_id == "forest_end"
                and trig.get("event") == "stair_down"
                and trig.get("target_map") == "lab_entrance"
            ):
                # ▼ doctorゲート未消化ならロック
                vp_raw = game_state.FLAGS.get("videos_played") or set()
                played = _has_played_cutscene(vp_raw, "forest_end", DOCTOR_EVENT_ID)
                print(f"[TRIG] check doctor_gate: played={played}  raw={type(vp_raw).__name__} size={len(vp_raw) if hasattr(vp_raw,'__len__') else 'NA'}")
                if not cin_has_played("forest_end", DOCTOR_EVENT_ID):
                    try:
                        toast.show("まだ中には入れない……。")
                    except Exception:
                        print("[TRIG] forest_end stair_down is locked until doctor event is finished")
                    return  # 早期リターンで map_confirm に入らない
                            
            game_state.state["mode"] = "map_confirm"
            game_state.state["pending_trigger"] = trig

            # ★効果音（読み込み済み想定: 'cursor'）
            try:
                sound_manager.play_se("cursor")
            except Exception:
                pass
            print(f"イベント:{event_id} 発生！（Y/Nで選択）")
            return

    # --- 新：'>' + suggested_exit（踏むだけで Y/N を出す）---これ動いてないかも？
    if tile == '>' and cur_map.get("suggested_exit"):
        from core.interactions import try_use_exit
        msg = try_use_exit(cur_id, cur_map)
        if msg:
            # ★ここで確認トーストが出たことを合図にSEを鳴らす
            try:
                sound_manager.play_se("cursor")
            except Exception:
                pass
            print(msg)
            return

    # === ★ Eタイルでエンディングへ（dungeon_2 限定 / 一度化）===================
    # ・「一度だけ」発火させたいので、game_state.FLAGS['triggers_fired'] にキーを記録
    # ・実行は scenes/ending_event.py の run_ending_sequence() に一本化
    if cur_id == "dungeon_2" and tile == 'E':
        fired = game_state.FLAGS.setdefault("triggers_fired", set())
        key = f"{cur_id}:ending:E_tile"
        if key not in fired:
            fired.add(key)
            try:
                # 遅延インポートで循環依存を回避しつつ、失敗時もゲーム継続
                from scenes.ending_event import run_ending_sequence
                # --- ▼▼▼ ここで必ず“足音・SE”を静音してから突入 ▼▼▼ ---
                try:
                    sound_manager.hush_effects_for_cutscene(fade_ms=120)
                except Exception:
                    pass
                # カットシーン・ガード（動画/演出中は新規の足音を発火させない）
                prev_cutscene = getattr(game_state, "is_cutscene", False)
                game_state.is_cutscene = True
                try:
                    # シナリオ行頭の BGM/SE/VOICE 指示を intro_event と同様に有効化する
                    run_ending_sequence(screen, BASE_DIR, sound_manager=sound_manager) # エンディングへ sound_manager を受け渡す。
                finally:
                    # 戻りで必ず解除し、万一の鳴り残しも消す
                    game_state.is_cutscene = prev_cutscene
                    try:
                        sound_manager.hush_effects_for_cutscene(fade_ms=120)
                    except Exception:
                        pass
                # ★ エンディングから戻ってきたらタイトルへ
                _return_to_title()
            except Exception as e:
                print(f"[WARN] ending sequence failed: {e}")
        return

# エンディング------------------------------------------------------------
_ENDING_SURF_CACHE: pygame.Surface | None = None

def _get_ending_symbol_surface() -> pygame.Surface:
    """
    エンディング用シンボル画像を返す。
    1) assets/sprites/ending_symbol.png があればそれを使用（convert_alpha）
    2) 無ければ紫の円＋白スターのフォールバックを生成
    """
    global _ENDING_SURF_CACHE
    if _ENDING_SURF_CACHE is not None:
        return _ENDING_SURF_CACHE

    img_path = BASE_DIR / "assets" / "sprites" / "ending_symbol.png"
    surf: pygame.Surface | None = None
    try:
        if img_path.exists():
            img = pygame.image.load(str(img_path))
            if pygame.display.get_surface() is not None:
                img = img.convert_alpha()
            surf = img
    except Exception as e:
        print(f"[ENDING_SYMBOL] failed to load '{img_path}': {e}")

    if surf is None:
        # --- フォールバック描画（紫の円＋白い星）---
        surf = pygame.Surface((56, 56), pygame.SRCALPHA)
        pygame.draw.circle(surf, (180, 120, 255, 230), (28, 28), 22)        # 円
        pygame.draw.circle(surf, (0, 0, 0, 160), (28, 28), 22, width=2)     # ふち
        # 簡易スター
        cx, cy, r = 28, 24, 10
        pts = []
        for i in range(10):
            ang = i * math.pi / 5.0
            rad = r if (i % 2 == 0) else r * 0.45
            pts.append((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
        pygame.draw.polygon(surf, (255,255,255,240), pts)
        pygame.draw.polygon(surf, (0,0,0,180), pts, width=1)
    _ENDING_SURF_CACHE = surf
    return surf

def _collect_end_points_for_map(cur_map: dict) -> list[tuple[float, float]]:
    """
    現在のマップから 'E' のタイル中心ワールド座標(px)を列挙。
    """
    pts: list[tuple[float, float]] = []
    layout = cur_map.get("layout", [])
    for ty, row in enumerate(layout):
        for tx, ch in enumerate(row):
            if ch == 'E':
                # タイル中心へ（既存実装に合わせて TILE(px) 基準）
                wx = (tx + 0.5) * TILE
                wy = (ty + 0.5) * TILE
                pts.append((wx, wy))
    return pts

def draw_ending_symbols(screen: pygame.Surface, zbuf: list[float | None]) -> None:
    """
    'E' タイル上にエンディング用シンボルを描画。
    - ビルボード投影（画面内FOVのみ）
    - Zバッファチェックで壁の裏側は描かない（透け防止）
      （壁列→zbufの列対応の取り方は、追跡者ビルボードの実装に準拠）
    - ゆっくり上下バウンドで視認性アップ
    """
    cur_map = MAPS[game_state.current_map_id]
    points = _collect_end_points_for_map(cur_map)
    if not points:
        return

    # プレイヤー基準
    px, py = game_state.player_x, game_state.player_y
    pa = game_state.player_angle
    W, H = screen.get_width(), screen.get_height()
    HALF_W = W * 0.5

    # 視野・投影用
    tan_half = math.tan(FOV * 0.5)
    dist_to_plane = (W / 2.0) / max(1e-6, tan_half)
    fov_margin = 0.20

    # スプライト画像（共通）
    sprite = _get_ending_symbol_surface()
    spr_w, spr_h = sprite.get_width(), sprite.get_height()

    # ふわふわ上下（垂直オフセット）
    t = pygame.time.get_ticks() / 1000.0
    bob_px = math.sin(t * 2.6) * (TILE * 0.08)   # お好みで 0.06～0.12

    # 遠い→近い（半透明重なりを自然に）
    candidates: list[tuple[float,float,float,float]] = []  # (wx,wy,perp,rel)
    for (wx, wy) in points:
        dx, dy = wx - px, wy - py
        dist = math.hypot(dx, dy)
        if dist < 1e-4:
            continue
        ang_to = math.atan2(dy, dx)
        rel = (ang_to - pa + math.pi) % (2 * math.pi) - math.pi
        if abs(rel) > (FOV * 0.5 + fov_margin):
            continue
        perp = dist * math.cos(rel)
        if perp <= 0:
            continue
        candidates.append((wx, wy, perp, rel))
    candidates.sort(key=lambda x: x[2], reverse=True)  # perp 降順

    for (wx, wy, perp, rel) in candidates:
        # 画面X座標（水平FOVの線形マッピング）
        screen_x = (rel / (FOV / 2.0)) * HALF_W + HALF_W
        # --- Zバッファの遮蔽チェック（追跡者ビルボードの実装に準拠） ---
        col = int(screen_x / max(1, W) * len(zbuf))
        col = max(0, min(col, len(zbuf) - 1))
        wall_d = zbuf[col]
        # 手前に壁がある & シンボルの方がさらに奥 → 描かない
        # （列→距離の比較ロジックは既存の敵スプライトと同様） 
        if wall_d is not None and wall_d > 0 and perp > wall_d:
            continue

        # 投影スケール：距離前方成分で安定させる
        cam_y = perp
        screen_h = int((TILE * 1.1) * (dist_to_plane / max(1e-6, cam_y))) # 大きくしたい場合はここを増やします。1.5倍のサイズ
        if screen_h <= 0:
            continue
        screen_w = int(spr_w * (screen_h / spr_h))

        # 足元Y：遠距離は透視で沈む、近距離は安定地面へ寄せる（軽いブレンド）
        # （係数は追跡者表示と同等感に）
        ground_y = H * 1.0 # 地面基準の高さ
        persp_y  = H * 0.5 + (TILE * 0.25) * (dist_to_plane / max(1e-6, cam_y))
        blend = max(0.0, min(1.0, perp / (TILE * 6.0)))   # 0〜6タイルで遷移
        mid_y = persp_y * blend + ground_y * (1.0 - blend) + bob_px

        # 描画（中央揃え）
        dest = pygame.Rect(0, 0, screen_w, screen_h)
        dest.centerx = int(screen_x)
        dest.bottom  = int(mid_y)
        screen.blit(pygame.transform.smoothscale(sprite, (dest.w, dest.h)), dest)


def _return_to_title() -> None:
    """
    エンドロール終了後にタイトルを表示し、選択に応じて遷移する。

    - 「Start」:
        すでにタイトルを一度表示しているので、ここでは
        タイトルを挟み直さずに「ムービー → イントロ」だけ実行して本編へ戻す。
    - 「Load」:
        起動時と同じロード専用メニュー（MenuScene）を開き、
        セーブスロットを選ばせてからロードする。
    """
    # ★ ここで「エンディングを一度クリアした」フラグを立てる
    #   - セーブには載せず、メモリ上だけで扱う
    try:
        setattr(game_state, "afterword_unlocked", True)
        print("[INFO] ending cleared: afterword menu unlocked for this session.")
    except Exception as e:
        print(f"[WARN] failed to set afterword_unlocked flag: {e}")

    try:
        # 遅延 import：
        #   - 循環依存の回避
        #   - テスト時など、一部シーンを読み込まない環境への配慮
        from scenes.title_scene import TitleScene
        from scenes.scene_manager import run_scene
        from scenes.startup import (
            run_newgame_sequence_without_title,
            _run_menu_as_modal_load,
        )
    except Exception as e:
        print(f"[WARN] cannot prepare title sequence after ending: {e}")
        return

    while True:
        # ------------------------------------------------------------------
        # 1) タイトル画面を表示して、プレイヤーの選択を受け取る
        #    - Start / Load / Quit などを想定
        # ------------------------------------------------------------------
        choice = run_scene(TitleScene(BASE_DIR, sound_manager=sound_manager), screen)

        # ------------------------------------------------------------------
        # 2) Start が選ばれた場合
        #    - すでにタイトルを一度見せているので、
        #      ここでは「ムービー → イントロ」だけを再生する。
        # ------------------------------------------------------------------
        if choice == "start":
            # ★ New Game 用のリセットを一括で実施
            try:
                # core.game_state はファイル先頭で
                #   import core.game_state as game_state
                # されています。
                game_state.reset_for_new_run()
                print("[INFO] reset_for_new_run() completed for new game after ending.")
            except Exception as e:
                # ここで失敗してもゲーム自体は続行できるようにしておく
                print(f"[WARN] reset_for_new_run failed: {e}")

            # そのうえで、ムービー→イントロだけを再生して本編へ
            try:
                run_newgame_sequence_without_title(
                    screen,
                    BASE_DIR,
                    sound_manager=sound_manager,
                )
            except Exception as e:
                print(f"[WARN] newgame sequence after ending failed: {e}")

            # ムービー→イントロ終了後は、そのまま本編ループへ復帰
            return

        # ★ Afterword（あとがき）が選ばれた場合
        elif choice == "afterword":
            try:
                from scenes.afterword import AfterwordScene
            except Exception as e:
                print(f"[WARN] cannot import AfterwordScene: {e}")
            else:
                try:
                    scene = AfterwordScene(BASE_DIR, sound_manager=sound_manager)
                    run_scene(scene, screen)
                except Exception as e:
                    print(f"[WARN] AfterwordScene execution failed: {e}")
            # あとがき終了後は、再びタイトル選択へ戻る
            continue
        
        # ------------------------------------------------------------------
        # 3) Load が選ばれた場合
        #    - 起動時のタイトルと同じロード専用メニューを開き、
        #      セーブスロットを選んでもらう。
        # ------------------------------------------------------------------
        elif choice == "load":
            try:
                loaded = _run_menu_as_modal_load(
                    screen,
                    BASE_DIR,
                    sound_manager=sound_manager,
                )
            except Exception as e:
                print(f"[WARN] cannot open load menu after ending: {e}")
                # ロードメニューが開けないときは、旧挙動（直 load_game）でフォールバック
                try:
                    load_game(BASE_DIR)
                    ensure_current_map_assets_synced(force=True)
                    on_world_rebuild_for_current_map()
                except Exception as e2:
                    print(f"[WARN] load_game failed (fallback): {e2}")
                return

            if loaded == "quit":
                # ロード画面側でウィンドウ×などが押されたケース
                print("[INFO] modal load menu requested quit after ending.")
                return

            if loaded is True:
                # ロード成功：
                # セーブデータから状態を復元したあとは、
                # マップや敵などの見た目を再構築して本編へ戻す
                ensure_current_map_assets_synced(force=True)
                on_world_rebuild_for_current_map()
                return

            # loaded が False の場合（Esc キャンセルなど）は、
            # もう一度タイトル画面に戻して選び直してもらう。
            continue

        # ------------------------------------------------------------------
        # 4) それ以外（将来的に Options 等を追加したときの保険）
        # ------------------------------------------------------------------
        else:
            print(f"[INFO] title choice={choice!r} (no action after ending)")
            return


def _cancel_confirm_if_moved_off_tile():
    """確認モード中に > から離れたら自動キャンセルする。"""
    if game_state.state.get("mode") != "map_confirm":
        return
    trig = game_state.state.get("pending_trigger") or {}
    pos = trig.get("pos")
    if not pos:
        return
    px = int(game_state.player_x // TILE)
    py = int(game_state.player_y // TILE)
    if (px, py) != tuple(pos):
        # そのタイルを踏んでいない＝キャンセル
        game_state.state["mode"] = "normal"
        game_state.state["pending_trigger"] = None

# --- 安全ヘルパー：wall_specialの値が Surface / {"surf": Surface} どちらでも受ける ---
def _resolve_wall_surface(wall_special: dict, symbol: str, default_surf):
    """
    wall_special[symbol] が:
      - pygame.Surface の場合 → それを返す
      - {"surf": pygame.Surface} の場合 → その "surf" を返す
      - それ以外/未定義 → default_surf を返す
    """
    ent = wall_special.get(symbol)
    # ① Surface 直返しのパターン
    if isinstance(ent, pygame.Surface):
        return ent
    # ② {"surf": Surface} の古いパターン
    if isinstance(ent, dict):
        s = ent.get("surf")
        if isinstance(s, pygame.Surface):
            return s
    # ③ 何も無ければデフォルト壁
    return default_surf

def draw_floor(angle_rad: float) -> None:
    """
    フロア/天井/特殊床（special）の逆投影描画。
    重要ポイント:
      - 床/天井が両方 None でも、special があれば描く（川や橋を消さない）
      - special は α合成（PNGの透明度を尊重）
      - floor_tex が無い場合は special を直接塗る（下地なしでも見える）
    """
    # ------------------------------
    # マップ情報の取得
    # ------------------------------
    layout = MAPS[game_state.current_map_id]["layout"]
    if not layout:  # レイアウトが空（想定外）の場合は何もしない
        return

    map_h = len(layout)
    map_w = len(layout[0])

    # 現在のテクスチャ群
    floor_tex = game_state.current_textures.get("floor_arr")     # (TILE, TILE, 3) or None
    ceil_tex  = game_state.current_textures.get("ceiling_arr")   # (TILE, TILE, 3) or None
    special   = game_state.current_textures.get("special", {})   # {symbol: {'arr':(H,W,3),'alpha':(H,W)}}

    # 床も天井もなく、special も無ければ描くものがないので早期リターン
    if floor_tex is None and ceil_tex is None and not special:
        return

    # ------------------------------
    # タイルグリッド（ASCII コード行列）
    #   - 旧版: tile_grid が None のときだけ build
    #   - 新版: マップサイズが変わったら作り直す安全対策あり
    # → ここでは「旧描画ロジック + 新安全対策」を採用
    # ------------------------------
    tile_grid = getattr(game_state, "current_tile_grid", None)
    if (
        tile_grid is None
        or tile_grid.shape[0] != map_h
        or tile_grid.shape[1] != map_w
    ):
        tile_grid = build_tile_grid(layout)
        game_state.current_tile_grid = tile_grid

    # 念のため、以降も tile_grid の実サイズを使う
    map_h, map_w = tile_grid.shape

    # ------------------------------
    # プレイヤー位置・視線ベクトル
    # ------------------------------
    # プレイヤー位置（タイル空間）
    px = game_state.player_x / TILE
    py = game_state.player_y / TILE

    # 視線ベクトルとスクリーン平面
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    dir_x, dir_y = cos_a, sin_a

    # FOV/2 の tan を使って視線に直交するスクリーン平面ベクトルを作る
    fov_half_tan = math.tan(FOV * 0.5)
    plane_x, plane_y = -sin_a * fov_half_tan, cos_a * fov_half_tan

    # 各画面 x 列用のインデックス
    xs = np.arange(WIDTH, dtype=np.float32)

    # バッファをゼロクリア (H, W, 3)
    floor_buffer.fill(0)
    EPS = 1e-3

    # TILE が 2 のべき乗ならビット AND で高速マスク
    fast_mask = (TILE & (TILE - 1)) == 0

    # =========================================================
    # 画面下半分: 床 + special
    # 画面上半分: 天井
    # =========================================================
    for y in range(HALF_HEIGHT, HEIGHT):
        # 画面中心からの相対行位置（0 が地平線）
        p = y - HEIGHT * 0.5
        if abs(p) < EPS:
            # 中央ラインは壁で完全に隠れるのでスキップ
            continue

        # スクリーン座標 → ワールドタイル空間への距離
        row_dist = (0.5 * HEIGHT) / p

        # 画面左端・右端に対応するレイ方向ベクトル
        ray0_x, ray0_y = dir_x - plane_x, dir_y - plane_y
        ray1_x, ray1_y = dir_x + plane_x, dir_y + plane_y

        # 1px 進むごとのワールド座標の変化量
        step_x = (row_dist * (ray1_x - ray0_x)) / WIDTH
        step_y = (row_dist * (ray1_y - ray0_y)) / WIDTH

        # 左端カラムに対応するワールド座標（タイル空間）
        wx0 = px + row_dist * ray0_x
        wy0 = py + row_dist * ray0_y

        # 全カラム分のワールド座標
        world_xs = wx0 + xs * step_x
        world_ys = wy0 + xs * step_y

        # ★ ここで「world_xs/world_ys が範囲外なら行ごと continue」
        #    というチェックを入れていたのが“黒く切れる”原因。
        #    遠距離ほど簡単にマップ外に出てしまうため、
        #    地平線付近の行が丸ごと描画されなくなっていた。
        #    → そのチェックは入れない。

        # タイルインデックス（floor: 切り捨て）
        ti = np.floor(world_xs).astype(np.int32)
        tj = np.floor(world_ys).astype(np.int32)

        # マップ範囲内だけを描画対象にするマスク
        inside = (tj >= 0) & (tj < map_h) & (ti >= 0) & (ti < map_w)
        if not inside.any():
            # この行ではマップが一切見えない（完全に外）なのでスキップ
            continue

        # タイル内の相対座標 [0, 1)
        fx = world_xs - np.floor(world_xs)
        fy = world_ys - np.floor(world_ys)

        # テクスチャ座標 (0..TILE-1)
        tx = (fx * TILE).astype(np.int32)
        ty = (fy * TILE).astype(np.int32)
        if fast_mask:
            tx &= (TILE - 1)
            ty &= (TILE - 1)
        else:
            tx %= TILE
            ty %= TILE

        # この y 行の floor_buffer へのビュー
        row_floor = floor_buffer[:, y]  # shape: (W, 3)
        idx = np.where(inside)[0]

        # -------------------------------------------------
        # 1) 床テクスチャ（ベース）
        # -------------------------------------------------
        if floor_tex is not None:
            # inside なカラムだけ床テクスチャを転送
            row_floor[idx] = floor_tex[ty[idx], tx[idx]]

        # -------------------------------------------------
        # 2) special（川/橋/床スイッチなど）を重ねる
        # -------------------------------------------------
        if special:
            # 今見えている列がどのタイル記号を指しているか
            tile_codes = np.zeros(WIDTH, dtype=np.uint8)
            tile_codes[idx] = tile_grid[tj[idx], ti[idx]]

            # 点滅制御（床スイッチ *_lit）
            now_ms = pygame.time.get_ticks()
            blink_on = (now_ms // 400) % 2 == 0
            blink_set = game_state.state.get("switch_blink_active", set())

            for symbol, entry in special.items():
                if not isinstance(entry, dict):
                    continue
                # '_lit' は点滅時に参照するので、ここではスキップ
                if len(symbol) != 1 or symbol.endswith("_lit"):
                    continue

                arr_normal = entry.get("arr")    # (TILE,TILE,3)
                alpha_n    = entry.get("alpha")  # (TILE,TILE) or None
                if arr_normal is None:
                    continue

                sym_code = ord(symbol)
                m = inside & (tile_codes == sym_code)
                if not m.any():
                    continue
                ii = np.where(m)[0]

                # デフォルトは通常版
                use_arr   = arr_normal
                use_alpha = alpha_n

                # 点滅 ON のときだけ lit 版に切り替え
                if (symbol in blink_set) and blink_on:
                    lit_entry = special.get(f"{symbol}_lit")
                    if lit_entry:
                        arr_lit   = lit_entry.get("arr")
                        alpha_lit = lit_entry.get("alpha")
                        if arr_lit is not None:
                            use_arr = arr_lit
                            # α情報が無ければ不透明 255 とみなす
                            if alpha_lit is not None:
                                use_alpha = alpha_lit
                            else:
                                use_alpha = np.full(
                                    (TILE, TILE), 255, dtype=np.uint8
                                )

                # special テクスチャのサンプリング
                sp = use_arr[ty[ii], tx[ii]]  # (#ii, 3)

                # ▼ 旧版と同じロジック
                #   - floor_tex がある + αがある → αブレンド
                #   - それ以外          → そのまま上書き（橋や川を確実に見せる）
                if floor_tex is not None and use_alpha is not None:
                    a = use_alpha[ty[ii], tx[ii]].astype(np.float32) / 255.0
                    base = row_floor[ii].astype(np.float32)
                    out = sp.astype(np.float32) * a[:, None] + base * (1.0 - a[:, None])
                    row_floor[ii] = out.astype(np.uint8)
                else:
                    row_floor[ii] = sp

        # -------------------------------------------------
        # 3) 天井（画面上半分にミラー描画）
        # -------------------------------------------------
        if ceil_tex is not None:
            y_top = HEIGHT - 1 - y
            row_ceil = floor_buffer[:, y_top]
            row_ceil[idx] = ceil_tex[ty[idx], tx[idx]]

    # ------------------------------
    # 最終的な floor_buffer を Surface にして blit
    # ------------------------------
    surf = pygame.surfarray.make_surface(floor_buffer)
    screen.blit(surf, (0, 0))

def _surf_to_arrays_for_special(surf: pygame.Surface, *, size: int) -> tuple[np.ndarray, np.ndarray]:
    """
    pygame.Surface(αあり) → special 用 (H,W,3) と α(H,W) のndarrayへ変換
    - size: タイル一辺（TILE）
    """
    s = pygame.transform.smoothscale(surf, (size, size)).convert_alpha()
    # RGB は (W,H,3) なので (H,W,3) に転置してから C 連続の uint8 に
    rgb = pygame.surfarray.array3d(s).swapaxes(0, 1)
    rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
    # ★重要★ Alpha は (W,H) のまま返るので (H,W) に転置してから連続化
    a = pygame.surfarray.array_alpha(s).swapaxes(0, 1)
    a = np.ascontiguousarray(a, dtype=np.uint8)
    return rgb, a

def draw_rays() -> np.ndarray:
    """
    壁のレイキャスティング描画。
    - 画面列ごとの最終的な「壁までの距離」を zbuffer[0..WIDTH-1] に格納して返す。
      → このZバッファでアイテム（スプライト）との前後関係を正しく処理できる。
    """
    layout = MAPS[game_state.current_map_id]["layout"]
    map_h = len(layout); map_w = len(layout[0])

    # 1) 先に床/天井
    draw_floor(game_state.player_angle)

    angle = game_state.player_angle
    px, py = game_state.player_x, game_state.player_y
    cur_angle = angle - FOV/2

    wall_default = game_state.current_textures["wall"]
    wall_special = game_state.current_textures.get("wall_special", {})

    # x座標→レイの区間境界（NUM_RAYS本）
    x_positions = [int(round(i * WIDTH / NUM_RAYS)) for i in range(NUM_RAYS + 1)]

    # ★Zバッファ（列ごとの壁距離）。初期は「非常に遠い」。
    zbuffer = np.full(WIDTH, 1e9, dtype=np.float32)

    for ray in range(NUM_RAYS):
        sin_a, cos_a = math.sin(cur_angle), math.cos(cur_angle)
        hit_x = 0
        # 初期値は「空間」を示す記号（dot）にしておくと無難
        hit_ch = '.'
        depth = 1

        for depth in range(1, MAX_DEPTH):
            x = px + depth * cos_a
            y = py + depth * sin_a
            i, j = int(x / TILE), int(y / TILE)

            if 0 <= j < map_h and 0 <= i < len(layout[j]):
                ch = layout[j][i]
                # draw_rays() の“壁ヒット検出”のところ
                walkable = TILE_TYPES.get(ch, {"walkable": False})["walkable"]
                if not walkable:
                    # ★ スプライトで描くオブジェクトは「壁にしない」＝素通り
                    if ch in ('M', 'F', 'O', 'w', 'B'):
                        continue
                    prev_x = px + (depth - 1) * cos_a
                    prev_y = py + (depth - 1) * sin_a
                    i_prev, j_prev = int(prev_x / TILE), int(prev_y / TILE)
                    hit_x = (y % TILE) if i_prev != i else (x % TILE)
                    hit_ch = ch
                    break

            else:
                # マップ外は壁扱い
                hit_x = 0
                hit_ch = '#'
                break

        # 垂直距離補正（魚眼補正）
        depth_perp = depth * math.cos(angle - cur_angle)
        wall_h = min((TILE * 500) / (depth_perp + 1e-6), HEIGHT)

        surf = _resolve_wall_surface(wall_special, hit_ch, wall_default)
        if surf:
            tex_w, tex_h = surf.get_width(), surf.get_height()
            tex_x = int(hit_x / TILE * tex_w) % tex_w
            column = surf.subsurface((tex_x, 0, 1, tex_h))
            x_screen = x_positions[ray]
            width_ray = x_positions[ray + 1] - x_screen
            if width_ray <= 0:
                cur_angle += DELTA_ANGLE
                continue

            column = pygame.transform.scale(column, (width_ray, int(wall_h)))
            screen.blit(column, (x_screen, HALF_HEIGHT - int(wall_h // 2)))

            # ★このレイが担当する画面x範囲に“壁までの距離（perp）”を埋める
            x0 = max(0, x_screen)
            x1 = min(WIDTH, x_screen + width_ray)
            if x0 < x1:
                # 多重書き込みがあっても最小値（より手前の壁）を保持
                zbuffer[x0:x1] = np.minimum(zbuffer[x0:x1], depth_perp)

        cur_angle += DELTA_ANGLE

    return zbuffer

def _is_unpicked_item(map_id: str, it: dict) -> bool:
    """
    ★“未取得だけ描く／拾える”ためのフィルタ関数。
    - MAPS の定義は不変に保ち、取得済みかどうかは FLAGS['picked_items'] で判定します。
    - it: {"id","type","tile",...} 形式（内部で正規化）
    """
    it = normalize_item_entry(it)  # 必ず正規化
    picked_set = game_state.FLAGS.get("picked_items", set())
    tx, ty = it["tile"]
    # id があれば個体識別に使う。無ければ type 名で代用（= その座標のその種類を1個体とみなす）
    uniq = it.get("id") or it.get("type")
    key = make_entity_key(map_id, "item", uniq, tx, ty)
    return key not in picked_set

def draw_items(zbuffer: np.ndarray):
    """
    アイテム（スプライト）を世界座標→画面座標に投影して描画。
      - ふわふわ上下アニメ（“浮遊”演出）
      - 影の楕円（床に“居る”実在感を補強）
      - アイテムごとに位相をずらし、全て同じタイミングで動かないようにする

      - FOV端に±0.2radのバッファ
      - perp_dist = dist * cos(angle_diff) によるスケール安定化
      - Zバッファ（列ごとの壁距離）より手前のみ描画
      - スケール済みキャッシュで負荷を抑制
    """
    sprites_dict = game_state.current_textures.get("sprites", {})
    if not sprites_dict:
        return

    px, py = game_state.player_x, game_state.player_y
    pa = game_state.player_angle

    # 画面中心→左右端までの「tan」比率（x投影用）
    tan_half_fov = math.tan(FOV * 0.5)
    fov_margin = 0.2  # ★FOV端の可視バッファ

    # --- アニメ用の時間（秒） ---
    t = pygame.time.get_ticks() * 0.001

    candidates = []
    for raw in MAPS[game_state.current_map_id].get("items", []):
        it = normalize_item_entry(raw)  # 毎回正規化
        if not _is_unpicked_item(game_state.current_map_id, it):
            continue

        # タイル中心（ピクセル）をスプライトのワールド座標とする
        tx, ty = it["tile"]
        wx = tx * TILE + TILE * 0.5
        wy = ty * TILE + TILE * 0.5

        dx = wx - px
        dy = wy - py
        dist = math.hypot(dx, dy)
        if dist < 1e-3:
            continue

        angle_to = math.atan2(dy, dx)
        # [-pi,pi] に正規化した差角
        angle_diff = (angle_to - pa + math.pi) % (2 * math.pi) - math.pi
        # FOV端±余白の可視判定
        if abs(angle_diff) > (FOV * 0.5 + fov_margin):
            continue

        perp_dist = dist * math.cos(angle_diff)  # ★正しいスケール用の垂直距離
        if perp_dist <= 0:
            continue  # 真後ろ（カメラ背面）

        candidates.append({
            "item": it,
            "wx": wx, "wy": wy,
            "dist": dist,
            "perp_dist": perp_dist,
            "angle_diff": angle_diff,
        })

    # 遠い→近い の順に描いて、あとから近い物で上書き（半透明の重なりに強い）
    candidates.sort(key=lambda d: d["perp_dist"], reverse=True)

    for c in candidates:
        it = c["item"]
        key = it["type"]
        meta = get_sprite_meta(key)
        base_surf = sprites_dict.get(key)  # 透過PNG推奨
        if base_surf is None:
            continue

        perp = c["perp_dist"]
        angle_diff = c["angle_diff"]

        # ---- 画面上の高さを計算（壁と同じスケール感に合わせる）----
        raw_h = (TILE * 500) / (perp + 1e-6)
        target_h = int(min(raw_h * float(meta.get("scale", 1.0)), HEIGHT * 2))
        if target_h <= 1:
            continue
        # 幅は元画像のアスペクト比を維持
        aspect = base_surf.get_width() / max(1, base_surf.get_height())
        target_w = max(1, int(target_h * aspect))

        # ---- スクリーンX位置の算出（角度→[-1..+1]→[0..W]へ）----
        # 差角0が中央、±FOV/2で0/W
        screen_x_center = int((WIDTH / 2) * (1 + (math.tan(angle_diff) / tan_half_fov)))

        # ---- “床に立っている感”の基準Y（ここをアニメの基準にする）----
        y_offset = int(meta.get("y_offset_px", 0))
        y_top_base = HALF_HEIGHT - (target_h // 2) + y_offset

        # ======================================================================
        # ★ 浮遊アニメ：上下サイン波
        # ======================================================================
        period_s = 1.6                          # 周期（秒）
        speed = (2 * math.pi) / period_s        # 角速度
        # 位相をタイル座標から擬似乱数的に決める（同期防止）
        tile_x, tile_y = it["tile"]
        phase = ((tile_x * 73856093) ^ (tile_y * 19349663)) & 0xFFFF
        phase = (phase / 65535.0) * 2 * math.pi

        # 近距離ほど画面上の高さが大きい＝その割合で揺らすと自然
        base_amp = target_h * 0.05
        far_atten = max(0.5, min(1.0, 120.0 / (perp + 1e-6)))  # 0.5〜1.0
        amp_px = int(max(2, base_amp * far_atten))

        bob = math.sin(t * speed + phase)  # -1..+1
        bob_px = int(bob * amp_px)         # 実ピクセル

        # ほんの少し左右にもゆらす（好みで削除OK）
        sway = math.sin(t * speed * 0.6 + phase * 1.7)  # -1..+1
        sway_px = int(sway * max(1, target_w * 0.02))

        # 実際に使う描画原点
        x_left = (screen_x_center - target_w // 2) + sway_px
        y_top = y_top_base - bob_px  # 上に持ち上がると「浮いた」感じになる

        # ---- スケール済みSurfaceをキャッシュ ----
        cache_key = (key, target_h)
        scaled = game_state.sprite_scale_cache.get(cache_key)
        if scaled is None:
            scaled = pygame.transform.smoothscale(base_surf, (target_w, target_h))
            game_state.sprite_scale_cache[cache_key] = scaled

        # ---- 画面外クリップ ----
        draw_x0 = max(0, x_left)
        draw_x1 = min(WIDTH, x_left + target_w)
        if draw_x0 >= draw_x1:
            continue

        # ======================================================================
        # ★ 影（楕円）：床面に“存在”させる
        # ======================================================================
        bottom_y = y_top + target_h
        shadow_w = int(target_w * 0.55)
        shadow_h = int(target_h * 0.16)
        # 浮き量に応じて強度を変える（高いほど薄く小さく）
        bob_norm = (bob + 1) * 0.5  # 0..1（0=最下/接地気味, 1=最上）
        alpha = int(120 - 60 * bob_norm)  # 120→60
        sh_w = max(6, int(shadow_w * (0.9 - 0.2 * bob_norm)))
        sh_h = max(3, int(shadow_h * (0.9 - 0.2 * bob_norm)))

        shadow_surf = pygame.Surface((sh_w, sh_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, alpha), (0, 0, sh_w, sh_h))
        # 影の貼り付け位置（中央合わせ）
        shadow_x = screen_x_center - sh_w // 2 + sway_px
        shadow_y = bottom_y - max(2, sh_h // 2)
        # 影は壁の前後関係に関わらず床に“のる”表現なので、先にベタ描画でOK
        if 0 <= shadow_x < WIDTH and 0 <= shadow_y < HEIGHT:
            screen.blit(shadow_surf, (shadow_x, shadow_y))

        # --- 近接ヒント/縁取りのパラメータ -------------------------------
        highlight_radius_px = 72   # 近距離判定（視認性UPの閾値）
        outline_rgba = (255, 255, 180, 160)  # 柔らかい黄の縁取り（RGBA）
        outline_offset = 1         # スプライト外側に1px膨らませる

        # 近接判定（“実距離”）＋視界内かつ壁に隠れていないかの簡易判定
        is_near = c.get("dist", perp) <= highlight_radius_px
        visible_here = (0 <= screen_x_center < WIDTH) and (perp < zbuffer[screen_x_center] - 1e-4)

        # ==========================
        # ★ 近距離ハイライト：縁取り
        # ==========================
        outline_surf = None
        if is_near:
            cache_key_outline = (key, target_h, outline_rgba)
            outline_surf = game_state.sprite_outline_cache.get(cache_key_outline)
            if outline_surf is None:
                mask = pygame.mask.from_surface(scaled)
                points = mask.outline(1)  # 1px外側の輪郭点列
                w, h = scaled.get_width(), scaled.get_height()
                outline_surf = pygame.Surface((w + outline_offset*2, h + outline_offset*2), pygame.SRCALPHA)
                ox = oy = outline_offset
                for px_o, py_o in points:
                    outline_surf.set_at((px_o + ox, py_o + oy), outline_rgba)
                game_state.sprite_outline_cache[cache_key_outline] = outline_surf

        # ---- 列ごとにZバッファで前後判定＋1px幅でブリット ----
        col_w = 1
        for sx in range(draw_x0, draw_x1, col_w):
            src_x = sx - x_left
            if perp < zbuffer[sx] - 1e-4:
                # ① 縁取り（近距離時）
                if outline_surf is not None:
                    out_x = sx - outline_offset
                    out_y = y_top - outline_offset
                    out_sub = outline_surf.subsurface((src_x, 0, col_w, outline_surf.get_height()))
                    screen.blit(out_sub, (out_x, out_y))
                # ② 本体
                sub = scaled.subsurface((src_x, 0, col_w, target_h))
                screen.blit(sub, (sx, y_top))

        # ===== ラベル（“E：拾う”）をスプライトの下端に少し被せて描画 =====
        if is_near and visible_here:
            sprite_bottom = y_top + target_h
            overlap_px = max(6, int(target_h * 0.28))
            label_top = sprite_bottom - overlap_px
            blit_pill_label_midtop(
                screen,
                "E：拾う",
                center_x=screen_x_center + sway_px,
                top_y=label_top,
                size=16,
                text_color=(255, 255, 255),
                outline_color=(0, 0, 0),
                outline_px=2,
                bg_rgba=(0, 0, 0, 170),
                radius=6,
            )

# --- ワールド座標(ピクセル)→スクリーン投影（ラベル用の簡易版） -----------------
def _project_to_screen(wx: float, wy: float, *, fov_margin: float = 0.2):
    """
    返り値: dict or None
      {
        'screen_x': int,         # 画面中央基準のX座標（ラベル中央に使う）
        'perp': float,           # 垂直距離（Zバッファ比較用）
        'y_top_base': int,       # "スプライト基準の上辺Y" 相当（ラベルの上下計算に流用）
        'target_h': int          # スプライト高さ相当（ラベルの“被せ量”の基準）
      }
    None: FOV外／背面など
    """
    px, py = game_state.player_x, game_state.player_y
    pa = game_state.player_angle
    dx, dy = wx - px, wy - py
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return None

    angle_to = math.atan2(dy, dx)
    angle_diff = (angle_to - pa + math.pi) % (2 * math.pi) - math.pi
    if abs(angle_diff) > (FOV * 0.5 + fov_margin):
        return None

    perp = dist * math.cos(angle_diff)
    if perp <= 0:
        return None

    tan_half_fov = math.tan(FOV * 0.5)
    screen_x = int((WIDTH / 2) * (1 + (math.tan(angle_diff) / tan_half_fov)))

    # ラベル位置計算のために、アイテムと同じスケールを仮想で出す
    raw_h = (TILE * 500) / (perp + 1e-6)
    target_h = int(min(raw_h * 1.0, HEIGHT * 2))
    y_offset = 12  # “床に居る”感じの軽い下げ（ドア/スイッチ共通の仮想値）
    y_top_base = HALF_HEIGHT - (target_h // 2) + y_offset

    return {
        "screen_x": screen_x,
        "perp": perp,
        "y_top_base": y_top_base,
        "target_h": max(1, target_h),
    }
# -----------------------------------------------------------------------------

def _draw_world_hint_label(wx: float, wy: float, text: str, zbuffer: np.ndarray,
                           *, overlap_frac: float = 0.22,  # 0.12〜0.30がおすすめ
                           sway_px: int = 0):
    """
    ドア/スイッチのタイル中心などの (wx, wy) に対して、
    画面に“少し被せる”ラベルを描く。
    - Zバッファで遮蔽されていれば描かない
    - overlap_frac: スプライト高さ相当の何割ぶんか被せる量
    """
    proj = _project_to_screen(wx, wy)
    if proj is None:
        return

    x = proj["screen_x"]
    perp = proj["perp"]
    target_h = proj["target_h"]
    y_top = proj["y_top_base"]
    draw_x0 = max(0, x - 1)
    draw_x1 = min(WIDTH, x + 1)

    # 可視（壁で隠れていない）判定：列中央近傍でOK
    visible = False
    for sx in range(draw_x0, draw_x1):
        if perp <= zbuffer[sx] + 0.05:  # ドアは“壁面そのもの”なので+εで許容
            visible = True
            break
    if not visible:
        return

    sprite_bottom = y_top + target_h
    overlap_px = max(6, int(target_h * overlap_frac))
    label_top = sprite_bottom - overlap_px

    blit_pill_label_midtop(
        screen,
        text,
        center_x=x + sway_px,
        top_y=label_top,
        size=16,
        text_color=(255, 255, 255),
        outline_color=(0, 0, 0),
        outline_px=2,
        bg_rgba=(0, 0, 0, 170),
        radius=6,
    )

# ============================================================
# 共有ユーティリティ：タイル中心 → 画面ラベル描画の定型を一箇所に集約
# ============================================================

def _tile_center(tx: int, ty: int) -> tuple[float, float]:
    """タイル座標(tx, ty)から“世界座標の中心(px)”に変換します。"""
    return (tx * TILE + TILE * 0.5, ty * TILE + TILE * 0.5)

def _label_geom_for_tile(tx: int, ty: int, zbuffer: np.ndarray, *, overlap_frac: float = 0.22):
    """
    ラベルを“貼る位置”を計算し、描けるならそのジオメトリを返します。
    戻り値: (screen_x, label_top, proj) または None（不可視／FOV外など）

    - proj: 既存の _project_to_screen() と同じ辞書（再計算を避けられます）
    - overlap_frac: ラベルをスプライト（壁面）にどれくらい重ねるかの比率
    """
    wx, wy = _tile_center(tx, ty)

    # 画面投影（FOV外・背面はここで弾く）
    proj = _project_to_screen(wx, wy)
    if proj is None:
        return None

    x = proj["screen_x"]
    perp = proj["perp"]
    target_h = proj["target_h"]
    y_top = proj["y_top_base"]

    # Zバッファで“壁の裏に隠れていないか”を確認
    # 1〜2ピクセル幅で可視判定することで、細い隠れを拾いやすくします
    x0 = max(0, x - 1)
    x1 = min(WIDTH, x + 1)
    visible = any(perp <= zbuffer[sx] + 0.05 for sx in range(x0, x1))
    if not visible:
        return None

    # ラベルの“上辺Y”を計算（少しだけ重ねて視認性を上げる）
    sprite_bottom = y_top + target_h
    overlap_px = max(6, int(target_h * overlap_frac))
    label_top = sprite_bottom - overlap_px

    return (x, label_top, proj)

def emit_label_for_tile(
    tx: int,
    ty: int,
    text: str,
    zbuffer: np.ndarray,
    *,
    overlap_frac: float = 0.22,
    size: int = 16,
    after_draw: Callable[[int, int, dict], None] | None = None, 
):
    """
    タイル(tx,ty)に“ピル型ラベル”を描画します。描けた場合は (screen_x, label_top, proj) を返します。
    after_draw が指定されていれば、ラベル描画直後に呼びます（進捗バーなど二段表示に便利）。

    例）木の進捗バー:
        emit_label_for_tile(..., after_draw=lambda x, top, proj:
            _draw_small_progress_bar_midtop(screen, x, top + 22, hits, TREE_HITS_REQUIRED, w=120))

    ※ ラベル自体の描画は blit_pill_label_midtop() を利用します。
    """
    geom = _label_geom_for_tile(tx, ty, zbuffer, overlap_frac=overlap_frac)
    if geom is None:
        return None

    x, label_top, proj = geom
    blit_pill_label_midtop(
        screen,
        text,
        center_x=x,
        top_y=label_top,
        size=size,
        text_color=(255, 255, 255),
        outline_color=(0, 0, 0),
        outline_px=2,
        bg_rgba=(0, 0, 0, 170),
        radius=6,
    )

    if after_draw is not None:
        # after_draw には (screen_x, label_top, proj) を渡す
        after_draw(x, label_top, proj)

    return geom

def _dist2_px(px: float, py: float, wx: float, wy: float) -> float:
    """2D 距離の2乗（sqrtを避けたいとき用の超軽量版）"""
    dx, dy = px - wx, py - wy
    return dx * dx + dy * dy

def draw_interaction_hints(zbuffer: np.ndarray):
    """
    近接時に「E：〜」ラベルを表示。
    - ドア：E：開ける / 鍵が必要
    - スイッチ：E：押す
    - 大木：E：大木を倒す(進捗バー) / 斧が必要
    - 守人：E：供物を捧げる / 供物が必要
    """
    cur_map = MAPS[game_state.current_map_id]
    layout = cur_map["layout"]

    # プレイヤー位置・距離閾値（半径Rの2乗で比較して sqrt を避ける）
    px, py = game_state.player_x, game_state.player_y
    R = 80.0
    R2 = R * R

    # ---------------------------------------
    # 1) ドア（壁ブロック対応：見えなければ画面固定ラベルにフォールバック）
    # ---------------------------------------
    # ドアは壁（タイル境界）なので、タイル中心に“世界貼り”したラベルは壁面に
    # 隠れやすい。まずは emit_label_for_tile を試し、不可なら画面固定で前面表示。
    #
    # さらに「正面1マスがドア」の時だけ 1.0 秒だけ表示して“出しっぱなし”を回避。
    cx, cy = int(px // TILE), int(py // TILE)
    fx, fy = _front_tile(px, py, game_state.player_angle)  # 正面1マス（壁向き時はここがドア）

    # 近接セッション（同じ文言を連続表示しないための軽量デバウンス）
    if not hasattr(draw_interaction_hints, "_door_hint"):
        draw_interaction_hints._door_hint = {"key": None, "until": 0}
    _H = draw_interaction_hints._door_hint
    now = pygame.time.get_ticks()

    # ---------------------------------------
    # 1) ドア（鍵が必要かどうかで文言分岐）
    #    ・通常：ドアタイルへ“世界貼り”
    #    ・壁で隠れる/遠い：正面2タイル目がドアなら
    #        → 1タイル目の床に貼る（不可視なら画面固定ピルへ）
    # ---------------------------------------
    cx, cy = int(px // TILE), int(py // TILE)
    fx1, fy1 = _front_tile(px, py, game_state.player_angle)   # 正面1マス
    fx2, fy2 = (fx1 + (fx1 - cx), fy1 + (fy1 - cy))           # 正面2マス（一直線）

    # ★ 未定義エラー対策：スコープに is_front を用意しておく（初期値 False）
    is_front = False  # ← まずは関数スコープに用意（ループで上書き）

    # -----------------------------
    # 1) ドア（鍵あり/なしで文言分岐）
    # -----------------------------
    for door in cur_map.get("doors", []):
        tx, ty = door["tile"]
        wx, wy = _tile_center(tx, ty)

        # game_state 上で既に「開いたドア」として記録されている場合はスキップ
        door_id = door.get("id", "")
        if door_id and game_state.is_door_opened(game_state.current_map_id, door_id):
            continue

        # 距離が遠いなら対象外
        if _dist2_px(px, py, wx, wy) > R2:
            continue

        # 既に“床化”（= 開いている）しているなら対象外（保険）
        try:
            ch = layout[ty][tx]
            if TILE_TYPES.get(ch, {"walkable": False}).get("walkable", False):
                continue
        except Exception:
            continue

        # 文言（鍵が必要 or 開ける）
        lock_id = door.get("lock_id")
        need_key = bool(lock_id and game_state.inventory.get(lock_id, 0) <= 0)
        text = f"{display_name(lock_id)}が必要" if need_key else "E：開ける"
        key  = (game_state.current_map_id, tx, ty, text)

        # 同一文面の出しっぱなしを抑止
        if not _hint_session_should_draw(key):
            continue

        # A) まずは“ドアそのもの”に世界貼り（見えていれば最良）
        drew = emit_label_for_tile(tx, ty, text, zbuf, overlap_frac=0.22)
        if drew:
            drew_any = True
            continue

        # B) ドアが正面2マス目にあり、正面1マス目が床なら「床側に貼る」
        if (fx2, fy2) == (tx, ty):
            walk1 = False
            if 0 <= fy1 < len(layout) and 0 <= fx1 < len(layout[0]):
                ch1 = layout[fy1][fx1]
                walk1 = bool(TILE_TYPES.get(ch1, {"walkable": False}).get("walkable", False))
            if walk1:
                drew2 = emit_label_for_tile(fx1, fy1, text, zbuf, overlap_frac=0.18)
                if drew2:
                    drew_any = True
                    continue

        # C) それでも見えないなら、画面固定ピルで確実に提示
        blit_pill_label_midtop(screen, text, center_x=WIDTH // 2, top_y=HEIGHT - 86, size=16)
        drew_any = True


        # 見えなかった（＝壁面に隠れた等）場合のみ、画面固定の前面ラベルへ。
        # ただし“正面1マスがドア”の場合に限る（視点と関係ない無限点灯を防止）。
        if is_front:
            key = (game_state.current_map_id, tx, ty, text)
            if key != _H["key"] or now > _H["until"]:
                _H["key"] = key
                _H["until"] = now + 1000  # 表示は 1.0s だけ
            # 期限内だけ表示
            if now <= _H["until"]:
                blit_pill_label_midtop(
                    screen,
                    text,
                    center_x=WIDTH // 2,
                    top_y=HEIGHT - 86,   # 画面下部中央（トーストと被らない高さ）
                    size=16,
                    text_color=(255, 255, 255),
                    outline_color=(0, 0, 0),
                    outline_px=2,
                    bg_rgba=(0, 0, 0, 170),
                    radius=6,
                )
        else:
            # 正面から外れたらセッションを終了（次に正面に来た時に再び1秒だけ表示）
            if _H["key"] is not None:
                _H["key"] = None
                _H["until"] = 0

    # ---------------------------------------
    # 2) スイッチ（近ければ「E：押す」）
    # ---------------------------------------
    # 2) スイッチ（近ければ「E：押す」）
    #    正：マップ定義では puzzle["switches"] に入っている。
    #        ここを参照しないとループが回らず、ラベルが出ない。
    puzzle = cur_map.get("puzzle") or {}
    switches = puzzle.get("switches") or {}
    # 既存マップは dict 形式（{"a":{"pos":(x,y)}, …}）なので values() を回す
    for info in (switches.values() if isinstance(switches, dict) else []):
        # info 例: {"pos": (15, 7)}
        tx, ty = info["pos"]
        wx, wy = _tile_center(tx, ty)  # タイル中心のワールド座標（px）
        # プレイヤ中心(px,py) からの二乗距離を閾値 R2（例:80px^2）で判定
        if _dist2_px(px, py, wx, wy) > R2:
            continue
        # タイル位置へワールド固定の吹き出しを投げる。
        # overlap_frac は壁頭頂からのオフセット量の微調整（既存値を踏襲）
        emit_label_for_tile(tx, ty, "E：押す", zbuffer, overlap_frac=0.18)

    # ---------------------------------------
    # 3) 大木（足元 'O' か、正面1マス 'O' を対象）
    # ---------------------------------------
    cx = int(px // TILE)
    cy = int(py // TILE)

    # 正面1マスの計算ヘルパ
    def _front_O_or_None():
        fx, fy = _front_tile(px, py, game_state.player_angle)
        if 0 <= fy < len(layout) and 0 <= fx < len(layout[0]) and layout[fy][fx] == 'O':
            return fx, fy
        return None

    # 足元 or 正面に 'O' があればターゲットにする
    tree_target = (cx, cy) if layout[cy][cx] == 'O' else _front_O_or_None()
    if tree_target is not None:
        tx, ty = tree_target
        has_axe = game_state.inventory.get("axe", 0) > 0
        hits = game_state.state.get("chop_hits", {}).get((game_state.current_map_id, tx, ty), 0)
        text = (f"E：大木を倒す ({hits}/{TREE_HITS_REQUIRED})") if has_axe else "斧が必要"

        # 進捗バーは after_draw で“ラベルの下”に追記
        def _after(x, label_top, proj):
            _draw_small_progress_bar_midtop(
                screen,
                x,
                label_top + 22,  # ラベル直下に 22px 程度空ける
                hits,
                TREE_HITS_REQUIRED,
                w=120
            )

        emit_label_for_tile(
            tx, ty, text, zbuffer,
            overlap_frac=0.20,
            after_draw=(_after if has_axe and hits > 0 else None)
        )

    # ---------------------------------------
    # 4) 守人（足元 'M' か、正面1マス 'M' を対象）
    # ---------------------------------------
    def _front_M_or_None():
        fx, fy = _front_tile(px, py, game_state.player_angle)
        if 0 <= fy < len(layout) and 0 <= fx < len(layout[0]) and layout[fy][fx] == 'M':
            return fx, fy
        return None

    guard_target = (cx, cy) if layout[cy][cx] == 'M' else _front_M_or_None()
    if guard_target is not None:
        tx, ty = guard_target
        have = game_state.inventory.get("spirit_orb", 0) > 0
        text = "E：供物を捧げる" if have else "供物（幽き珠）が必要"
        emit_label_for_tile(tx, ty, text, zbuffer, overlap_frac=0.20)

    # --- 敵の追跡更新と捕獲処理（毎フレーム） ---
    #    ローカル関数として壁判定コールバックを必ず定義してから使用します。
    def _enemy_is_block_px(nx: float, ny: float) -> bool:
        """
        追跡者AI用の“ピクセル座標での通行不可判定”コールバック。
        - Chaser.update() へ渡すための軽量ラッパ
        - 半径を小さめ(6px)にして角での引っかかりを抑制
        """
        return is_wall(int(nx), int(ny), radius=6)  # ← main.py 既存の is_wall を想定

    def _respawn_player_to_map_start(cur_id: str):
        """suggested_player_start をリスポーン地点として使用"""
        m = MAPS.get(cur_id, {})
        sx, sy = m.get("suggested_player_start", (1.5, 1.5))
        # タイル中心 → ピクセル
        game_state.player_x = sx * TILE
        game_state.player_y = sy * TILE
        game_state.player_dir = 0.0

    # ループ内：敵更新 → 捕獲 → リスポーン
    for ch in getattr(game_state, "current_enemies", []):
        caught = ch.update((game_state.player_x, game_state.player_y), _enemy_is_block_px)
        if caught:
            # 既存のフェード演出を優先利用（あれば）
            # fade_out(screen, duration=300)
            # suggested_player_start へリスポーン（maps の推奨開始位置）
            m = MAPS.get(game_state.current_map_id, {})
            sx, sy = m.get("suggested_player_start", (1.5, 1.5))
            game_state.player_x = sx * TILE
            game_state.player_y = sy * TILE
            game_state.player_dir = 0.0
            # 敵も初期化
            for c in game_state.current_enemies:
                c.reset()
            # fade_in(screen, duration=300)
            break  # 1体でも捕獲したら今フレームは終了
    
def _draw_small_progress_bar_midtop(surface, center_x, top_y, cur, need, w=90, h=8):
    """小型の進捗バーを描画（midtopアンカー）"""
    x = int(center_x - w // 2); y = int(top_y)
    pygame.draw.rect(surface, (0,0,0,160), (x, y, w, h), border_radius=3)
    fill_w = int(w * max(0.0, min(1.0, cur/need)))
    if fill_w > 0:
        pygame.draw.rect(surface, (160,220,160,220), (x, y, fill_w, h), border_radius=3)
    pygame.draw.rect(surface, (255,255,255,180), (x, y, w, h), width=1, border_radius=3)

def draw_map_confirm_prompt(surface):
    """map_confirm 中は毎フレーム、画面下部に Y/N の確認文を出す。"""
    if game_state.state.get("mode") != "map_confirm":
        return
    trig = game_state.state.get("pending_trigger") or {}
    msg = trig.get("prompt") or "先へ進みますか？"
    # 「（Y/N）」を付けて目立たせる
    text = f"{msg}（Y/N）"
    draw_label(
        surface,
        text,
        size=18,
        pos=(WIDTH // 2, HEIGHT - 32),
        anchor="midbottom",
        bg_color=(0, 0, 0, 160),
    )

def draw_inventory_overlay(surface): # インベントリオーバーレイ（デバック用：画面にアイテムを表示します）
    """画面左上にインベントリを簡易表示（Noto Sans JPで統一）"""
    fps = int(clock.get_fps())
    rect = draw_label(surface, f"FPS: {fps}", size=16, pos=(10, 10),
                    anchor="topleft", bg_color=(0,0,0,130))
    y = rect.bottom + 6
    x = 10
    for name, cnt in game_state.inventory.items():
        rect = draw_label(
            surface,
            f"{name}: {cnt}",
            size=16,
            pos=(x, y),
            anchor="topleft",
            bg_color=(0, 0, 0, 130),
        )
        y = rect.bottom + 6

_has_played_video = cin_has_played # このマップで指定IDのムービーを再生済みか？（セーブ/ロード対応のsetを参照）
_mark_video_played = cin_mark_played # 再生済みマークを立てる（JSON保存時にlist化→ロードでsetに復元される想定）

def _player_near_any_symbol(symbols: tuple[str, ...], radius_px: float) -> bool:
    """マップ内の指定記号（例: 'F','f'）のいずれかに半径r以内で近接しているかを判定"""
    layout = MAPS[game_state.current_map_id]["layout"]
    px, py = game_state.player_x, game_state.player_y
    r2 = radius_px * radius_px
    for y, row in enumerate(layout):
        for x, ch in enumerate(row):
            if ch in symbols:
                cx, cy = x * TILE + TILE * 0.5, y * TILE + TILE * 0.5
                if (px - cx)**2 + (py - cy)**2 <= r2:
                    return True
    return False

def _check_auto_fog_movie_once():
    """
    霧（F/f）に近づいたらムービーを“1回だけ”再生する。
    - 霧を晴らした（fog_cleared に現在マップIDが入った）後は発火しない。
    - 「スキップ」でも“一度流れた扱い”にする → 次回から再生しない。
    自動ムービーは cin_enqueue → _process_cinematic_queue() に任せる。
    """
    return

def _check_auto_river_movie_once():

    """
    〈川（w/W）に近づいたらムービーを“1回だけ”再生〉
    - 橋が架かった等で 'w' が無くなっていれば発火しません（軽い早期return）
    - スキップしても“一度流れた扱い”にして二度と出さない設計
    自動ムービーは cin_enqueue → _process_cinematic_queue() に任せる。
    """
    return

def _check_auto_trunk_movie_per_tree():
    """自動ムービーは cin_enqueue → _process_cinematic_queue() に任せる。"""
    return

# --- 連打＆多重発火の安全弁（カットシーン直後の連続トリガ防止） ------------------
if not hasattr(game_state, "cinematic_cooldown_ms"):
    game_state.cinematic_cooldown_ms = 0  # 次に発火可能になる時刻（ms）

_arm_cinematic_cooldown = cin_arm_cd # 次の発火を少し遅らせて“多重再生”を防ぐ（霧と川が隣接する等の保険）
_can_fire_cinematic = cin_can_fire # 今ムービーを発火してよいか？（クールダウン中やカットシーン中なら不可）

def play_inline_video(screen, base_dir: Path, rel_path: str, *, allow_skip=True, fade=True):
    return cin_play_blocking(screen, base_dir, rel_path, allow_skip=allow_skip, fade=fade)

# === Cinematics → UIトースト 橋渡しアダプタ ============================
# - 引数の揺れに対応: toast_cb(msg) / toast_cb(msg, ms) / toast_cb(msg, duration=ms)
# - UI実装の揺れに対応: toast.show / show_toast / ui.toast を順番に試す
# - 失敗してもゲームが止まらないよう例外は握りつぶす
def _toast_adapter(*args, **kwargs):
    """
    Cinematics側から呼ばれるコールバックをUIのトーストに橋渡しする。
    例:
        toast_cb("テキスト")                     # ms省略
        toast_cb("テキスト", 2000)              # ms指定
        toast_cb("テキスト", duration=2000)     # キーワード引数
    """
    # --- 引数を素直に解釈 ---
    message = None
    ms = None
    if args:
        message = args[0]
        if len(args) > 1:
            ms = args[1]
    if ms is None:
        ms = kwargs.get("ms", kwargs.get("duration", None))

    if not message:
        return  # 何も表示しない

    # デフォルト表示時間（ms）。UI側が未対応でも安全
    try:
        duration = int(ms) if ms is not None else 1800
    except Exception:
        duration = 1800

    # --- UIトースト呼び出し（存在するものを順に試す） ---
    try:
        # 例: toast.show("msg", 1800)
        toast.show(message, duration)  # type: ignore[name-defined]
        return
    except Exception:
        pass

    try:
        # 例: show_toast("msg", 1800)
        show_toast(message, duration)  # type: ignore[name-defined]
        return
    except Exception:
        pass

    try:
        # 例: ui.toast("msg", 1800)
        ui.toast(message, duration)    # type: ignore[name-defined]
        return
    except Exception:
        pass

    # 最後の保険（UIにトーストが無い環境）
    try:
        print(f"[TOAST] {message}")
    except Exception:
        pass

# --- 汎用：近接で一度だけムービー（集約版ラッパ） -----------------------------
def trigger_proximity_movie_once(
    *,
    video_id: str,                        # 保存に使うユニークID（例: "fog_intro" / "river_intro"）
    symbols: tuple[str, ...],             # 近接判定するマップ記号（例: ('F','f') / ('w','W')）
    video_path: str | None = None,        # 再生する動画パス（指定があれば優先）
    radius_px: float = 96.0,              # 近接半径
    enable_if = lambda: True,             # 条件関数：Falseなら発火しない（例: 霧クリア後は無効）
    toast_on_end: str | None = None,      # 再生し終えた後のトースト（任意）
    toast_on_skip: str = "……（スキップ）", # スキップ時のトースト（任意）
) -> bool:
    """
    【集約版】
    VideoEvent を直接使わず、core.cinematics.trigger_proximity_movie_once に委譲します。
    互換のため video_id / video_path の両方を受け取り、指定があれば video_path を優先します。
    戻り値は従来どおり：True=再生（またはスキップ）を一度行った / False=何もしなかった
    """
    from core.cinematics import trigger_proximity_movie_once as _cin_trigger_once
    # cinematics 側は video_id に .mp4 を渡せばそのまま扱います
    vid = video_path or video_id
    return _cin_trigger_once(
        screen, BASE_DIR,
        video_id=vid,
        symbols=symbols,
        radius_px=radius_px,
        enable_if=enable_if,
        toast_on_end=toast_on_end,
        toast_on_skip=toast_on_skip,
        audio_path=audio_path,
        sound_manager=sound_manager,
    )

def _process_cinematic_queue():
    """
    interactions 側が積んだ演出ジョブ（ムービー等）を1件だけ処理。
    - すでに“再生済みID”ならスキップして次へ
    - 再生後にトーストを出す（指定があれば）
    """
    # ムービー完了時のメッセージを “必ず” トーストに橋渡しするアダプタ
    def _toast_adapter(msg, ms=1800):
        # コールバックの実装違いに耐性を持たせる（msgだけ来る実装でも動く）
        try:
            toast.show(str(msg), ms=ms)
        except TypeError:
            toast.show(str(msg), ms=1800)

    # 1フレームにつき1件だけ進め、完了時は _toast_adapter を呼んでもらう
    cin_process_queue(screen, BASE_DIR, toast_cb=_toast_adapter, sound_manager=sound_manager)

# -----------------------------------------------------------------------------------------

# 追跡者の足元Yを覚えて、フレーム間の移動量を制限するための状態変数
_CHASER_GROUND_Y: float | None = None

# 接近/離脱の判定用に前回距離を保持
_CHASER_PREV_DIST: float | None = None

def _draw_chaser_billboard(screen_surf: pygame.Surface, zbuf: list[float | None]) -> None:
    """
    追跡者スプライトをレイキャスト画面にビルボードとして描画する。
    - 投影（位置→画面座標）はプレイヤー基準の相対角と深度を用いる
    - アニメ進行は update_chaser_anim() / get_chaser_frame_current() に一元化
    - zバッファで壁に隠れる場合は描画しない
    """
    # --- 状態取得と基本チェック ---
    st = game_state.state.get("chaser", {})
    if not st or not st.get("active"):
        return
    if st.get("map_id") != game_state.current_map_id:
        return

    # ワールド座標（ピクセル）
    sx, sy = float(st.get("x", 0.0)), float(st.get("y", 0.0))
    px, py = game_state.player_x, game_state.player_y
    ang    = game_state.player_angle

    # プレイヤー基準の相対ベクトル（2D）
    dx, dy = (sx - px), (sy - py)
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return  # 同一座標のときは描かない

    # スプライト方向と相対角（-π..+π）
    target_ang = math.atan2(dy, dx)
    rel_ang = (target_ang - ang + math.pi) % (2 * math.pi) - math.pi

    # 視野角（水平FOV）：エンジン定義があれば優先
    FOV = FOV_RAD if 'FOV_RAD' in globals() else math.radians(60.0)

    # FOV外（少し余裕を持たせる）
    if abs(rel_ang) > (FOV * 0.55):
        return

    W, H = screen_surf.get_width(), screen_surf.get_height()
    HALF_W, HALF_H = W * 0.5, H * 0.5

    # 画面X：相対角を水平方向に線形マッピング
    #   rel_ang = -FOV/2 → x=0, 0 → x=W/2, +FOV/2 → x=W
    screen_x = (rel_ang / (FOV / 2.0)) * HALF_W + HALF_W

    # --- 壁との遮蔽（zバッファ）チェック ---
    # 画面X(0..W) → レイ配列(0..len(zbuf)-1)へ写像
    col = int(screen_x / max(1, W) * len(zbuf))
    col = max(0, min(col, len(zbuf) - 1))
    wall_d = zbuf[col]

    # 手前に壁がある & スプライトがさらに奥 → 隠れて見えない
    if wall_d is not None and wall_d > 0 and dist > wall_d:
        return

    # --- アニメ進行（中央集権） ---
    update_chaser_anim()                 # 毎フレーム1回呼ぶ想定（ここでOK）
    frame = get_chaser_frame_current()   # 現在のコマ画像（CHASER_FRAMES[CHASER_CUR_INDEX]）

    # --- 投影スケールの計算 ---
    # 「距離dist」そのものではなく、視線方向の“前方成分” cam_y = dist * cos(rel_ang) を使うと歪みが少ない
    cam_y = dist * max(1e-6, math.cos(rel_ang))  # 正面に近いほど大きい
    # 焦点距離（水平FOVを使った簡易式）
    dist_to_plane = (W / 2.0) / math.tan(FOV / 2.0)

    # ワールド上での見かけ基準サイズ（高さ基準）
    base_world_size_px = TILE * 1.2  # 好みで調整（1.2～1.6）
    # 画面上の高さpx（遠くほど小さくなる）
    screen_h = int(base_world_size_px * (dist_to_plane / cam_y))
    if screen_h <= 0:
        return
    # 幅はアスペクト維持
    screen_w = int(frame.get_width() * (screen_h / max(1, frame.get_height())))

    # --- 足元Yの“透視投影” + 近距離安定化ブレンド ---
    # 1) 遠距離：透視投影（距離で地平線に寄る）を使う
    # 2) 近距離：見た目が暴れやすいので「安定地面Y」に寄せる
    #    → 距離に応じて 1) と 2) を線形補間（ブレンド）する

    # ●目線高さ（小さめから調整。沈み込みが気になったら下げる）
    EYE_HEIGHT_PX = TILE * 1.0  # 0.8～1.3 で微調整可

    # ●安全ガード：正面成分が小さすぎると数式が跳ねるので下限を設ける
    cam_y_safe = max(24.0, cam_y)

    # ●透視投影の足元Y（遠距離の理想挙動）
    ground_proj = HALF_H + (EYE_HEIGHT_PX * dist_to_plane / cam_y_safe)

    # ●近距離での“安定”足元Y（固定気味にする値）
    #   ここは「地平線（HALF_HEIGHT）より十分下」で、常に地面っぽく見える高さに。
    ground_near = HALF_H + TILE * 2.0  # 大きくすると“下寄り”（0.8～2.4で調整）

    # ●距離に応じて補間（NEAR→FAR で 0→1）
    NEAR_START = TILE * 0.8   # これ以下は“ほぼ近距離扱い”
    NEAR_END   = TILE * 2.4   # これ以上は“ほぼ遠距離扱い”
    #   t=0 → 近距離（安定地面） / t=1 → 遠距離（透視投影）
    t = 0.0
    if NEAR_END > NEAR_START:
        t = (dist - NEAR_START) / (NEAR_END - NEAR_START)
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)  # clamp01

    # ●線形補間：ground_y = (1-t)*near + t*proj
    ground_y_f = ground_near * (1.0 - t) + ground_proj * t

    # ●見た目安定用クランプ（上下限を決めて“逃げ”を防止）
    H = screen_surf.get_height()
    min_ground  = HALF_H + TILE * 1.2   # これより“上”（地平線側）へ上がらない
    max_ground = H - 6                       # 画面下端に落ちすぎない
    ground_y = int(min(max_ground, max(min_ground, ground_y_f)))

    # === ここから「上に逃げないブレーキ（時間方向の制限）」を追加 ===
    global _CHASER_GROUND_Y

    # 初回は現状に同期（いきなり飛ばないように）
    if _CHASER_GROUND_Y is None:
        _CHASER_GROUND_Y = float(ground_y)

    prev = _CHASER_GROUND_Y
    target = float(ground_y)

    # 1) 距離帯に応じて“なめらか係数”を少し変える（近距離ほど強めに安定）
    if dist <= TILE * 1.5:
        alpha = 0.30   # 近距離：素早く寄せすぎない（=安定）
    elif dist <= TILE * 3.0:
        alpha = 0.22   # 中距離
    else:
        alpha = 0.15   # 遠距離

    # 2) まずはローパス（滑らかに目標へ寄せる）
    raw = prev + (target - prev) * alpha

    # 3) フレーム間の最大移動量を制限（特に“上方向（画面の上=Yが小さくなる）”を強く制限）
    #    画面座標は「下に行くほど +Y 」なので、"上に逃げる" = Y が一気に小さくなること。
    MAX_UP_PER_FRAME   = 3.0  # 上方向（小さくなる）の最大変化量（厳しめ：小さいほど逃げにくい）
    MAX_DOWN_PER_FRAME = 5.0  # 下方向（大きくなる）は多少許容（沈みは目立ちにくい）

    # 変化量を計算
    delta = raw - prev

    # 上方向に動きすぎるならブレーキ
    if delta < -MAX_UP_PER_FRAME:
        raw = prev - MAX_UP_PER_FRAME
    # 下方向に動きすぎるなら軽くブレーキ（必要に応じて調整）
    elif delta > MAX_DOWN_PER_FRAME:
        raw = prev + MAX_DOWN_PER_FRAME

    # --- 接近中は「上がらない」単方向ブレーキを追加 ---
    global _CHASER_PREV_DIST
    if _CHASER_PREV_DIST is None:
        _CHASER_PREV_DIST = dist

    # 接近（今回のdistが前回より短い）なら、上方向の変化をさらに抑制
    if dist < _CHASER_PREV_DIST:
        # 接近中に以前より上（Yが小）へは行かせない
        if raw < prev:
            raw = prev  # ← “上に逃げない”を保証（必要なら 0.5px など微量許容に変えてもOK）

    _CHASER_PREV_DIST = dist  # 距離を記録

    # 状態更新 & ground_y 確定
    _CHASER_GROUND_Y = raw
    ground_y = int(raw)

    # 状態更新 & 実際に使う ground_y を確定
    _CHASER_GROUND_Y = raw
    ground_y = int(raw)

    # --- スケールしてスプライト作成 ---
    if (screen_w, screen_h) != frame.get_size():
        sprite = pygame.transform.smoothscale(frame, (screen_w, screen_h))
    else:
        sprite = frame

    # --- 足元基準で配置（下辺中央＝midbottom を地面に合わせる） ---
    rect = sprite.get_rect()
    FOOT_OFFSET = 6  # 画像下端の余白に合わせて 4～8 で微調整
    rect.midbottom = (int(screen_x), int(ground_y + FOOT_OFFSET))

    # --- 影（任意。接地感UP）---
    rx = max(4, int(18 * (screen_h / 120)))  # 横半径（距離に伴って少し変化）
    ry = max(2, int(rx * 0.45))              # 縦半径（潰すと床影っぽい）
    shadow = pygame.Surface((rx * 2, ry * 2), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 110), shadow.get_rect())
    screen_surf.blit(shadow, shadow.get_rect(center=(int(screen_x), int(ground_y))))

    # --- 本体を最後に描く ---
    screen_surf.blit(sprite, rect)

# ----------------------------------------------------------------------------------------

def _tile_center_px(tx: int | float, ty: int | float) -> tuple[float, float]:
    """タイル座標から“そのタイルの中心ピクセル”を返す小関数"""
    return (tx * TILE + TILE * 0.5, ty * TILE + TILE * 0.5)

# ----------------------------------------------
# 追跡者BGM（開始／停止）ヘルパ
# ----------------------------------------------
def _start_chaser_bgm_if_needed() -> None:
    """
    追跡者が出現中なら、専用BGMを一度だけ開始する。
    - assets/sounds/bgm/うしろからなにかが近づいてくる.mp3.enc があればそれを使用
    - 無ければ うしろからなにかが近づいてくる.mp3 を試す
    - どちらも無ければ何もしない（警告を出すだけ）
    """
    st = game_state.state.setdefault("chaser", {})
    if not st.get("active"):
        return
    if st.get("__bgm_on"):
        return  # 多重起動を防止
    try:
        # 優先順位：暗号化 → 平文
        cand = [
            "うしろからなにかが近づいてくる.mp3.enc",
            "うしろからなにかが近づいてくる.mp3",
        ]
        chosen = None
        for name in cand:
            full = sound_manager.bgm_path / name
            # ★ どのパスを探しているか可視化
            print(f"[CHASE BGM] probing: {full}")
            if full.exists():
                chosen = name
                break
        if chosen:
            # ループで再生（SoundManagerが重複起動を抑止)
            sound_manager.play_bgm(chosen, loop=True)
            st["__bgm_on"] = True
            # デバッグ表示
            print(f"[CHASE BGM] start -> {chosen}")
        else:
            # ファイルが無ければスキップ（動作には影響させない）
            if not st.get("__bgm_warned"):
                print("[CHASE BGM][WARN] assets/sounds/bgm/(うしろからなにかが近づいてくる.mp3|うしろからなにかが近づいてくる.mp3.enc) が見つかりません。BGMなしで続行。")
                st["__bgm_warned"] = True
    except Exception as e:
        print("[CHASE BGM][WARN]", e)

def _stop_chaser_bgm(fade_ms: int = 500) -> None:
    """
    追跡者専用BGMをフェードアウトで停止。
    - フラグも落として、次回の出現で再起動できるようにする
    """
    try:
        sound_manager.fadeout_bgm(ms=fade_ms)
    except Exception:
        pass
    st = game_state.state.setdefault("chaser", {})
    st["__bgm_on"] = False

def _update_chaser_and_check_caught(dt_sec: float):
    """
    追跡者が有効なら、プレイヤーへ向かって少し前進し、一定距離で“捕捉”。
    - 出現マップ外では動かない
    - 壁衝突は簡易に抑止（そのフレーム動かさない）
    - 捕獲は安全時間／クールダウン／ロックで多重発火を防止
    - 分岐で引っかからないよう、プレイヤーが見えない時だけ簡易A*で経路補助
    """
    st = game_state.state.setdefault("chaser", {})
    if not st.get("active"):
        return
    if st.get("map_id") != game_state.current_map_id:
        return
    # ★ 出現中BGM：ここで一度だけ起動（既に起動済みなら何もしない）
    _start_chaser_bgm_if_needed()

    now = pygame.time.get_ticks()
    # ★ 追跡者の“起床”までは動かさない
    wake_at = st.get("wake_at_ms", 0)
    if now < wake_at:
        return

    # 現在位置とプレイヤー位置
    cx, cy = float(st.get("x", game_state.player_x)), float(st.get("y", game_state.player_y))
    px, py = game_state.player_x, game_state.player_y

    # プレイヤーまでの距離
    dx, dy = (px - cx), (py - cy)
    dist = math.hypot(dx, dy)
    if dist <= 1e-6:
        return

    # --- パラメータ ---
    speed_px_per_sec = 80.0      # 追跡速度
    catch_radius_px  = CHASER_CATCH_RADIUS  # 定数化（例:22.0）

    # --- 捕獲ガード ---
    if now < game_state.state.get("__chaser_safe_until", 0):
        return  # スポーン直後の安全時間
    if now < game_state.state.get("__chaser_cooldown_until", 0):
        return  # クールダウン中
    if game_state.state.get("__caught_lock", False):
        return  # 捕獲シーケンス中

    # --- 捕獲チェック（移動前） ---
    if dist <= catch_radius_px:
        game_state.state["__caught_lock"] = True
        game_state.state["__chaser_cooldown_until"] = now + CHASER_CATCH_COOLDOWN
        # ★ まず追跡BGMを止めてから → 捕獲ムービーへ
        _stop_chaser_bgm(fade_ms=500)
        _on_player_caught_by_chaser()
        return

    # --- 目的地を決定 ---
    nav = game_state.state.setdefault("__nav", {"next_wp": None, "repath_at": 0})
    target_x, target_y = px, py  # デフォルトはプレイヤー

    # プレイヤーが壁で見えていなければ簡易A*でウェイポイントを使う
    if not _los_clear(cx, cy, px, py):
        if now >= nav.get("repath_at", 0) or not nav.get("next_wp"):
            layout = MAPS[game_state.current_map_id]["layout"]
            sx, sy = int(cx // TILE), int(cy // TILE)
            gx, gy = int(px // TILE), int(py // TILE)
            step = _a_star_next_step(layout, (sx, sy), (gx, gy))
            if step:
                wx = step[0] * TILE + TILE * 0.5
                wy = step[1] * TILE + TILE * 0.5
                nav["next_wp"] = (wx, wy)
            else:
                nav["next_wp"] = None
            nav["repath_at"] = now + NAV_REPATH_MS
        if nav.get("next_wp"):
            target_x, target_y = nav["next_wp"]

    # ウェイポイントに到達したら消す
    if nav.get("next_wp"):
        wx, wy = nav["next_wp"]
        if (target_x - cx) ** 2 + (target_y - cy) ** 2 <= (TILE * 0.3) ** 2:
            nav["next_wp"] = None

    # --- 前進 ---
    dirx, diry = target_x - cx, target_y - cy
    d = max(1e-6, math.hypot(dirx, diry))
    step = speed_px_per_sec * max(0.0, float(dt_sec))
    vx, vy = (dirx / d) * step, (diry / d) * step

    nx, ny = cx + vx, cy + vy

    # 壁衝突チェック（スライド移動も試す）
    if not is_wall(nx, ny, radius=8):
        st["x"], st["y"] = nx, ny
    elif not is_wall(nx, cy, radius=8):
        st["x"], st["y"] = nx, cy
    elif not is_wall(cx, ny, radius=8):
        st["x"], st["y"] = cx, ny
    else:
        st["x"], st["y"] = cx, cy

    # --- 捕獲チェック（移動後） ---
    dx2, dy2 = (px - st["x"]), (py - st["y"])
    if dx2 * dx2 + dy2 * dy2 <= (catch_radius_px ** 2):
        game_state.state["__caught_lock"] = True
        game_state.state["__chaser_cooldown_until"] = now + CHASER_CATCH_COOLDOWN
        _on_player_caught_by_chaser()

    # DEVログ
    if DEV_MODE and now % 500 < 16:
        print(f"[CHASER] x={st['x']:.1f}, y={st['y']:.1f}, can_catch={can_catch}, dist={dist:.1f}")

# ---------------------------------------------------------------------
# 追跡者トリガの“発火済み”を、指定マップ分だけリセットするユーティリティ
# - 形式: f"{map_id}:chaser_spawn:{trigger_id}" を対象に除去
# - 例: dungeon_1 で捕まって戻されたら dungeon_1 分だけをリセット
# ---------------------------------------------------------------------
def _reset_chaser_triggers_for_map(map_id: str) -> None:
    """
    捕獲→安全ワープの“周回やり直し”時に、追跡者近接トリガを再び有効化する。
    - maps.py 側の 'proximity_triggers'（kind='chaser_spawn'）のみ対象
    - 動画や他のトリガ種別には一切影響を与えない
    """
    try:
        fired: set[str] = game_state.FLAGS.setdefault("triggers_fired", set())
        # 対象キーを抽出（{map}:chaser_spawn:{id}）
        targets = {k for k in fired if k.startswith(f"{map_id}:chaser_spawn:")}
        if targets:
            fired.difference_update(targets)
            if DEV_MODE:
                print(f"[CHASER][RESET] cleared {len(targets)} fired keys for map={map_id}")
    except Exception as e:
        if DEV_MODE:
            print("[CHASER][RESET][WARN]", e)

def _on_player_caught_by_chaser():
    """
    追跡者に捕まったときの一連の処理：
    ムービー → lab_entranceへ“安全ワープ” → トースト → 追跡者停止 → ロック解除
    """
    _stop_chaser_bgm(fade_ms=250)  # 念のため捕獲BGM停止

# ★ 追跡者近接トリガのリセット処理
    #   - もともとは「捕獲直前のマップ(prev_map)だけ」リセットしていた
    #   - dungeon_1 と dungeon_2 は“1セットのチェイサー区画”として扱いたいので、
    #     どちらで捕まっても両方の chaser_spawn をリセットする。
    #   - それ以外のマップ（例：forest_*）では従来通り、そのマップだけリセットする。
    try:
        prev_map = getattr(game_state, "current_map_id", "")

        # dungeon 系のリンク定義
        linked_maps_by_prev = {
            # dungeon_1 で捕まったら 1階・2階両方のトリガをリセット
            "dungeon_1": ("dungeon_1", "dungeon_2"),
            # dungeon_2 で捕まった場合も同様に 1階・2階両方をリセット
            "dungeon_2": ("dungeon_1", "dungeon_2"),
        }

        if prev_map in linked_maps_by_prev:
            # ★ dungeon_1 / dungeon_2 のときは、ペアになっているマップすべてに対して
            #    chaser_spawn 用の一度化フラグを削除する
            for mid in linked_maps_by_prev[prev_map]:
                _reset_chaser_triggers_for_map(mid)
        elif prev_map:
            # ★ その他のマップは従来通り、そのマップだけをリセット
            _reset_chaser_triggers_for_map(prev_map)

    except Exception:
        # リセット処理中に何か起きてもゲーム進行が止まらないように握りつぶす
        if DEV_MODE:
            import traceback
            traceback.print_exc()
    
    # 1) 捕獲ムービー（あれば再生。失敗は握りつぶし）
    try:
        movie = "assets/movies/chaser_caught.mp4"
        if os.path.exists(os.path.join(BASE_DIR, movie)):
            play_inline_video(screen, BASE_DIR, movie, allow_skip=True, fade=False)
    except Exception:
        pass

    # 2) lab_entrance の '>' のタイルを探し、その「ひとつ下(y+1)」へ安全ワープ
    try:
        layout = MAPS["lab_entrance"]["layout"]
        spawn_tx, spawn_ty = None, None
        for ty, row in enumerate(layout):
            ix = row.find('>')
            if ix != -1:
                spawn_tx, spawn_ty = ix, ty + 1  # ＜ の直下（廊下側）に立たせる
                break
        if spawn_tx is None:
            # フォールバック：既定の復帰点（8,2）※廊下の中央あたり
            spawn_tx, spawn_ty = 8, 2

        # ★ワープはユーティリティで一括（座標・アセット・敵・環境音まで即同期）
        game_state.state["__suppress_warp_frames"] = 0   # ★重要：ワープ抑止を解除
        _warp_to("lab_entrance", (spawn_tx, spawn_ty))
        print("[DEBUG] caught -> warp to", game_state.current_map_id, game_state.player_x, game_state.player_y)
        # 向きを北向きに：
        game_state.player_angle = -math.pi / 2
    except Exception:
        # ワープ探索で万一失敗した場合の保険フォールバック
        game_state.current_map_id = "lab_entrance"
        game_state.player_x = 8 * TILE + TILE * 0.5
        game_state.player_y = 2 * TILE + TILE * 0.5

    # 3) トースト（UI 側ブリッジが切れても握りつぶし）
    try:
        toast.show("捕まってしまった……。")
    except Exception:
        pass

    # 4) 追跡者を無効化（以降の更新・描画を止める）
    st = game_state.state.setdefault("chaser", {})
    st["active"] = False
    st["__bgm_on"] = False

    # 5) 捕獲ロック解除
    game_state.state["__caught_lock"] = False
    
# --- 安全ワープ小関数（タイル→画面座標更新＋ロード） ------------------------
def _warp_to(map_id: str, spawn_tile_xy: tuple[int,int]):
    """マップIDとタイル座標を受けて、即座にワープするユーティリティ"""
    # ★ ロード直後の数フレームは“自動ワープ”を抑止して、ロード位置上書きを防ぐ
    try:
        st = getattr(game_state, "state", {})
        if isinstance(st, dict) and st.get("__suppress_warp_frames", 0) > 0:
            st["__suppress_warp_frames"] -= 1
            return
    except Exception:
        pass

    # ▼ デバッグログ：どこからどこへワープしているか確認用
    if DEV_MODE:
        cur_map = getattr(game_state, "current_map_id", None)
        px = getattr(game_state, "player_x", 0.0) / TILE
        py = getattr(game_state, "player_y", 0.0) / TILE
        print(
            f"[WARP] from={cur_map} ({px:.2f},{py:.2f}) "
            f"to={map_id} tile={spawn_tile_xy}"
        )
            
    game_state.current_map_id = map_id
    tx, ty = spawn_tile_xy
    game_state.player_x = tx * TILE + TILE * 0.5
    game_state.player_y = ty * TILE + TILE * 0.5

    # ★同フレーム内で即同期（テクスチャ/スプライト/床特効まで）
    load_current_map_assets()
    game_state._last_loaded_map_id = map_id  # 二重ロード防止
    # 次の描画を1回スキップして“混在フレーム”を消す
    global just_teleported
    just_teleported = True

# --- lab前：ドア接近で“動画→イベント→ワープ”一連を一回だけ -------------------

# def _dbg_log_doctor_seq_state():
#     """lab前ドアの発火条件をまとめて可視化（開発用）"""
#     if game_state.current_map_id != "forest_end":
#         return
#     # ドア近接時のみログ（ノイズ抑制）
#     near = _player_near_any_symbol(('D',), 120.0)
#     if not near:
#         return
#     from pathlib import Path
#     layout = MAPS["forest_end"]["layout"]
#     D_count = sum(r.count('D') for r in layout)
#     played = _has_played_video("forest_end", DOCTOR_SEQ_ID)
#     is_cut = getattr(game_state, "is_cutscene", False)
#     now = pygame.time.get_ticks()
#     cd  = getattr(game_state, "cinematic_cooldown_ms", 0)
#     movie_path = Path(BASE_DIR) / "assets" / "movies" / "doctor_burst_out.mp4"
#     print("[DOCTORDBG]",
#           f"D_count={D_count}",
#           f"nearD={near}",
#           f"played={played}",
#           f"is_cutscene={is_cut}",
#           f"cooldown_ok={now>=cd}",
#           f"movie_exists={movie_path.exists()}")

def _is_near_forest_end_door(radius_px: float = 96.0) -> bool:
    """'D' 記号 or doors[] の座標のいずれかに半径内で近接しているか"""
    if game_state.current_map_id != "forest_end":
        return False
    R2 = radius_px * radius_px
    px, py = game_state.player_x, game_state.player_y
    layout = MAPS["forest_end"]["layout"]
    # 1) レイアウト上の 'D'
    for y, row in enumerate(layout):
        for x, ch in enumerate(row):
            if ch == 'D':
                cx = x * TILE + TILE * 0.5
                cy = y * TILE + TILE * 0.5
                dx, dy = px - cx, py - cy
                if dx*dx + dy*dy <= R2:
                    return True
    # 2) doors リストの座標（'D' が床に置換されても検出可能）
    for d in MAPS["forest_end"].get("doors", []):
        x, y = d.get("tile", (None, None))
        if x is None or y is None:
            continue
        cx = x * TILE + TILE * 0.5
        cy = y * TILE + TILE * 0.5
        dx, dy = px - cx, py - cy
        if dx*dx + dy*dy <= R2:
            return True
    return False

def _doors_opened_for_forest_end() -> bool:
    """観音ドアのどちらかが開いていれば True（セーブ後 list→set の型ゆらぎも吸収）"""
    opened = game_state.FLAGS.get("doors_opened", set())
    if isinstance(opened, list):
        opened = set(tuple(t) for t in opened)
        game_state.FLAGS["doors_opened"] = opened
    target = {("forest_end", 10, 4), ("forest_end", 10, 5)}
    return bool(opened & target)

def maybe_run_doctor_gate_once() -> None:
    """
    【一本化版】lab前ドアの“動画→イベント→ワープ”シーケンスを一度だけ実行。
    発火条件：
      - 現在地が forest_end で、
      - まだ再生済み（DOCTOR_EVENT_ID）でなく、
      - クールダウン/カットシーン中でなく、
      - 「ドアに近接」が成立。
    実行：
      - 再生済みを先にマーク（スキップでも二度出さない）
      - cinematics.run_doctor_gate_sequence() に委譲
    """
    if game_state.current_map_id != "forest_end":
        return
    if cin_has_played("forest_end", DOCTOR_EVENT_ID):
        return
    if not cin_can_fire():
        return
    if not (_is_near_forest_end_door(96.0) or _doors_opened_for_forest_end()):
        return
    # スキップでも一度扱いにするため、先に既視化
    cin_mark_played("forest_end", DOCTOR_EVENT_ID)
    #  grant_key=False（lab内へ）
    cin_run_doctor_gate(
        screen, BASE_DIR,
        grant_key=False,
        target_face="E",   # ★ lab_entrance に入った直後の向き（東向き）     
        toast_cb=lambda m, ms: toast.show(m, ms=ms),
        video_audio="assets/sounds/se/映写機.mp3.enc",
        sound_manager=sound_manager,
    )

def _footrev_tile_to_index_mapping(cfg: dict) -> dict[tuple[int,int], int]:
    """(x,y) -> 1..N の対応表を作る（高速化のため毎回生成でもNが小さいので十分軽い）"""
    steps = cfg.get("steps") or []
    return {tuple(pos): i for i, pos in enumerate(steps, start=1)}

# ★ ロード処理が積んだ「確定スポーン予約」を、次フレームで必ず適用する
def _apply_pending_load_spawn_if_any():
    try:
        st = getattr(game_state, "state", None)
        if not isinstance(st, dict):
            return
        tgt = st.pop("__pending_load_spawn", None)
        if not isinstance(tgt, dict):
            return
        t_map = tgt.get("map")
        t_x   = float(tgt.get("x", game_state.player_x))
        t_y   = float(tgt.get("y", game_state.player_y))
        t_a   = float(tgt.get("angle", game_state.player_angle))

        # マップが違えば即座に切替（ただし assets は 1 回だけ）
        if t_map and t_map != game_state.current_map_id:
            game_state.current_map_id = t_map
            load_current_map_assets()
            game_state._last_loaded_map_id = t_map

        # 位置と向きを“最後に”上書き（他の処理が触れても最終的に勝つ）
        game_state.player_x = t_x
        game_state.player_y = t_y
        game_state.player_angle = t_a

        # 画面のチラつきを避けるため、次の描画をスキップ
        global just_teleported
        just_teleported = True

        # 念のため：自動ワープ抑止フレームを少なくとも 1 に維持
        st["__suppress_warp_frames"] = max(1, int(st.get("__suppress_warp_frames", 0)))
    except Exception:
        pass

# -------------------------------
# メインループ
# -------------------------------
last_tile = (
    int(game_state.player_x // TILE),
    int(game_state.player_y // TILE),
)
just_teleported = False  # テレポート直後判定用フラグ

while True:
    ensure_current_map_assets_synced() # 強制同期
    # ---- 1. イベント処理 ----
    for event in pygame.event.get():
        # --- フォールバック・トーストのドレイン（毎フレーム） ---
        try:
            st = getattr(game_state, "state", {})
            if isinstance(st, dict):
                q = st.get("__toast_queue", [])
                # 溜まっているものをすべて表示（順に）
                while q:
                    m = q.pop(0)
                    # UIトーストとして確実に表示
                    toast.show(str(m))
        except Exception:
            pass

        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        # F5（クイックセーブ）、F9（クイックロード）
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F5:
                # ▼ クイックセーブは UI 側で確実にトーストを出したいので、
                #    save_system 側の通知は抑止（notify=False）し、
                #    ここで明示的に表示します。
                ok = save_game("slot1", meta_comment="クイックセーブ", notify=False)
                # 念のため：トーストブリッジが切れていても UI 側は必ず表示
                if ok:
                    toast.show("データをセーブしました。")
                
                if sound_manager.has_se("save_ok"): # ★ 成功SE
                    sound_manager.play_se("save_ok")
                else:
                    toast.show("セーブに失敗しました。")
                
                if sound_manager.has_se("save_fail"): # ★ 失敗SE
                    sound_manager.play_se("save_fail")            

            if event.key == pygame.K_F9:
                from core import toast_bridge
                toast_bridge.bind_toast(toast)  # ロード"前"に橋渡し
                ok = load_game("slot1")
                toast_bridge.bind_toast(toast)  # 念のため
                if ok:
                    toast_bridge.show("ロードしました。", ms=4000)
                if sound_manager.has_se("load_ok"): # ★ 成功SE
                    sound_manager.play_se("load_ok")

        # メニュー表示中：メニューへイベントを流す
        if menu_scene is not None:
            result = menu_scene.handle_event(event)
            if result == "close":
                # 閉じるSE
                if sound_manager.has_se("menu_close"):
                    sound_manager.play_se("menu_close")
                menu_scene = None
            elif result == "save_request":
                toast.show("セーブは未実装です")
            elif isinstance(result, str) and result.startswith("use:"):
                item_id = result.split(":", 1)[1]
                toast.show(f"{item_id} を使った（ダミー）")
            continue  # メニュー中は本編のキー操作無効

        # Eキーのデバウンス
        if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
            now = pygame.time.get_ticks()
            if now - last_use_ms < USE_COOLDOWN:
                continue
            last_use_ms = now

            cur_map_id = game_state.current_map_id
            cur_map = MAPS[cur_map_id]

            # 1) 拾得
            msg = try_pickup_item(cur_map)
            if msg:
                print(msg)
                toast.show(msg)
                sound_manager.play_se("get_item")  # ← 取得時SEを再生

            # 2) ドア解錠
            msg, opened = try_open_door(cur_map_id, cur_map)
            if msg:
                print(msg); toast.show(msg)

            if opened:
                # 実マップの壁を床に変える（'#' → '.'）
                tx, ty = opened["tile"]
                set_tile(cur_map["layout"], tx, ty, '.')  # walkable床に置換
                # ★ レイアウト変更に合わせてタイルキャッシュ更新
                game_state.current_tile_grid = build_tile_grid(cur_map["layout"])
                # ★ 永続フラグ
                game_state.FLAGS.setdefault("doors_opened", set()).add((cur_map_id, tx, ty))
                # ★解錠SE
                sound_manager.play_se("door_unlock")

                # ★ ドア用トーストを即時クリア（“発火位置に貼る”タイプの残りを消す）
                try:
                    world_toast.clear_tile(cur_map_id, (tx, ty))
                except Exception:
                    pass

                # ★ ドア用トーストの“再点灯”を短時間ブロック（開錠直後の踏み直し対策）
                game_state.state["__door_prompt_block_until"] = pygame.time.get_ticks() + 1200  # ms
                game_state.state["__door_prompt_block_tile"]  = (tx, ty)

            # 3) スイッチ押下
            msg = try_press_switch(cur_map_id, cur_map)
            if msg:
                print(msg); toast.show(msg)
                # ★ スイッチで地形が変わる場合があるため、タイルキャッシュを更新
                game_state.current_tile_grid = build_tile_grid(cur_map["layout"])
            # --- 押下結果に応じてSEを再生（1フレーム限定フラグ） interactions.py → try_press_switch　---
            try:
                result = game_state.state.pop("__last_switch_result", None)  # 取り出したら即クリア
                if result == "solved":
                    # クリア優先：あれば専用SE、無ければOK SEにフォールバック
                    if sound_manager.has_se("switch_solved"):
                        sound_manager.play_se("switch_solved")
                    elif sound_manager.has_se("switch_ok"):
                        sound_manager.play_se("switch_ok")
                elif result == "ok":
                    if sound_manager.has_se("switch_ok"):
                        sound_manager.play_se("switch_ok")
                elif result == "ng":
                    if sound_manager.has_se("switch_ng"):
                        sound_manager.play_se("switch_ng")
            except Exception:
                pass

            #  ★ クリア直後の“最終仕上げ”適用（1回だけ）
            #    interactions.try_press_switch(...) の中で switch_solved=True になったフレームで、
            #    ここが実行されます。レイアウト再構成（X↔.）→ lit 差し替え まで一括で行い、
            #    さらにタイルグリッドを作り直して描画に反映します。
            if game_state.state.get("switch_solved") and not game_state.state.get("switch_applied"):
                game_state.current_tile_grid = build_tile_grid(MAPS[cur_map_id]["layout"])
                game_state.state["switch_applied"] = True  # 一回化フラグ（次フレーム以降は実行されない）

            # 4) 倒木（斧が必要／3ヒット進捗）
            msg = try_chop_tree(cur_map_id, cur_map, sound_manager)
            if msg:
                if game_state.state.pop("suppress_instant_toast", False):
                    # ムービー後に出すので、今は出さない
                    pass
                else:
                    print(msg); toast.show(msg)
                _process_cinematic_queue()
                # ★ 倒木フラグに基づいて橋を即適用（ロード待ちにしない）
                _apply_trees_state_for_map(cur_map_id)
                # ★ タイルグリッド更新（衝突と床描画のため）
                game_state.current_tile_grid = build_tile_grid(cur_map["layout"])
                # 大木(O)の見た目スプライトも即時同期（念のため）
                build_world_sprites_for_map(cur_map_id)

            # 5) 守人解除（供物が必要／霧を晴らす）
            msg = try_offer_guardian(cur_map_id, cur_map)
            build_world_sprites_for_map(cur_map_id)  # Mが消えたら見た目も消す（視覚レイヤも即反映）
            if msg:
                # ★ 永続化フラグ（セーブ対象）
                game_state.FLAGS.setdefault("fog_cleared", set()).add(cur_map_id)

                # ★ 霧の適用（フラグに基づいて確実に消す）
                _apply_fog_state_for_map(cur_map_id)

                # 守人の適用も同時に
                _apply_guardian_state_for_map(cur_map_id)

                # world_sprites を“もう一度”作り直す（霧や守人の残骸を消す）
                build_world_sprites_for_map(cur_map_id)

                # タイルグリッド更新（まとめて1回）
                game_state.current_tile_grid = build_tile_grid(cur_map["layout"])

                # 霧が晴れるムービーを再生（1回だけ）
                
                q = game_state.state.setdefault("cinematic_queue", deque())
                q.append({
                    "kind": "video",
                    "id": f"fog_clear@{cur_map_id}",                # 再生済み管理用の一意ID
                    "video_path": "assets/movies/fog_cleared.mp4", 
                    "audio_path": "assets/sounds/se/魔法陣を展開.mp3.enc", 
                    "toast_on_end": "霧が晴れた……",                 # 見終わった後のトースト
                    "toast_on_skip": "……（スキップ）",
                })

                # --- メインループ内（入力処理・移動・当たり判定が終わり、マップIDが確定した後）---

                # 一回だけデバッグダンプ（このマップにいる間は再出力しない）
                if game_state.current_map_id == "forest_end" and not game_state.state.get("_dbg_dumped"):
                    _debug_dump_lab_gate()
                    game_state.state["_dbg_dumped"] = True

                # オートトリガ呼び出し群
                maybe_run_doctor_gate_once()
                
                _process_cinematic_queue()

            # 6) 出口（ '>' ）：遷移確認モードへ
            msg = try_use_exit(cur_map_id, cur_map)
            if msg:
                print(msg); toast.show(msg)

        if game_state.state.get("switch_solved") and not game_state.state.get("switch_applied"):
            # いまのマップのパズルIDを取得（無ければ "switch_A"）
            pid = (MAPS[cur_map_id].get("puzzle") or {}).get("id", "switch_A")

            # puzzles_solved を「常に list」として扱う（set が来てもここで矯正）
            ps = game_state.FLAGS.setdefault("puzzles_solved", [])
            if isinstance(ps, set):
                ps = list(ps)
                game_state.FLAGS["puzzles_solved"] = ps

            pair = (cur_map_id, pid)

            # 既存要素は ["map","id"] 形式の可能性もあるので tuple で比較して重複回避
            if not any(tuple(x) == pair for x in ps):
                ps.append(pair)

            # その場でも開放を反映
            game_state.current_tile_grid = build_tile_grid(MAPS[cur_map_id]["layout"])

            # ★ “一回化”フラグのみを立てる（switch_solved は触らないのが安全）
            game_state.state["switch_applied"] = True

        # map_confirm モード中の 「Y/N」
        if game_state.state.get("mode") == "map_confirm":
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_y, pygame.K_RETURN):
                    sound_manager.play_se("kazamidori_y")
                    trig = game_state.state.get("pending_trigger") or {}
                    target_map = trig.get("target_map")
                    target_pos = trig.get("target_pos")

                    if target_map and target_pos:
                        # --- テレポート実行 ---
                        game_state.current_map_id = target_map
                        game_state.player_x = target_pos[0] * TILE + TILE // 2
                        game_state.player_y = target_pos[1] * TILE + TILE // 2

                        # === 到着時の向きを指定できるようにする ======================
                        # トリガーに "target_angle"（ラジアン） もしくは
                        # "target_face"（'N','E','S','W' のいずれか）を持たせた場合に反映。
                        # ※ "target_angle" が 2πより大きい（=度のつもり）なら度→ラジアン変換。
                        ang = trig.get("target_angle", None)
                        face = trig.get("target_face", None) or trig.get("face", None) or trig.get("look", None)

                        if ang is None and isinstance(face, str):
                            f = face.strip().upper()[:1]
                            # 右向き=東=0 を基準に、画面座標系に合わせて割り当て
                            # E:0, S:π/2, W:π, N:3π/2
                            face_table = {"E": 0.0, "S": math.pi * 0.5, "W": math.pi, "N": math.pi * 1.5}
                            ang = face_table.get(f, None)

                        if isinstance(ang, (int, float)):
                            # もし誤って度で渡されたら（>2πを想定）自動で度→ラジアンに補正
                            if abs(ang) > (2.0 * math.pi + 1e-3):
                                ang = math.radians(ang)
                            game_state.player_angle = ang % (2.0 * math.pi)
                        # =====================================================================
 
                        # 新マップのアセット一括再ロード（テクスチャ＋タイル等）
                        load_current_map_assets()

                        # === 追加：マップ着地後の“プロンプト抑止”印（Enter誤爆ガード 0.5秒） ===
                        st = game_state.state
                        st["__map_prompt_block_until"] = pygame.time.get_ticks() + 500  # 500ms

                        # ▼lab_entrance 用：ロード直後や遷移直後に点滅状態を正規化
                        if game_state.current_map_id == "lab_entrance":
                            st = game_state.state
                            prog = st.get("switch_progress", [])
                            solved = st.get("switch_solved", False)
                            blink = st.setdefault("switch_blink_active", set())

                            if st.get("switch_solved", False):
                                # クリア済みは表示しない（消灯）
                                blink.clear()
                            else:
                                # 未クリアは prog から再構築（ズレがあれば自動修正）
                                if set(blink) != set(prog):
                                    blink.clear()
                                    blink.update(prog)

                            # クリア済みなら点滅は消す
                            if solved:
                                blink.clear()
                            else:
                                # 未クリアなら「正解済みのスイッチだけ」点滅に載せ直す
                                blink.clear()
                                blink.update(prog)   # prog は ["b","d",...] のような配列を想定

                        # 再トリガー防止
                        last_tile = (int(target_pos[0]), int(target_pos[1]))
                        print(f"{trig.get('event','move')} で {target_map} へ移動！")

                        # ★ 追加：到着直後もしばらくは確認プロンプトを出さない
                        game_state.state["__map_prompt_block_until"] = pygame.time.get_ticks() + PROMPT_COOLDOWN_MS

                    # 状態リセット
                    game_state.state["mode"] = "normal"
                    game_state.state["pending_trigger"] = None

                elif event.key in (pygame.K_n, pygame.K_ESCAPE):
                    # キャンセル
                    sound_manager.play_se("kazamidori_n")
                    game_state.state["mode"] = "normal"
                    game_state.state["pending_trigger"] = None

                    # ★ 追加：今はまだ同じ '<' / '>' 上にいる → 再点灯防止
                    game_state.state["__map_prompt_block_until"] = pygame.time.get_ticks() + PROMPT_COOLDOWN_MS

            continue  # map_confirm 中は他処理を飛ばす

        if event.type == pygame.KEYDOWN:
            # Esc/M でメニューを開く
            if event.key in (pygame.K_ESCAPE, pygame.K_m):
                # 開閉専用se
                if sound_manager.has_se("menu_open"):
                    sound_manager.play_se("menu_open")
                menu_scene = MenuScene(sound_manager=sound_manager)
                continue

            # F3（Ctrl/⌘ 必須）でデバッグ表示トグル：ここに一元化
            if event.key == pygame.K_F3:
                mods = pygame.key.get_mods()
                ctrl_or_cmd = mods & (pygame.KMOD_CTRL | pygame.KMOD_META)
                if not ctrl_or_cmd:
                    toast.show("F3は Ctrl/⌘ と一緒に押してください（必要なら Fn も）")
                    continue
                if not DEV_MODE:
                    toast.show("DEV_MODE が OFF のため無効（起動時は DEV_MODE=1 を設定）")
                    continue
                SHOW_DEBUG_OVERLAY = not SHOW_DEBUG_OVERLAY
                toast.show(f"デバッグ表示: {'ON' if SHOW_DEBUG_OVERLAY else 'OFF'}")
                continue

            # F11 でフルスクリーン切り替え
            # ・Esc はイベントスキップ等に使っているので、フルスクリーンとは分離
            if event.key == pygame.K_F11:
                is_fs = toggle_fullscreen()
                # トーストが使える状況なら、状態を軽く表示
                try:
                    toast.show(f"フルスクリーン: {'ON' if is_fs else 'OFF'}")
                except Exception:
                    # タイトルなどトーストが無い文脈でも落ちないようにしておく
                    pass
                continue

            # --- DEV: F8で追跡者をプレイヤー背後に強制出現 ---
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F8:
                _spawn_chaser_behind(distance_px=96.0)  # ← ここを背後版に
                try:
                    from core import toast_bridge
                    toast_bridge.show("[DEV] 追跡者を出現させました（背後）")
                except Exception:
                    pass

    # ==== ゲーム更新はメニューが開いていないときだけ ====
    is_menu_open = (menu_scene is not None)

    if not is_menu_open:
        # ← ここで一回だけ取得（以降で共通利用）
        keys = pygame.key.get_pressed()

        # --- プレイヤー移動（モジュール化 core/player.py） ---
        # ① まず移動処理
        moved, curr_tile = handle_movement(
            keys=keys,                 # ← 取得した keys を渡す
            state=game_state,
            is_wall=is_wall,
            tile_size=TILE,
        )
        # ② 次に回転処理（←→で向きが変わったかどうか）
        rotated = handle_rotation(keys=keys, state=game_state)

    # ----------------------------------------------------------
    # ★足音（改良版）
    #   ・歩行:  前後キー押下 かつ 実際に移動できたフレーム（moved=True）
    #   ・回転:  方向転換が発生したフレーム（rotated=True）
    #   → どちらか片方でも満たせば “ループ再生を開始/維持”
    #   → どちらも満たさなければ “停止”
    #   ※ 同じ name="footstep" チャンネルを使うので二重になりません
    # ----------------------------------------------------------
    def _footstep_env_key(map_id: str) -> str:
        mid = (map_id or "").lower()
        # 明示指定がある場合:  maps[map_id]["footstep"] == "forest|lab|tunnel"
        try:
            from maps import MAPS
            explicit = (MAPS.get(map_id, {}).get("footstep") or "").lower()
            if explicit in ("forest", "lab", "tunnel"):
                return f"step_{explicit}"
        except Exception:
            pass
        # 自動判定（必要に応じて規則を足してください）
        if mid.startswith("forest"):
            return "step_forest"
        if ("dungeon" in mid) or ("tunnel" in mid) or ("underground" in mid):
            return "step_tunnel"
        if ("lab" in mid) or ("research" in mid) or ("lab" in mid):
            return "step_lab"
        return "step_forest"

    # 前進/後退キーが押されているか（例: ↑↓ / W S）
    forward_pressed = keys[pygame.K_UP] or keys[pygame.K_w]
    backward_pressed = keys[pygame.K_DOWN] or keys[pygame.K_s]
    walking_input = forward_pressed or backward_pressed

    footstep_key = _footstep_env_key(game_state.current_map_id)

    # --- カットシーン（ムービー/イベント）中は足音を完全停止し、再開もしない ---
    if getattr(game_state, "is_cutscene", False) or getattr(game_state, "suppress_footsteps", False):
        sound_manager.stop_loop(name="footstep", fade_ms=80)
    else:
        # 「歩けた」または「回転した」ならループを鳴らす（同時入力でも1本だけ）
        if (walking_input and moved) or rotated:
            sound_manager.play_loop(name="footstep", se_key=footstep_key, fade_ms=50)
        else:
            sound_manager.stop_loop(name="footstep", fade_ms=80)

        # タイル跨ぎ時の処理（ここが唯一の“タイル跨ぎ”入口）
    if moved and curr_tile is not None and curr_tile != last_tile:
        check_map_triggers()                         # 出口・階段などのタイル上トリガ
        _check_proximity_triggers_from_map()         # 近接型トリガ（追跡者/ムービー 等）
        last_tile = curr_tile
        _cancel_confirm_if_moved_off_tile()          # 確認ダイアログ中に動いたら解除
        # 必要ならここでムービーキュー処理などを呼び出す
        # _process_cinematic_queue()
        
        is_forest = game_state.current_map_id.startswith("forest") # 森マップだけで動くようガード
        # 近接ムービーの発火（旧 if move_x or move_y ブロックから移設）
        # 近接ムービー発火（fog）
        cin_trigger_once(
            screen, BASE_DIR,
            video_id="assets/movies/fog_block_intro.mp4", # ムービー
            audio_path="assets/sounds/se/死後の世界.mp3.enc", # ムービーの音
            symbols=('F','f'),
            radius_px=96.0,
            enable_if=lambda: game_state.current_map_id not in game_state.FLAGS.get("fog_cleared", set()),
            # ▼ムービー終了後のトーストと、スキップ時のトーストを追加
            toast_on_end="霧が立ちこめて進めない……",
            toast_on_skip="……（スキップ）",
            toast_cb=lambda m, ms: toast.show(m, ms),
            # ▼▼▼ SoundManager を渡す（VideoEvent → play_video が voice音量に連動させる）
            sound_manager=sound_manager,
        )

        # river
        cin_trigger_once(
            screen, BASE_DIR,
            video_id="assets/movies/river_warning.mp4",
            audio_path="assets/sounds/se/河原.mp3.enc",
            symbols=('w','W'),
            radius_px=96.0,
            enable_if=lambda: True,
            toast_on_end="川の流れが激しい…橋があれば渡れそうだ。",
            toast_on_skip="……（スキップ）",
            toast_cb=_toast_adapter,  
            sound_manager=sound_manager,
        )

        # trunk
        cin_trigger_once(
            screen, BASE_DIR,
            video_id="assets/movies/trunk_intro.mp4",
            audio_path="assets/sounds/se/河原.mp3.enc",
            symbols=('O',),
            radius_px=96.0,
            enable_if=lambda: True,
            toast_on_end="太い大木が行く手をふさいでいる…",
            toast_on_skip="……（スキップ）",
            toast_cb=_toast_adapter,  
            sound_manager=sound_manager,
        )

        # --- ★重要：ムービー再生があった場合でも、戻ってきたら環境音を再適用 ---
        # ここは cin_trigger_once が“再生しなかった”場合でも呼んでOK（無害）。
        # ループ環境音が止まっていれば再開し、同じ音が鳴っていれば内部でノーオペになります。
        try:
            _apply_map_ambience()
        except Exception:
            pass

        last_tile = curr_tile
        _cancel_confirm_if_moved_off_tile()
        # _process_cinematic_queue()

        # --- 視点回転（←→キー core/player.py）---
        rotated = handle_rotation(
            keys=keys,
            state=game_state,
            rot_per_tick=0.04,      # お好みで調整
            # key_left=pygame.K_LEFT, key_right=pygame.K_RIGHT  # 変更したい場合だけ指定
        )

    # # === 追跡者：移動＆捕捉チェック（毎フレーム） ===
    _update_chaser_and_check_caught(clock.get_time() / 1000.0)

    # 毎フレーム、動画のキューを回す
    _process_cinematic_queue()                

    # ★ムービー終了後などに環境音が止まっていたら復旧（同じ音ならノーオペ）
    try:
        _apply_map_ambience()
    except Exception:
        pass

    def get_portrait_hint(cur_map: dict) -> str | None:
        puzzle = cur_map.get("puzzle")
        if not puzzle:
            return None
        portraits = puzzle.get("portraits", {})
        if not portraits:
            return None

        # 近接判定（肖像画タイル中心に半径r）
        from core.config import TILE
        px, py = game_state.player_x, game_state.player_y
        r = 64.0  # お好みで
        for label, info in portraits.items():
            tx, ty = info["pos"]
            cx, cy = tx * TILE + TILE/2, ty * TILE + TILE/2
            if (px - cx)**2 + (py - cy)**2 <= r * r:
                look = info.get("look", "?")
                dir_ja = {"N":"北","E":"東","S":"南","W":"西"}.get(look, look)
                return f"この肖像画は{dir_ja}を見ている…"
        return None

    # 毎フレーム更新
    cur_map = MAPS[game_state.current_map_id]
    hint_text = get_portrait_hint(cur_map)

    if hint_text:
        draw_label(
            screen,
            hint_text,
            size=18,
            pos=(WIDTH//2, HEIGHT - 24),
            anchor="midbottom",
            bg_color=(0, 0, 0, 140),
        )
        just_teleported = False

    # ---- 6. 描画 ----
    clock.tick(60)

    # ★ 直前フレームの経過時間（ms）→ 秒に
    dt_sec = clock.get_time() / 1000.0
    # ★ メニューを開いていないときだけ進める（ポーズ扱い）
    if menu_scene is None:
        game_state.playtime_sec += dt_sec

    def draw_minimap(surface, *, box_size: int = 96, margin: int = 8):
        inv = game_state.inventory
        if inv.get("map_chart", 0) <= 0:
            return

        cur_map = MAPS[game_state.current_map_id]
        layout = cur_map["layout"]
        H = len(layout)
        W = len(layout[0]) if H else 0
        if H == 0 or W == 0:
            return

        # ミニマップのスケール
        s = min(box_size / W, box_size / H)
        map_w_px = int(W * s)
        map_h_px = int(H * s)
        x0 = WIDTH - margin - map_w_px
        y0 = margin

        panel = pygame.Surface((map_w_px, map_h_px), pygame.SRCALPHA)
        pygame.draw.rect(panel, (0,0,0,160), panel.get_rect(), border_radius=8)
        pygame.draw.rect(panel, (255,255,255,40), panel.get_rect(), width=1, border_radius=8)

        # ❶ 地形描画
        for j, row in enumerate(layout):
            for i, ch in enumerate(row):
                walkable = TILE_TYPES.get(ch, {"walkable": False})["walkable"]
                rx = int(i*s); ry = int(j*s)
                rw = max(1, int((i+1)*s) - rx)
                rh = max(1, int((j+1)*s) - ry)
                rect = (rx, ry, rw, rh)
                if ch == '>': color, border = MMC["exit"], MMC["border"]
                elif ch == '<': color, border = MMC["entrance"], MMC["border"]
                elif walkable: color, border = MMC["floor"], None
                else: color, border = MMC["wall"], None
                pygame.draw.rect(panel, color, rect)
                if border:
                    pygame.draw.rect(panel, border, rect, width=1)

        # ❷ アイテム描画（羅針盤所持のみ）
        if inv.get("item_compass",0) > 0:
            item_colors = {
                "key_forest": (240,210,50,255),
                "key_lab":    (240,210,50,255),
                "spirit_orb": (120,220,255,255),
                "axe":        (180,110,60,255),
                "map_chart":  (180,180,180,255),
                "item_compass": (180,180,180,255)
            }
            # ★ アイテムマーカーの大きさ調整ポイント
            #    - 係数(0.5)を変えると全体の大きさが変わります
            #    - 第1引数(2)が「最小サイズ(px)」です            
            dot = max(4, int(s*0.5))  # 最小4px、スケールに応じて
            for raw in cur_map.get("items",[]):
                it = normalize_item_entry(raw)
                if not _is_unpicked_item(game_state.current_map_id,it):
                    continue
                tx, ty = it["tile"]
                cx = int((tx+0.5)*s)
                cy = int((ty+0.5)*s)
                t = it.get("type","misc")
                color = item_colors.get(t,(230,230,230,255))
                pygame.draw.circle(panel, color, (cx,cy), dot)
                pygame.draw.circle(panel, (0,0,0,180), (cx,cy), dot, width=1)

        # ❸ プレイヤー描画
        px_t = game_state.player_x / TILE
        py_t = game_state.player_y / TILE
        cx = px_t*s
        cy = py_t*s
        ang = game_state.player_angle
        r_tip = max(6, int(s))  # 先端の長さ
        r_base = r_tip*0.8
        tip = (cx + math.cos(ang)*r_tip, cy + math.sin(ang)*r_tip)
        back_cx = cx - math.cos(ang)*r_base
        back_cy = cy - math.sin(ang)*r_base
        nx = math.cos(ang+math.pi/2)*r_base*0.6
        ny = math.sin(ang+math.pi/2)*r_base*0.6
        left = (back_cx+nx, back_cy+ny)
        right = (back_cx-nx, back_cy-ny)
        pygame.draw.polygon(panel,(255,255,255,230),[tip,left,right])
        pygame.draw.polygon(panel,(0,0,0,220),[tip,left,right],width=1)

        # ❹ 追跡者描画
        ch = game_state.state.get("chaser",{})
        if ch.get("active") and ch.get("map_id")==game_state.current_map_id:
            try:
                cx_t = float(ch["x"])/TILE
                cy_t = float(ch["y"])/TILE
                mx = int(cx_t*s)
                my = int(cy_t*s)
                dot_r = max(6,int(s))  # ミニマップに合ったサイズ アイテムマーカーと同じ
                pygame.draw.circle(panel,(220,40,40,255),(mx,my),dot_r)
            except Exception:
                pass

        # ❺ エンディングシンボル
        end_points = _collect_end_points_for_map(cur_map)
        symbol_surf = _get_ending_symbol_surface()
        symbol_dot = max(15,int(s))  # 少し大きめに見えるサイズ
        for wx,wy in end_points:
            mx = int(wx/TILE*s)
            my = int(wy/TILE*s)
            scaled_surf = pygame.transform.smoothscale(symbol_surf,(symbol_dot,symbol_dot))
            panel.blit(scaled_surf,(mx-symbol_dot//2,my-symbol_dot//2))

        # 最後に panel を画面に描画
        surface.blit(panel,(x0,y0))

    #  フレーム 
    # -----------------------------------------
    # フレームのワールドトーストを初期化
    begin_world_toasts()  
    
    _apply_pending_load_spawn_if_any()
    # ▼ どんな経路でロードされても、描画前に一度は自己修復
    _ensure_special_ready_for_current_map(verbose=False)

    # ★：自動ムービー＆デバッグ
    tick_auto_events_and_debug()
    # 壁や床の描画（Zバッファ取得）
    zbuf = draw_rays()

    # 風見鶏ガイド（マップ移動の目印）
    draw_weathercock_guides(screen, zbuf) 

    # エンディング床（'E'）シンボル
    draw_ending_symbols(screen, zbuf)

    # ★ 追跡者の赤い○（ビルボード）を描画
    _draw_chaser_billboard(screen, zbuf) # ← 場所確認には第2引数のzbufを外すと壁に透ける。
    
    # 取得しないスプライト（守人など）、透明な壁
    draw_world_sprites(zbuf)

    # アイテム（スプライト）描画（壁との前後関係をZバッファで判定）
    draw_items(zbuf)

    # 近接ラベル（ドア／スイッチも統一UIで）
    draw_interaction_hints(zbuf)

    # デバッグオーバーレイ（DEV_MODE のときだけ有効）
    if DEV_MODE and SHOW_DEBUG_OVERLAY:
        draw_inventory_overlay(screen)

    # Y/N メッセージ
    draw_map_confirm_prompt(screen)
    # ミニマップ
    draw_minimap(screen)

    # 今フレーム分を一括表示
    flush_world_toasts(screen)  

    # メニューを先に最前面へ
    if menu_scene is not None:
        menu_scene.draw(screen, WIDTH, HEIGHT)

    # ★ デバッグ：敵の赤丸を重ね描き（最前面・任意）
    if hasattr(game_state, "current_enemies"):
        for ch in game_state.current_enemies:
            # カメラオフセットを使っていなければ (0,0) でOK
            ch.draw_debug_2d(screen, (0.0, 0.0))
            
    # ---- 近接ラベル（最前面に） -----------------------------------------
    # ※ここに移動：壁/スプライト/メニュー/ミニマップより前面で、トーストの直前に
    #   ドアやスイッチの「E：〜」「◯◯が必要」を最上位レイヤで描く
    #
    # デバウンスのため、draw_interaction_hints() 内で描画候補を列挙しつつ
    # _hint_session_should_draw() で同一ヒントの出し過ぎを抑えます。
    #
    # 実装：既存の draw_interaction_hints を薄くラップする関数を用意します。
    # ---- 近接ラベル（最前面に） -----------------------------------------
    def _draw_interaction_hints_front(zbuf):
        """
        ドア・スイッチ等の近接ヒントを“最前面レイヤ”で描画する。
        - ドアが壁で隠れて見えない場合は、正面1タイルが床なら床側に貼る
        - それでも不可視なら画面固定ピルにフォールバック
        ※「ドアを開けたあとは walkable なのでヒントは出ない」挙動は維持
        """
        cur_map = MAPS[game_state.current_map_id]
        layout  = cur_map["layout"]

        # プレイヤー位置
        px, py = game_state.player_x, game_state.player_y
        cx, cy = int(px // TILE), int(py // TILE)

        is_front = False  # ← まずは関数スコープに用意（ループで上書き）

        # 正面1/2マス（“壁で隠れる”ケースに備えて床へのフォールバックで使う）
        fx1, fy1 = _front_tile(px, py, game_state.player_angle)        # 正面1マス
        fx2, fy2 = (fx1 + (fx1 - cx), fy1 + (fy1 - cy))                # 正面2マス

        # 距離閾値（R の2乗で比較して sqrt を避ける）
        # 既定: 80px → 少しゆるめて 110px（= 80 * 1.375）
        R2 = (110.0 * 110.0)

        drew_any = False

        # -----------------------------
        # 1) ドア（鍵あり/なしで文言分岐）
        # -----------------------------
        for door in cur_map.get("doors", []):
            tx, ty = door["tile"]
            wx, wy = _tile_center(tx, ty)

            # 既に開いているドアは完全にスキップ
            if door.get("opened"):
                continue

            # 距離が遠いなら対象外
            if _dist2_px(px, py, wx, wy) > R2:
                continue

            # すでに“床化”しているドア（= 開いているドア）は対象外にする
            #    ドアを開けたあと set_tile(..., '.') で床に変えているので、
            #    ここで現在のタイル文字を見て、walkable ならスキップします。
            try:
                ch = layout[ty][tx]  # 現在のタイル文字を取得
                # TILE_TYPES の walkable が True なら床など“通行可能”とみなす
                if TILE_TYPES.get(ch, {"walkable": False}).get("walkable", False):
                    continue  # 開いているドアなのでヒントは出さない
            except Exception:
                # 範囲外など何かおかしければ、安全側に倒してスキップ
                continue

            # ★ ここまで来た＝「ヒント対象として扱うドア」
            #    デバッグ出力して、opened やタイル文字を確認
            print(
                f"[DEBUG] hint for door at {game_state.current_map_id} "
                f"tile=({tx},{ty}) opened={door.get('opened')} ch={ch!r}"
            )
            # ここまで来た時点で「まだ壁として存在するドア」
            lock_id = door.get("lock_id")
            text = (
                f"{display_name(lock_id)}が必要"
                if (lock_id and game_state.inventory.get(lock_id, 0) <= 0)
                else "E：開ける"
            )

            # ★ この“個別ドア”に対する「正面1マスがドアか？」の判定を計算
            #    （画面固定ピル表示は“正面1マスがドア”の時だけ 1.0s 出す設計）
            is_front = ((fx1, fy1) == (tx, ty))

            # A) まずは“ドアそのもの”に世界貼り（見えていれば最良）
            drew = emit_label_for_tile(tx, ty, text, zbuf, overlap_frac=0.22)
            if drew:
                drew_any = True
                continue

            # B) ドアが正面2マス目にあり、正面1マス目が床なら「床側に貼る」
            if (fx2, fy2) == (tx, ty):
                walk1 = False
                if 0 <= fy1 < len(layout) and 0 <= fx1 < len(layout[0]):
                    ch1 = layout[fy1][fx1]
                    walk1 = bool(TILE_TYPES.get(ch1, {"walkable": False}).get("walkable", False))
                if walk1:
                    drew2 = emit_label_for_tile(fx1, fy1, text, zbuf, overlap_frac=0.18)
                    if drew2:
                        drew_any = True
                        continue

            # C) それでも見えないなら、画面固定ピルで確実に提示
            blit_pill_label_midtop(screen, text, center_x=WIDTH // 2, top_y=HEIGHT - 86, size=16)
            drew_any = True

        # -----------------------------
        # 2) スイッチ（近ければ「E：押す」）
        #    ※ 正しい格納場所：cur_map["puzzle"]["switches"]
        #       形式は {"a":{"pos":(x,y)}, "b":{"pos":(x,y)}, ...}
        # -----------------------------
        puzzle = cur_map.get("puzzle") or {}
        switches = puzzle.get("switches") or {}
        # dict形式を想定。想定外なら空ループにして安全にスキップ。
        for info in (switches.values() if isinstance(switches, dict) else []):
            tx, ty = info["pos"]  # 例: (15, 7)
            wx, wy = _tile_center(tx, ty)
            # 前面版は R をゆるめている（R2=110^2）。ここでも同じ閾値を使用。
            if _dist2_px(px, py, wx, wy) > R2:
                continue
            key = (game_state.current_map_id, tx, ty, "E：押す")
            # 同一ヒントの出しっぱなしを抑制
            if not _hint_session_should_draw(key):
                continue
            emit_label_for_tile(tx, ty, "E：押す", zbuf, overlap_frac=0.18)
            drew_any = True

        # -----------------------------
        # 3) 候補が無ければセッション終了（次回再接近で再表示）
        # -----------------------------
        if not drew_any:
            _hint_session_left_proximity()

    _draw_interaction_hints_front(zbuf)

    # ---- 肖像画ヒント-----------------------------------
    def _draw_portrait_hint_front():
        cur_map = MAPS[game_state.current_map_id]
        hint_text = get_portrait_hint(cur_map)  # 既存のヘルパをそのまま利用
        if hint_text:
            draw_label(
                screen,
                hint_text,
                size=18,
                pos=(WIDTH//2, HEIGHT - 24),
                anchor="midbottom",
                bg_color=(0, 0, 0, 140),
            )
    _draw_portrait_hint_front()

    # 位置付きトースト（世界貼り → だめなら前面ピル）
    world_toast.draw(screen, zbuf)
    # トースト
    now_ms = pygame.time.get_ticks()
    toast.draw(screen, now_ms, WIDTH, HEIGHT)
    # メニュー最前面
    if menu_scene is not None:
        menu_scene.draw(screen, WIDTH, HEIGHT)

    pygame.display.flip()
