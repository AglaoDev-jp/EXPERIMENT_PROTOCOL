# core/interactions.py
"""
インタラクション系の共通関数群（拾得・ドア・スイッチ）
"""

from __future__ import annotations
from typing import Optional, Tuple, Dict, Any, List, Set, Deque, Iterable, Iterator
from collections import deque

import pygame
from core.config import TILE
from core.maps import MAPS
from core.tile_types import TILE_TYPES
import core.game_state as game_state
from core.items import display_name
from core import toast_bridge

# 拾得半径（プレイヤー中心からのピクセル距離）
PICKUP_RADIUS_PX = 72   # # 距離ベースの拾得半径（px）。draw_items() のハイライト(≈72px)調整可能。

# __all__ は “from core.interactions import *” の公開対象
__all__ = [
    "try_pickup_item",
    "try_open_door",
    "try_press_switch",
    "try_chop_tree",
    "try_offer_guardian",
    "try_use_exit",
]

# ---------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------
def _player_tile_xy() -> Tuple[int, int]:
    """プレイヤーの現在タイル座標を返す。"""
    px = int(game_state.player_x // TILE)
    py = int(game_state.player_y // TILE)
    return px, py


def _is_adjacent_or_same(ax: int, ay: int, bx: int, by: int) -> bool:
    """
    タイル座標ベースで、同一または隣接（上下左右いずれか）を許す近接判定。
    - ドアやアイテムに“密着”していればOKにしたいときに便利。
    """
    return abs(ax - bx) + abs(ay - by) <= 1

def _is_inline_two_step(ax: int, ay: int, bx: int, by: int) -> bool:
    """
    ax,ay（プレイヤー）から bx,by（ドア）までが一直線で“ちょうど2タイル離れ”
    の場合に True。間の1タイルが walkable（床）であることが条件。
    例）P .. D の並びで、P の位置から E が届くイメージ。
    """
    dx = bx - ax
    dy = by - ay
    if (abs(dx) == 2 and dy == 0) or (abs(dy) == 2 and dx == 0):
        mx = ax + (dx // 2)
        my = ay + (dy // 2)
        try:
            row = MAPS[game_state.current_map_id]["layout"][my]
            ch  = row[mx] if isinstance(row, str) else str(row[mx])[0]
        except Exception:
            return False
        walkable_mid = bool((TILE_TYPES.get(ch, {"walkable": False})).get("walkable", False))
        return walkable_mid
    return False

# MAP上の“個体”を一意に識別するキー（差分管理の要）
def make_entity_key(map_id: str, kind: str, item_or_chest_id: str, tx: int, ty: int) -> str:
    # 例: "forest_1:item:map_chart@3,3" / "forest_2:chest:chest_01@10,7"
    return f"{map_id}:{kind}:{item_or_chest_id}@{tx},{ty}"

# ---- kind→画像パスのマッピング（仕様に合わせた最低限の対応） ----
SPRITE_FILE_BY_KIND = {
    "key":      "assets/sprites/key_gold_64.png",
    "tool":     "assets/sprites/axe_64.png",
    "offering": "assets/sprites/orb_64.png",
}

# ====== 森ギミック用の定数（マジックナンバーの早期固定） ======
TREE_HITS_REQUIRED = 3     # 倒木に必要なヒット数
FOG_CLEAR_RADIUS   = 8     # 霧を晴らす探索半径（タイル）
HIT_COOLDOWN_MS    = 250   # Eキーの連打抑制（main側と合わせてOK）

# state辞書の初期化（安全策）
st = game_state.state
st.setdefault("chop_hits", {})   # {(map_id, x, y): 現在ヒット数}
st.setdefault("cinematic_queue", deque())  # ← ムービー等の演出キュー

# ------------------------------------------------------------
# ヘルパ：プレイヤー“正面1マス”のタイル座標を得る
# ------------------------------------------------------------
def _front_tile(px: float, py: float, angle: float) -> Tuple[int, int]:
    fx = px + TILE * 0.6 * pygame.math.Vector2(1, 0).rotate_rad(angle).x
    fy = py + TILE * 0.6 * pygame.math.Vector2(1, 0).rotate_rad(angle).y
    return int(fx // TILE), int(fy // TILE)

# ---------------------------------------------------------------------
#  アイテム拾得
# ---------------------------------------------------------------------
def _normalize_item_entry(it: dict) -> dict:
    """旧式/新式のアイテム定義を統一形式へ正規化して返す。"""
    # 旧式: {"id","type","tile":(x,y),"picked":bool}
    if "tile" in it and "type" in it:
        return {
            "id": it.get("id", ""),
            "type": it["type"],
            "tile": tuple(it["tile"]),
            "picked": bool(it.get("picked", False)),
        }

    # 新式: {"id","kind","name","pos"} 想定 → 内部type名へ変換
    kind = it.get("kind")
    iid  = it.get("id", "misc")
    if kind == "tool" and iid.startswith("axe"):
        type_name = "axe"
    elif kind == "offering":
        type_name = "spirit_orb"
    elif kind == "key":
        # ★ 鍵の種類を id の接頭辞で判定
        if str(iid).startswith("key_lab"):
            type_name = "key_lab"
        elif str(iid).startswith("key_forest"):
            type_name = "key_forest"
        else:
            type_name = "key_forest"  # フォールバック

    else:
        type_name = iid

    return {
        "id": iid,
        "type": type_name,
        "tile": tuple(it.get("pos", (0, 0))),
        "picked": bool(it.get("picked", False)),
    }

def try_pickup_item(cur_map: Dict[str, Any]) -> Optional[str]:
    """
    「候補探索」も「取得」も FLAGS["picked_items"] を見る
    """
    items: List[Dict[str, Any]] = cur_map.get("items", [])
    if not items:
        return None

    px, py = game_state.player_x, game_state.player_y

    cur_map_id = getattr(game_state, "current_map_id", "")
    picked_set = game_state.FLAGS.get("picked_items", set())

    best_idx = -1
    best_d2 = 1e18

    # ▼未取得だけを探索（picked_set を参照）
    for idx, raw in enumerate(items):
        it = _normalize_item_entry(raw)
        tx, ty = it["tile"]
        # 個体キーは id があれば id、無ければ type を使う
        uniq = it.get("id") or it["type"]
        key = make_entity_key(cur_map_id, "item", uniq, tx, ty)
        if key in picked_set:
            continue  # 取得済みは候補から除外

        wx = tx * TILE + TILE * 0.5
        wy = ty * TILE + TILE * 0.5
        d2 = (px - wx) ** 2 + (py - wy) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_idx = idx

    if best_idx < 0:
        return None
    if best_d2 > (PICKUP_RADIUS_PX ** 2):
        return None

    # ▼実取得：インベントリ更新＋“差分セット”に登録（MAPSは書き換えない）
    it_norm = _normalize_item_entry(items[best_idx])
    inv_key = it_norm["type"]
    game_state.inventory[inv_key] = game_state.inventory.get(inv_key, 0) + 1

    tx, ty = it_norm["tile"]
    uniq = it_norm.get("id") or inv_key
    key = make_entity_key(cur_map_id, "item", uniq, tx, ty)
    game_state.FLAGS.setdefault("picked_items", set()).add(key)

    name_ja = display_name(inv_key)
    msg = f"{name_ja} を拾った。"
    game_state.message = msg     # ← 追加（常に state にも残す）
    return msg

# ---------------------------------------------------------------------
#  ドアの開錠
# ---------------------------------------------------------------------
def try_open_door(cur_map_id: str, cur_map: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    近接しているドア定義（cur_map['doors']）を探索し、必要なら鍵を消費して開錠する。
    - マップの実体更新（例: '#' → '.'）は main 側で行うため、本関数は
      “開けるべきドア情報（id と タイル座標）” を返すだけに留める。
    - 戻り値: (メッセージ文字列 or None, 開けたドアの dict or None)
        * dict は少なくとも {"id": ..., "tile": (x, y)} を含む。

    設計方針：
    - 表示は本関数内でトーストせず、呼び出し側に委ねる（toast_bridge で一元管理のため）。
      ただし、呼び出し側の都合に合わせられるよう、game_state.message には必ず同文言を格納する。
    """

    # --- 小ヘルパ：戻り値と game_state.message を常に同期させる -----------------
    def _ret(msg: Optional[str], door: Optional[Dict[str, Any]] = None) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        if msg is not None:
            game_state.message = msg  # 呼び出し側が state 経由でもメッセージを取れるように
        return msg, door

    # --- 事前取得（ロバストにレイアウトとドア配列を参照） -----------------------
    layout = cur_map.get("layout")
    if layout is None:
        # 念のため MAPS 経由でも拾えるようにしておく
        layout = MAPS.get(cur_map_id, {}).get("layout", [])

    doors = cur_map.get("doors", []) or []
    if not isinstance(doors, list) or not layout:
        return None, None  # ドア定義が無い／レイアウトが無いなら何もしない

    # プレイヤーの現在タイル座標（整数タイル座標）を取得
    px, py = _player_tile_xy()

    # --- ドアを走査 ----------------------------------------------------------
    # 「近接範囲に“開いているドアのみ”がある場合だけ」メッセージを出すためのフラグ
    saw_open_only = False

    for d in doors:
        # ドアのタイル座標（必須）
        tx, ty = d.get("tile", (-1, -1))
        if not (isinstance(tx, int) and isinstance(ty, int)) or tx < 0 or ty < 0:
            continue  # 無効定義はスキップ

        door_id = d.get("id", "")

        # まず「プレイヤーから操作可能な範囲」にあるかどうかを判定
        #   - 同じタイル / 上下左右に隣接
        #   - 直線方向に2タイル離れ（間が床）の P .. D
        if not (_is_adjacent_or_same(px, py, tx, ty) or _is_inline_two_step(px, py, tx, ty)):
            # 近接していないドアは今回の E 押下とは無関係なのでスキップ
            continue

        # レイアウト境界チェック＆そのタイル文字を取得
        try:
            row = layout[ty]
            ch = row[tx] if isinstance(row, str) else str(row[tx])[0]
        except Exception:
            continue  # 範囲外等はスキップ

        # 現在のタイルが walkable かどうか（ '.' など床になっていれば True）
        walkable = bool((TILE_TYPES.get(ch, {"walkable": False})).get("walkable", False))

        # 「既に開いているドア」判定
        already_open = False
        # 1) 永続フラグ上で「開いたドア」として記録されている
        if door_id and game_state.is_door_opened(cur_map_id, door_id):
            already_open = True
        # 2) レイアウト上、すでに床など walkable になっている
        elif walkable:
            already_open = True

        if already_open:
            # 「プレイヤー近接 + そのドアは開いている」場合だけフラグを立てる
            saw_open_only = True
            # そのドアに対してはこれ以上何もしない（再び開けたりはしない）
            continue

        # --- ここまで来たら「近接していて、まだ閉じているドア」 -----------------

        # --- 鍵チェック ------------------------------------------------------
        # lock_id（必要鍵 ID）。鍵が不要なら None 想定。
        # もし定義側で 'key' を使っているケースがあればフォールバックで拾う。
        need = d.get("lock_id", d.get("key"))
        consume = bool(d.get("consume", False))  # True なら使用後に鍵を消費
        have = (need is None) or (game_state.inventory.get(need, 0) > 0)

        if not have:
            # 鍵が必要なのに所持していない
            return _ret(f"鍵({need})が必要だ。", None)

        # --- 開錠処理（必要なら鍵を消費） -----------------------------------
        if consume and need:
            game_state.inventory[need] = max(0, game_state.inventory.get(need, 0) - 1)

        # このドアを game_state 上で「開いたドア」として記録
        if door_id:
            game_state.mark_door_opened(cur_map_id, door_id)

        # ここでは “どのドアを開けるか” の情報を返すだけ（実体更新は main 側）
        opened_info = {
            "id": d.get("id", ""),
            "tile": (tx, ty),
        }
        return _ret("鍵が回った…開いた！", opened_info)

    # ここまで来た＝「近接範囲に“閉じたドア”は無かった」
    # ただし、「近接範囲に“開いているドア（= 床化）”はあった」場合はメッセージを返す
    if saw_open_only:
        return _ret("ここは既に開いている。", None)

    return None, None


# ------------------------------------------------------------
# 倒木の on_unlock：対象タイルを'.'に、東隣の水('w')を橋('B')へ
# ------------------------------------------------------------
def _on_unlock_tree(map_id: str, tx: int, ty: int) -> None:
    layout = MAPS[map_id]["layout"]
    row = layout[ty]
    # 自身を '.' に
    layout[ty] = row[:tx] + '.' + row[tx+1:]
    # 東隣が 'w' なら 'B' に置換
    if tx + 1 < len(row) and layout[ty][tx+1] == 'w':
        r = layout[ty]
        layout[ty] = r[:tx+1] + 'B' + r[tx+2:]

def _enqueue_cinematic_video(*, unique_id: str, video_path: str,
                            toast_on_end: str | None = None,
                            toast_on_skip: str | None = "……（スキップ）",
                            audio_path: str | None = None,
                            se_cues: list[tuple[float, str]] | None = None) -> None:
    """
    ムービー再生ジョブを演出キューへ追加（main.py 側で消費・再生）。
    unique_id: 同一イベントの二重再生防止用（例: f"tree_fall@{map}:{x},{y}"）
    """
    q = game_state.state.setdefault("cinematic_queue", deque())
    q.append({
        "kind": "video",
        "id": unique_id,
        "video_path": video_path,
        "toast_on_end": toast_on_end,
        "toast_on_skip": toast_on_skip,
        "audio_path": audio_path,
        "se_cues": se_cues,
    })

# ------------------------------------------------------------
# 霧晴れの on_unlock：中心から半径FOG_CLEAR_RADIUS内の 'F' を'.'へ
# （壁や水はそのまま／“繋がり”で制限したい場合はBFSに差し替え可）
# ------------------------------------------------------------
def _on_clear_fog(map_id: str, cx: int, cy: int, radius: int = FOG_CLEAR_RADIUS) -> None:
    layout = MAPS[map_id]["layout"]
    h = len(layout); w = len(layout[0]) if h else 0
    r2 = radius * radius
    new_rows = list(layout)  # 文字列のリスト（書き換え用コピー）

    for y in range(max(0, cy - radius), min(h, cy + radius + 1)):
        row = new_rows[y]
        row_list = list(row)
        for x in range(max(0, cx - radius), min(w, cx + radius + 1)):
            if (x - cx) * (x - cx) + (y - cy) * (y - cy) > r2:
                continue
            if row_list[x] == 'F':
                row_list[x] = '.'
        new_rows[y] = "".join(row_list)

    MAPS[map_id]["layout"] = new_rows

# ------------------------------------------------------------
# 斧で倒木：足元 or 正面1マスの 'O' が対象
# ・進捗は (map_id,x,y) キーで管理
# ------------------------------------------------------------
def try_chop_tree(cur_map_id: str, cur_map: dict, sm) -> Optional[str]:
    # 斧所持チェック
    if game_state.inventory.get("axe", 0) <= 0:
        return None  # “ヒントUI側”で「斧が必要」を表示する

    # 対象：足元 or 正面1マスの 'O'
    px = int(game_state.player_x // TILE)
    py = int(game_state.player_y // TILE)
    tx, ty = px, py
    ch = cur_map["layout"][ty][tx]
    if ch != 'O':
        fx, fy = _front_tile(game_state.player_x, game_state.player_y, game_state.player_angle)
        if 0 <= fy < len(cur_map["layout"]) and 0 <= fx < len(cur_map["layout"][0]):
            ch = cur_map["layout"][fy][fx]
            if ch == 'O':
                tx, ty = fx, fy
            else:
                return None
        else:
            return None

    # --- ランタイム state の安全な初期化（2周目・ロード直後でもOKにする） ---
    st = game_state.state
    chop_hits = st.get("chop_hits")
    # ・初回プレイ前 / 2周目開始直後などで "chop_hits" が存在しない
    # ・あるいは旧バージョンセーブから list など別型で復元された
    #   といったケースにも耐えられるように、必ず dict に正規化する
    if not isinstance(chop_hits, dict):
        chop_hits = {}
        st["chop_hits"] = chop_hits

    key = (cur_map_id, tx, ty)
    hits = int(chop_hits.get(key, 0)) + 1
    chop_hits[key] = hits

    # 🔊 1回切るごとに木を切る音を再生
    sm.play_se("tree_chop")

    if hits >= TREE_HITS_REQUIRED:
        # ① その場の見た目を即座に更新
        _on_unlock_tree(cur_map_id, tx, ty)
        # ② 永続フラグ
        game_state.FLAGS.setdefault("trees_chopped", set()).add((cur_map_id, tx, ty))
        # ③ 進捗カウンタ後始末
        chop_hits.pop(key, None)

        # ★ ④ このタイミングで「倒木ムービー」をキューへ
        uid = f"tree_fall@{cur_map_id}:{tx},{ty}"  # 木ごとに一意
        _enqueue_cinematic_video(
            unique_id=uid,
            video_path="assets/movies/tree_fall.mp4",
            audio_path="assets/sounds/se/河原.mp3.enc",
            se_cues=[(0.0, "tree_crash")],
            toast_on_end="大木が倒れ、川に橋がかかった！",
            toast_on_skip="……（スキップ）",
        )
        # ★ ⑤ この一回に限って “即時トースト” を抑止（ムービー後に出したい）
        game_state.state["suppress_instant_toast"] = True

        # 返り値はあってもOK（表示は抑止される）
        game_state.message = "大木が倒れ、川に橋がかかった！"
        return game_state.message

    else:
        # 進捗メッセージは従来通り即時トースト
        game_state.message = f"大木を切り倒している… ({hits}/{TREE_HITS_REQUIRED})"
        return game_state.message

# ------------------------------------------------------------
# 守人解除：足元 or 正面1マスの 'M' が対象
# ・供物（spirit_orb）を1つ消費
# ・周囲の 'F' をまとめて晴らす
# ------------------------------------------------------------
def try_offer_guardian(cur_map_id: str, cur_map: dict) -> Optional[str]:
    # --- まず守人が“目の前 or 足元”にいるかだけ判定（元コードをそのまま活かす）---
    px = int(game_state.player_x // TILE)
    py = int(game_state.player_y // TILE)
    tx, ty = px, py
    try:
        ch = cur_map["layout"][ty][tx]
    except Exception:
        return None

    if ch != 'M':
        fx, fy = _front_tile(game_state.player_x, game_state.player_y, game_state.player_angle)
        if 0 <= fy < len(cur_map["layout"]) and 0 <= fx < len(cur_map["layout"][0]):
            ch = cur_map["layout"][fy][fx]
            if ch == 'M':
                tx, ty = fx, fy
            else:
                return None
        else:
            return None

    # 供物（幽き珠）の所持チェックと安全な減算
    # - 未所持（キーなし/0個）の場合はその旨メッセージを state に残して終了
    # - 所持している場合のみ 1 個消費し、0 になったらキーごと削除
    count = int(game_state.inventory.get("spirit_orb", 0))
    if count <= 0:
        # ※ UI 側（ヒントやトースト）で利用できるように state にも入れておく
        game_state.message = "供物（幽き珠）が必要だ。"
        return None
    # ここに来たら所持あり：安全に 1 個消費
    new_count = count - 1
    if new_count > 0:
        game_state.inventory["spirit_orb"] = new_count
    else:
        # 0 個になったらキーを消す（get/<=0 の分岐で次回以降も安全）
        game_state.inventory.pop("spirit_orb", None)

    # 守人を消す（'.'）＋ 霧を晴らす
    row = cur_map["layout"][ty]
    cur_map["layout"][ty] = row[:tx] + '.' + row[tx+1:]
    _on_clear_fog(cur_map_id, tx, ty, radius=FOG_CLEAR_RADIUS)

    game_state.message = "供物を捧げた。守人は消え、霧が晴れて視界が開けた。"
    return game_state.message

# ------------------------------------------------------------
# 出口：足元が '>' のとき、MAP内の suggested_exit に従って遷移確認
# ------------------------------------------------------------
def try_use_exit(cur_map_id: str, cur_map: dict) -> Optional[str]:
    px = int(game_state.player_x // TILE)
    py = int(game_state.player_y // TILE)
    if cur_map["layout"][py][px] != '>':
        return None

    ex = cur_map.get("suggested_exit")
    if not ex:
        return None

    # pos が書かれていない場合は「>に乗っていればOK」
    ex_pos = tuple(ex.get("pos", (px, py)))
    if (px, py) != ex_pos:
        return None

    to_map = ex["to_map"]
    # spawn は (1.5,1.5) のような“中心”指定もあるのでタイル整数に丸める
    spawn = MAPS.get(to_map, {}).get("suggested_player_start")
    if spawn is not None:
        tx, ty = int(spawn[0]), int(spawn[1])
    else:
        tx, ty = 1, 1

    game_state.state["mode"] = "map_confirm"
    game_state.state["pending_trigger"] = {
        "event": "exit",
        "pos": (px, py),
        "target_map": to_map,
        "target_pos": (tx, ty),   # ★整数タイル座標で統一
        "prompt": ex.get("prompt", "先へ進みますか？"),
    }
    msg = ex.get("prompt", "先へ進みますか？") + "（Y/N）"
    game_state.message = msg
    return msg

# ---------------------------------------------------------------------
# 押した後だけ点滅するスイッチ（順番ミスでリセット付き）
# ---------------------------------------------------------------------


# -----------------------------------------------------------------------------
# ヘルパ：座標をどの形式からでも (sx, sy) に正規化する
#  - 許容例:
#     (x, y) / [x, y]
#     {"x": x, "y": y}
#     {"pos": (x, y)} / {"pos": [x, y]} / {"xy": (x, y)}
#     [(x, y)] のように 1 要素の入れ子（誤ってネストした）も許容
#     "x,y" 形式の文字列も最後の保険として対応
# -----------------------------------------------------------------------------
def _coerce_xy_pair(val: Any) -> Optional[Tuple[int, int]]:
    # tuple/list 直 → (x,y)
    if isinstance(val, (list, tuple)):
        if len(val) >= 2 and all(isinstance(v, (int, float)) for v in val[:2]):
            return int(val[0]), int(val[1])
        if len(val) == 1 and isinstance(val[0], (list, tuple)) and len(val[0]) >= 2:
            a = val[0]
            if all(isinstance(v, (int, float)) for v in a[:2]):
                return int(a[0]), int(a[1])
        return None
    # dict → "x,y" / "pos" / "xy"
    if isinstance(val, dict):
        if "x" in val and "y" in val:
            try:
                return int(val["x"]), int(val["y"])
            except Exception:
                return None
        for k in ("pos", "xy"):
            if k in val:
                return _coerce_xy_pair(val[k])
        return None
    # "x,y" 文字列
    if isinstance(val, str) and ("," in val):
        try:
            xs, ys = val.split(",", 1)
            return int(float(xs.strip())), int(float(ys.strip()))
        except Exception:
            return None
    return None

# -----------------------------------------------------------------------------
# ヘルパ：puzzle["switches"] をどの形でも (sym, sx, sy) の列として走査できるようにする
#  - 許容例:
#     {"a": (x,y), "b": {"x":..,"y":..}, "c": {"pos": (x,y)}}
#     [("a",(x,y)), {"sym":"b","x":..,"y":..}, {"symbol":"c","pos":[x,y]}]
# -----------------------------------------------------------------------------
def _iter_switch_entries(switches: Any) -> Iterator[Tuple[str, int, int]]:
    # dict 型: {sym: <any shape>}
    if isinstance(switches, dict):
        for sym, v in switches.items():
            xy = _coerce_xy_pair(v)
            if xy:
                yield str(sym), xy[0], xy[1]
        return
    # list/tuple 型: [ (sym, coord), {...}, ... ]
    if isinstance(switches, (list, tuple)):
        for ent in switches:
            # 形式 A: (sym, (x,y))
            if isinstance(ent, (list, tuple)) and len(ent) >= 2:
                sym = ent[0]
                xy = _coerce_xy_pair(ent[1])
                if xy:
                    yield str(sym), xy[0], xy[1]
                continue
            # 形式 B: {"sym": "a", "x":.., "y":..} / {"symbol":"a","pos":(x,y)}
            if isinstance(ent, dict):
                sym = ent.get("sym") or ent.get("symbol") or ent.get("id")
                if sym is None:
                    continue
                if "x" in ent and "y" in ent:
                    try:
                        yield str(sym), int(ent["x"]), int(ent["y"])
                    except Exception:
                        continue
                    continue
                for k in ("pos", "xy"):
                    if k in ent:
                        xy = _coerce_xy_pair(ent[k])
                        if xy:
                            yield str(sym), xy[0], xy[1]
                        break
        return
    # その他は無視
    return

def try_press_switch(cur_map_id: str, cur_map: Dict[str, Any]) -> Optional[str]:
    """
    押し順式スイッチ（a/b/c/d）のインタラクションを **型を崩さず** 安定に処理する。

    重要ポイント：
      - 押せる条件は「足元 or 上下左右に隣接」。
      - 途中進行は FLAGS["puzzles_progress"][f"{map_id}:{puzzle_id}"] = ["a","b",...] に保存。
      - クリア時は FLAGS["puzzles_solved"] に (map_id, puzzle_id) を list[tuple] で重複なし追加。
      - 見た目は参照の付け替えのみ（current_textures["special"][k] = ..._lit）。※再ロード禁止
      - 封鎖解除は MAP レイアウトを '.' に書き換え（save_system 側の再構築とも整合）。
    """
    # すでにクリア済みなら、点滅を止めて lit 参照に寄せておしまい（冪等）
    if game_state.state.get("switch_solved") or _is_current_map_switch_puzzle_solved(cur_map_id):
        spec = (game_state.current_textures.get("special") or {})
        for k in ("a", "b", "c", "d"):
            lit_key = f"{k}_lit"
            if isinstance(spec.get(lit_key), dict) and "arr" in spec[lit_key]:
                spec[k] = spec[lit_key]  # ★ 参照の付け替えのみ（画像再ロードはしない）
        game_state.state.setdefault("switch_blink_active", set()).clear()
        game_state.state["switch_solved"] = True
        return None

    # 現在タイル座標（押せるかどうかの近接判定に使用）
    px, py = _player_tile_xy()

    # パズル定義の取得と基本検証
    puzzle: Dict[str, Any] = cur_map.get("puzzle", {}) or {}
    switches: Any = puzzle.get("switches", {}) or {}
    answer: List[str] = list(puzzle.get("answer", []) or [])
    puzzle_id: str = puzzle.get("id", "switch_A")
    if not switches or not answer:
        return None  # 定義が不十分なら何もしない

    # どのスイッチが押されたか：あらゆる定義形を正規化して探索
    pressed_symbol: Optional[str] = None
    for sym, sx, sy in _iter_switch_entries(switches):
        if _is_adjacent_or_same(px, py, sx, sy):
            pressed_symbol = str(sym)
            break
    if pressed_symbol is None:
        return None

    # ランタイム（非永続）と永続の準備
    st = game_state.state
    st.pop("__last_switch_result", None)   # ★ 直前フレームの残りを掃除
    f = game_state.FLAGS
    prog: List[str] = st.setdefault("switch_progress", [])
    blink_set: Set[str] = st.setdefault("switch_blink_active", set())
    pp: Dict[str, List[str]] = f.setdefault("puzzles_progress", {})
    progress_key = f"{cur_map_id}:{puzzle_id}"

    # 次に期待される記号と比較
    next_index = len(prog)
    if next_index >= len(answer):
        return None  # 既に満たしているはず（冪等）
    should_be = str(answer[next_index])

    if pressed_symbol == should_be:
        # ===== 正解：一歩前進 =====
        prog.append(pressed_symbol)
        blink_set.add(pressed_symbol)     # 途中は点滅対象
        pp[progress_key] = list(prog)     # ★ 永続へ同期（list[str]）

        # まだ途中ならトーストだけ返して終了
        if len(prog) < len(answer):
            st["__last_switch_result"] = "ok" # ★ 途中正解
            msg = puzzle.get("progress_toast", "スイッチ…正しい手応えだ。")
            game_state.message = msg
            return msg

        # ===== 全問正解：封鎖解除 + クリア登録 + 見た目更新 =====
        # 1) クリア登録（list[tuple] を維持・重複なし）
        solved_list: List[Tuple[str, str]] = list(f.get("puzzles_solved", []))
        solved_set = {tuple(x) for x in solved_list}
        key = (cur_map_id, puzzle_id)
        if key not in solved_set:
            solved_list.append(key)
        f["puzzles_solved"] = [tuple(x) for x in solved_list]  # ★ 最終型は list[tuple]

        # 2) 途中進行をクリア（永続／ランタイム）
        pp.pop(progress_key, None)
        st["switch_progress"] = []
        blink_set.clear()
        st["switch_solved"] = True
        st["switch_applied"] = True

        # 3) 封鎖解除：opens / unlock_barriers の座標を '.' に
        opens = (puzzle.get("opens") or []) + (puzzle.get("unlock_barriers") or [])
        layout = MAPS[cur_map_id]["layout"]
        new_rows: List[str] = []
        for y, row in enumerate(layout):
            row_list = list(row)
            for (tx, ty) in opens:
                if ty == y and 0 <= tx < len(row_list):
                    row_list[tx] = '.'
            new_rows.append("".join(row_list))
        MAPS[cur_map_id]["layout"] = new_rows

        # 4) 見た目更新は参照の付け替えのみ（再ロード禁止）
        spec = (game_state.current_textures.get("special") or {})
        for k in ("a", "b", "c", "d"):
            lit_key = f"{k}_lit"
            if isinstance(spec.get(lit_key), dict) and "arr" in spec[lit_key]:
                spec[k] = spec[lit_key]

        st["__last_switch_result"] = "solved"  # ★ クリア
        msg = puzzle.get("solved_toast", "ガシャン！…どこかの封鎖が外れた！")
        game_state.message = msg
        return msg

    else:
        # ===== 誤答：最初からやり直し（残留防止） =====
        prog.clear()
        blink_set.clear()
        pp[progress_key] = []  # ★ 永続も空にする（ロード後の再構築で残留しない）
        st["__last_switch_result"] = "ng"      # ★ 誤答
        msg = puzzle.get("retry_toast", "…違う！最初からやり直そう。")
        game_state.message = msg
        return msg

def _is_current_map_switch_puzzle_solved(cur_map_id: str) -> bool:
    """
    現在マップのスイッチ系パズルがクリア済みかを、FLAGS['puzzles_solved'] から判定する。
    list / set 混在に堅牢対応。
    """
    from core.maps import MAPS
    pid = (MAPS.get(cur_map_id, {}).get("puzzle") or {}).get("id")
    if not pid:
        return False
    ps = game_state.FLAGS.get("puzzles_solved") or []
    pairs = {tuple(x) for x in (ps if isinstance(ps, list) else list(ps))}
    return (cur_map_id, pid) in pairs


