# core/cinematics.py

# -*- coding: utf-8 -*-
"""
カットシーン（動画）制御の集約モジュール
 - 近接トリガ（シンボル／座標）
 - once 再生（videos_played フラグ管理）
 - クールダウン（多重発火防止）
 - キュー処理（1本ずつ再生）
 - 便利関数：ブロッキング再生、ドクター演出シーケンス
"""
from __future__ import annotations
from pathlib import Path
from collections import deque
from typing import Callable, Iterable, Optional
import math
import pygame

import core.game_state as game_state
from core.config import TILE, WIDTH, HEIGHT
from core.maps import MAPS
from core.transitions import fade_in, fade_out
#
# すべての動画再生は video_player.play_video に統一する
# （音声の指定・SEキューなど video_player 側の機能を全面利用）
from core.video_player import play_video as _vp_play_video

# --- 内部ユーティリティ ---------------------------------------------------
def _vp_set() -> set[str]:
    """videos_played セットを取得（初期化含む）"""
    return game_state.FLAGS.setdefault("videos_played", set())

def has_played(map_id: str, video_id: str) -> bool:
    return f"{map_id}|{video_id}" in _vp_set()

def mark_played(map_id: str, video_id: str) -> None:
    _vp_set().add(f"{map_id}|{video_id}")

def _cooldown_ms() -> int:
    return int(getattr(game_state, "cinematic_cooldown_ms", 0))

def _now_ms() -> int:
    return int(pygame.time.get_ticks())

def can_fire() -> bool:
    """カットシーン発火可能か？（カットシーン中でなく、CD 経過済み）"""
    return (not getattr(game_state, "is_cutscene", False)) and (_now_ms() >= _cooldown_ms())

def arm_cooldown(ms: int) -> None:
    setattr(game_state, "cinematic_cooldown_ms", _now_ms() + int(ms))

# --- 再生本体 --------------------------------------------------------------
def play_video_blocking(
    screen: pygame.Surface,
    base_dir: Path,
    video_path: str,
    *,
    allow_skip: bool = True,
    fade: bool = False,
    audio_path: str | None = None,
    sound_manager=None,
    se_cues: list[tuple[float, str]] | None = None
) -> dict:
    """
    video_player.play_video を使ったブロッキング再生（結果 dict を返す）
    - ここで fade_in/out を制御（video_player 側の fade_ms と二重にならないよう注意）
    - True/False を {"played_to_end": bool} に変換して上位互換の戻り値に整形
    """
    was_cut = getattr(game_state, "is_cutscene", False)
    game_state.is_cutscene = True
    try:
        # ★カットシーン前に効果音を一括サイレント化（足音ループ含む）
        # 引数で渡らない場合でもグローバルから拾って確実に止める
        try:
            sm = sound_manager
            if sm is None:
                from core import sound_manager as _global_sm
                sm = getattr(_global_sm, "sound_manager", None) or _global_sm
            if sm:
                sm.hush_effects_for_cutscene(fade_ms=160)
        except Exception:
            pass
        
        if fade:
            try: fade_out(screen, ms=250)
            except Exception: pass
        # video_player 側にすべて委譲。ここではフェードだけ担当。
        # fade_ms はここでやるので 0 で呼ぶ（ダブルフェード防止）
        finished = _vp_play_video(
            screen=screen,
            base_dir=base_dir,
            video_rel_path=video_path,
            audio_rel_path=audio_path,      # ← ここで音声ファイルを直指定できる
            allow_skip=allow_skip,
            fade_ms=0,                      # フェードは本関数で wrap する
            sound_manager=sound_manager,    # （任意）BGM/SE 音量統一のため
            se_cues=se_cues,                # （任意）ムービーに同期してSEを鳴らす
        )
        # 互換の戻り値に整形
        res = {"played_to_end": bool(finished)}
        if fade:
            try: fade_in(screen, ms=250)
            except Exception: pass
        return res or {}
    finally:
        game_state.is_cutscene = was_cut

