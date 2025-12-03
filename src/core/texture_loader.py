# core/texture_loader.py
# -*- coding: utf-8 -*-
from pathlib import Path
import pygame
import numpy as np

from .config import TILE

# 既存のユーティリティがあれば使う（無ければフォールバック）
try:
    from .asset_utils import make_wall_placeholder_surface, make_floor_placeholder_array, make_ceiling_placeholder_array
except Exception:
    make_wall_placeholder_surface = lambda tile: pygame.Surface((max(1,tile//2), max(1,tile*2)))
    def make_floor_placeholder_array(tile):
        arr = np.zeros((tile, tile, 3), dtype=np.uint8)
        arr[:, :] = (60, 90, 60)
        return arr
    def make_ceiling_placeholder_array(tile):
        arr = np.zeros((tile, tile, 3), dtype=np.uint8)
        arr[:, :] = (70, 70, 70)
        return arr

def _surf_to_tile_arrays_rgba(surf: pygame.Surface | None) -> tuple[np.ndarray | None, np.ndarray | None]:
    """
    (TILE, TILE, 3) のRGB配列と (TILE, TILE) のAlpha配列を返す。
    どちらか生成できなければ None を返す。
    """
    if surf is None:
        return None, None
    if surf.get_width() != TILE or surf.get_height() != TILE:
        surf = pygame.transform.smoothscale(surf, (TILE, TILE))
    # array3d: (W,H,3) → (H,W,3)
    rgb = pygame.surfarray.array3d(surf).swapaxes(0, 1).astype(np.uint8)
    # 透過が無いSurfaceでも array_alpha は生成できる（全面255になる）
    try:
        a = pygame.surfarray.array_alpha(surf).swapaxes(0, 1).astype(np.uint8)
    except Exception:
        # alphaが取れない場合は全面255扱い
        a = np.full((TILE, TILE), 255, dtype=np.uint8)
    return rgb, a

def _resolve_path(base_dir: Path, val: str | None) -> Path | None:
    if not val:
        return None
    p = Path(val)
    if p.is_absolute():
        return p
    # "assets/..." はそのまま、ファイル名だけなら assets/textures を補う
    if str(p).startswith("assets/"):
        return (base_dir / p).resolve()
    return (base_dir / "assets" / "textures" / p).resolve()


def _load_surface(base_dir: Path, rel: str | None) -> pygame.Surface | None:
    p = _resolve_path(base_dir, rel)
    if not p:
        return None
    try:
        # 透過があるかもしれないので convert_alpha
        return pygame.image.load(str(p)).convert_alpha()
    except Exception as e:
        print(f"[WARN] texture load failed: {rel} ({e})")
        return None


def _surf_to_tile_array3(surf: pygame.Surface | None) -> np.ndarray | None:
    """(TILE, TILE, 3) の ndarray へ。alphaは捨ててRGBにする。"""
    if surf is None:
        return None
    if surf.get_width() != TILE or surf.get_height() != TILE:
        surf = pygame.transform.smoothscale(surf, (TILE, TILE))
    # pygame.surfarray.array3d は (W,H,3) なので (H,W,3) に並べ替え
    arr = pygame.surfarray.array3d(surf).swapaxes(0, 1).astype(np.uint8)
    return arr


def _build_wall_special(base_dir: Path, mapping: dict) -> dict:
    """
    'wall_special': { 'D': 'door.png', ... } を
    { 'D': pygame.Surface, ... } へ正規化。
    （古い {"surf": Surface} 形式も受ける）
    """
    out = {}
    for sym, val in (mapping or {}).items():
        if isinstance(val, pygame.Surface):
            out[sym] = val
        elif isinstance(val, dict) and isinstance(val.get("surf"), pygame.Surface):
            out[sym] = val["surf"]
        elif isinstance(val, str):
            s = _load_surface(base_dir, val)
            if s is not None:
                out[sym] = s
    return out


def _build_special_floor(base_dir: Path, mapping: dict) -> dict:
    """
    'special': { 'w': 'forest_water.png', 'B': 'bridge.png', 'a_lit': '...' }
      → { 'w': {'arr': ndarray, 'alpha': ndarray}, ... } に正規化。
    互換: value が pygame.Surface / {'surf': Surface} / {'arr': ndarray} でもOK。
    """
    out = {}
    for sym, val in (mapping or {}).items():
        # 既に配列が入っている場合（上書き禁止／そのまま使う）
        if isinstance(val, dict) and isinstance(val.get("arr"), np.ndarray):
            # αが無いなら全面255を入れておく
            if "alpha" not in val or not isinstance(val["alpha"], np.ndarray):
                h, w = val["arr"].shape[:2]
                val["alpha"] = np.full((h, w), 255, dtype=np.uint8)
            out[sym] = val
            continue

        surf = None
        # 直接 Surface
        if isinstance(val, pygame.Surface):
            surf = val
        # {"surf": Surface}
        elif isinstance(val, dict) and isinstance(val.get("surf"), pygame.Surface):
            surf = val["surf"]

        # 文字列パス（※ '.' や単文字など“ファイルでない”ものは採用しない）
        elif isinstance(val, str):
            # 簡易判定：拡張子を含まない／パスとして解決できないものは無視
            if "." in val or "/" in val or "\\" in val:
                surf = _load_surface(base_dir, val)
            else:
                surf = None

        if surf is None:
            # ★ 要件：current_textures["special"] に文字列は絶対に入れない
            continue

        rgb, alpha = _surf_to_tile_arrays_rgba(surf)
        if rgb is not None:
            out[sym] = {"arr": rgb, "alpha": alpha}

    return out


def load_textures(base_dir: Path, map_def: dict) -> dict:
    """
    マップ定義から描画用テクスチャ群をロードして返す。
    返却:
      {
        "wall": pygame.Surface,
        "wall_special": {symbol: pygame.Surface, ...},
        "floor_arr": (TILE,TILE,3) ndarray or None,
        "ceiling_arr": (TILE,TILE,3) ndarray or None,
        "special": {symbol: {"arr": ndarray}, ...},
        "sprites": {},   # 後段で埋められる前提
      }
    """
    base_dir = Path(base_dir).resolve()
    tex_cfg = (map_def.get("textures") or {})

    # 壁（必須）
    wall_surf = _load_surface(base_dir, tex_cfg.get("wall"))
    if wall_surf is None:
        wall_surf = make_wall_placeholder_surface(TILE)

    # 床
    floor_arr = None
    if tex_cfg.get("floor") is None:
        floor_arr = None
    else:
        f_surf = _load_surface(base_dir, tex_cfg.get("floor"))
        floor_arr = _surf_to_tile_array3(f_surf) if f_surf is not None else make_floor_placeholder_array(TILE)

    # 天井
    ceil_arr = None
    if tex_cfg.get("ceiling") is None:
        ceil_arr = None
    else:
        c_surf = _load_surface(base_dir, tex_cfg.get("ceiling"))
        ceil_arr = _surf_to_tile_array3(c_surf) if c_surf is not None else make_ceiling_placeholder_array(TILE)

    # 壁の差し替え（ドア/封鎖/肖像など）
    wall_special = _build_wall_special(base_dir, tex_cfg.get("wall_special") or {})

    # 床の特殊タイル（川/橋/床スイッチなど）
    special = _build_special_floor(base_dir, tex_cfg.get("special") or {})

    return {
        "wall": wall_surf,
        "wall_special": wall_special,
        "floor_arr": floor_arr,
        "ceiling_arr": ceil_arr,
        "special": special,
        "sprites": {},  # 後で prepare_item_sprites が埋める
    }