# --- キュー処理 ------------------------------------------------------------
def enqueue_video(video_id: str, video_path: str, *, toast_on_end: Optional[str] = None,
                  toast_on_skip: Optional[str] = None, audio_path: Optional[str] = None) -> None:
    q = game_state.state.setdefault("cinematic_queue", deque())
    q.append({
        "kind": "video",
        "id": video_id,
        "video_path": video_path,
        "toast_on_end": toast_on_end,
        "toast_on_skip": toast_on_skip or "……（スキップ）",
        "audio_path": audio_path,
    })

def process_queue(screen: pygame.Surface, base_dir: Path, *,
                  toast_cb: Optional[Callable[[str,int],None]] = None,
                  sound_manager=None) -> None:
    q: deque = game_state.state.setdefault("cinematic_queue", deque())
    if not q or not can_fire():
        return
    job = q.popleft()
    if job.get("kind") != "video":
        return
    cur_map = game_state.current_map_id
    vid_id = job.get("id") or job.get("video_path")
    if has_played(cur_map, vid_id):
        return
    res = play_video_blocking(
        screen, base_dir,
        job["video_path"],
        allow_skip=True,
        fade=False,
        audio_path=job.get("audio_path"),
        se_cues=job.get("se_cues"),
        sound_manager=sound_manager,
    )
    mark_played(cur_map, vid_id)
    msg = job.get("toast_on_end") if res.get("played_to_end") else job.get("toast_on_skip")
    if msg and toast_cb:
        toast_cb(msg, 1400)
    arm_cooldown(1000)

# --- 近接トリガ（once） ----------------------------------------------------
def _player_near_any_symbol(symbols: Iterable[str], radius_px: float) -> bool:
    layout = MAPS[game_state.current_map_id]["layout"]
    px, py = game_state.player_x, game_state.player_y
    r2 = radius_px * radius_px
    for y, row in enumerate(layout):
        for x, ch in enumerate(row):
            if ch in symbols:
                cx, cy = x*TILE + TILE*0.5, y*TILE + TILE*0.5
                dx, dy = px - cx, py - cy
                if dx*dx + dy*dy <= r2:
                    return True
    return False

def trigger_proximity_movie_once(
    screen: pygame.Surface,
    base_dir: Path,
    *,
    video_id: str,
    symbols: Optional[Iterable[str]] = None,
    pos: Optional[tuple[int,int]] = None,  # tile 座標
    radius_px: float = 96.0,
    enable_if: Optional[Callable[[], bool]] = None,
    toast_on_end: Optional[str] = None,
    toast_on_skip: Optional[str] = "……（スキップ）",
    # トーストを実際に出すためのコールバック（例：lambda msg,ms: toast.show(msg, ms)）
    toast_cb: Optional[Callable[[str, int], None]] = None,
    toast_duration_ms: int = 1400,  # デフォルトの表示時間
    audio_path: str | None = None, # ▼ 背景環境音（動画の背後で流す）。指定がなければ無音。
    sound_manager=None, # 音量連動のための SoundManager（voice チャンネル・voice_volume）
) -> bool:
    """
    条件を満たしたら動画を即時再生（once）する。再生したら True を返す。
    ※ すぐ再生する版（キューに積まずにブロッキング）。用途により enqueue 版に替えてもOK。
    """
    # --- 条件＆クールダウンなどの既存ガード ---
    if enable_if and not enable_if():
        return False
    if not can_fire():
        return False
    cur_map = game_state.current_map_id
    if has_played(cur_map, video_id):
        return False

    # --- 近接判定（記号 or 座標 or 無条件） ---
    near = False
    if symbols:
        near = _player_near_any_symbol(tuple(symbols), radius_px)
    elif pos and len(pos) == 2:
        cx, cy = pos[0]*TILE + TILE*0.5, pos[1]*TILE + TILE*0.5
        dx = game_state.player_x - cx
        dy = game_state.player_y - cy
        near = (dx*dx + dy*dy) <= (radius_px*radius_px)
    else:
        near = True

    if not near:
        return False

    # --- 実再生（ブロッキング） ---
    res = play_video_blocking(
        screen, base_dir,
        video_path=video_id if video_id.endswith(".mp4") else f"assets/movies/{video_id}.mp4",
        allow_skip=True,
        fade=True,
        audio_path=audio_path, # ← ここで個別の音を受け渡し可
        sound_manager=sound_manager,
    )

    # 再生済みフラグ＆クールダウン
    mark_played(cur_map, video_id)
    arm_cooldown(1000)

    # --- 結果に応じてトーストを出す(トーストは呼び出し元で表示) ---
    try:
        played_to_end = bool(res.get("played_to_end"))
        msg = (toast_on_end if played_to_end else toast_on_skip)
        if msg and toast_cb:
            toast_cb(msg, toast_duration_ms)
    except Exception:
        # トースト周りで例外が出てもゲームは止めない
        pass
    return True

# --- ドクター演出（屋敷前）ユーティリティ -------------------------------
def run_doctor_gate_sequence(
        screen: pygame.Surface,
        base_dir: Path,
        *,
        video_path: str = "assets/movies/doctor_burst_out.mp4",
        dest_id: str = "lab_entrance",
        fallback_spawn: tuple[int,int] = (2, 8),
        grant_key: bool = False,  # ← 鍵を付与する設計に戻したい時だけ True
        video_audio: str | None = None,  # このイベントのムービー音を直接指定したい場合
        target_face: str | None = None,  # 'N','E','S','W' で向きを指定
        target_angle: float | None = None,  # 角度（ラジアン or 度）で指定
        toast_cb: Optional[Callable[[str,int],None]] = None,
        sound_manager=None,
    ) -> None:
    """
    1) ムービー再生
    2) doctor イベント（失敗は握りつぶし）
    3) フェード→ワープ→フェード
    4) トースト
    """
    # 1) ムービー（ここでも video_player を使う）
    try:
        play_video_blocking(
            screen, base_dir,
            video_path=video_path,
            allow_skip=True,
            fade=False,
            audio_path=video_audio,
            sound_manager=sound_manager, 
        )
    except Exception:
        pass
    # 2) doctor イベント
    try:
        from scenes.doctor_event import run_doctor_event
        _ = run_doctor_event(screen, base_dir, sound_manager=sound_manager)
    except Exception:
        pass

    # 必要なら鍵を付与（デフォルトは False） ※使わなかった。
    if grant_key:
        inv = game_state.inventory
        inv["key_mansion"] = inv.get("key_mansion", 0) + 1
        if toast_cb:
            toast_cb("『屋敷の鍵』を手に入れた", 1500)

    # 3) 移動
    try: fade_out(screen, ms=400)
    except Exception: pass
    dest_map = MAPS.get(dest_id, {})
    spawn_xy = tuple(dest_map.get("spawn", fallback_spawn))
    game_state.current_map_id = dest_id
    tx, ty = spawn_xy
    game_state.player_x = tx*TILE + TILE*0.5
    game_state.player_y = ty*TILE + TILE*0.5
    # --- ワープ後の向きを target_angle / target_face から反映 -------------------
    ang = target_angle
    face = (target_face or "").strip().upper()[:1] if ang is None and isinstance(target_face, str) else None
    if ang is None and face:
        # 右向き=東=0 を基準に、画面座標系に合わせて割り当て
        # E:0, S:π/2, W:π, N:3π/2
        face_table = {"E": 0.0, "S": math.pi * 0.5, "W": math.pi, "N": math.pi * 1.5}
        ang = face_table.get(face, None)
    if isinstance(ang, (int, float)):
        # もし誤って度で渡されたら（>2πを想定）自動で度→ラジアンに補正
        if abs(ang) > (2.0 * math.pi + 1e-3):
            ang = math.radians(ang)
        game_state.player_angle = ang % (2.0 * math.pi)
    # ----------------------------------------------------------------------    
    try: fade_in(screen, ms=350)
    except Exception: pass
    # 4) トースト
    if toast_cb:
        toast_cb("屋敷の中へ入った……", 1400)
    arm_cooldown(1200)
