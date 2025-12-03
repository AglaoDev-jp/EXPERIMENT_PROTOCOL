# core/items.py
# -*- coding: utf-8 -*-
"""
アイテム定義と、表示/分岐に使うユーティリティ群。
- ここで「旗(フラグ)アイテム」「消耗品」「ストーリー収集物」などを定義
- 表示名やカテゴリ、エンディング分岐用スコアの算出も一本化
"""

from __future__ import annotations
from typing import Tuple, Dict, Any

# ------------------------------------------------------------
# アイテムのマスタデータ
#   key:  アイテムID（inventoryのキーと一致させる）
#   name: 表示名（Notoで統一）
#   cat:  カテゴリ（"flag","key","consumable","material","clue"など自由）
#   score: 分岐評価で加点する値（収集系や重要フラグなら1など）
#   usable: メニューから「使う」対象か（消耗品など）
#   desc: 短い説明文
# ------------------------------------------------------------
ITEMS_DB: dict[str, dict] = {
    "map_chart": {
        "name": "古びた地図",
        "cat": "tool",
        "score": 0,
        "usable": False,
        "desc": "ミニマップを表示できるようになる。",
    },
    "item_compass": {
        "name": "探知の羅針盤",
        "cat": "tool",
        "score": 0,
        "usable": False,
        "desc": "ミニマップに未取得アイテムの位置を表示する。",
    },
    "axe": {
        "name": "斧",
        "cat": "tool",
        "score": 0,
        "usable": False,
        "desc": "重みのある斧。大木を倒せそう。",
    },
    "spirit_orb": {
        "name": "幽き珠",
        "cat": "offering",
        "score": 0,
        "usable": False,
        "desc": "ほのかに光る珠。何かを鎮める力がある。",
    },
    "key_forest": {
        "name": "銅の鍵",
        "cat": "key",
        "score": 0,
        "usable": False,
        "desc": "くすんだ銅色の鍵。どこの鍵だろう？",
    },
    "key_lab": {
        "name": "銀の鍵",
        "cat": "key",
        "score": 0,
        "usable": False,
        "desc": "古びた真鍮の鍵。どこの鍵だろう？",
    },

}

# 未登録IDのフォールバック（安全策）
def get_item_meta(item_id: str) -> dict:
    return ITEMS_DB.get(item_id, {
        "name": item_id,
        "cat": "misc",
        "score": 0,
        "usable": False,
        "desc": "",
    })

def display_name(item_id: str) -> str:
    return get_item_meta(item_id)["name"]

def is_flag_item(item_id: str) -> bool:
    return get_item_meta(item_id)["cat"] == "flag"

def ending_score(inventory: dict[str, int]) -> int:
    """分岐用のスコア（例：flag/clueなどの score 合計）"""
    score = 0
    for k, cnt in inventory.items():
        if cnt <= 0:
            continue
        meta = get_item_meta(k)
        # 所持数分を足す or 1個でも持ってたら1点、は好みで調整
        score += meta.get("score", 0) * cnt
    return score

def collect_rate(inventory: dict[str, int]) -> tuple[int, int]:
    """収集率の目安（scoreカテゴリ対象の収集達成/総数）"""
    total = sum(1 for k, v in ITEMS_DB.items() if v.get("score", 0) > 0)
    got   = 0
    for k, v in ITEMS_DB.items():
        if v.get("score", 0) > 0 and inventory.get(k, 0) > 0:
            got += 1
    return got, total

"""
SPRITE_DB:
- key:  items.py 内の「アイテムID/インベントリキー」と一致させる（例: "rusty_key"）
- file: assets/textures/ 以下の画像ファイル名（透過PNG推奨）
- scale: 画面上の相対スケール（壁の見え方に合わせて微調整）
- y_offset_px: 画面上で下方向(+)にずらす量。床に“接地”して見せるための調整用。
               例: +12〜+24 くらいで「床に立っている」感じが出やすい？
"""
# スプライト定義テーブル（マップ上に立体表示するアイテム画像の見た目を管理）
# - file       : 画像ファイル名（未配置でもローダで自動プレースホルダーが出る前提）
# - scale      : スプライトの拡大率（1.0 = 原寸）
# - y_offset_px: 画面下からの持ち上げ量（大きいほど浮いて見える）
SPRITE_DB: dict[str, dict] = {
    "map_chart": {
        "file": "item_map_chart.png",      # 置いてなければ自動プレースホルダーが出ます
        "scale": 1.0,
        "y_offset_px": 12,
    },
    "item_compass": {
        "file": "item_compass.png",
        "scale": 1.0,
        "y_offset_px": 12,
    },
    "rusty_key": {
        "file": "item_rusty_key.png",
        "scale": 0.9,
        "y_offset_px": 16,
    },

    "axe": {
        "file": "item_axe.png",            # 画像未配置でもプレースホルダー対応
        "scale": 1.1,                      # 少し大ぶりに見せる（お好みで 1.0〜1.2）
        "y_offset_px": 16,                 # 地面から持ち上げて視認性UP
    },
    "spirit_orb": {
        "file": "item_spirit_orb.png",
        "scale": 1.0,                      # 球体は原寸で見やすいことが多い
        "y_offset_px": 10,                 # ほんの少しだけ浮かせる
    },
    "key_forest": {
        "file": "item_key_lab_1.png",     # 別個の鍵画像を想定（共用なら rusty_key でも可）
        "scale": 0.95,                     # 鍵はやや小さめにすると床になじむ
        "y_offset_px": 16,
    },
    "key_lab": {
        "file": "item_key_lab_2.png",     # 別個の鍵画像を想定（共用なら rusty_key でも可）
        "scale": 0.95,                     # 鍵はやや小さめにすると床になじむ
        "y_offset_px": 16,
    },
    "crest_fragment": {
        "file": "item_crest_fragment.png",
        "scale": 1.0,
        "y_offset_px": 14,
    },
    "old_diary": {
        "file": "item_old_diary.png",
        "scale": 1.0,
        "y_offset_px": 12,
    },
    "torch": {
        "file": "item_torch.png",
        "scale": 1.2,                      # 背の高いスプライトは少し大きめ
        "y_offset_px": 18,                 # 下端が床にめり込まないよう高めに
    },
    "guardian": {
    "file": "forest_guardian.png",   # 透過PNG推奨（assets/textures/guardian.png）
    "scale": 1.15,            # 立ち像なので少し大きめ
    "y_offset_px": 12,        # 床に“沈みにくい”微調整
    },
}


def get_sprite_meta(item_id: str) -> dict:
    """スプライト用メタの安全取得（未登録は無難なデフォルト）"""
    return SPRITE_DB.get(item_id, {
        "file": "item_placeholder.png",  # 置換される（存在しなければ自動プレースホルダ）
        "scale": 1.0,
        "y_offset_px": 12,
    })

def infer_internal_type(item_id: str, kind: str) -> str:
    """
    新方式の ('id','kind','pos') から描画・ロジック用の内部type名を決定します。
    - ここを一箇所に固定することで、将来の種類追加も安全になります。
    """
    if kind == "tool" and item_id.startswith("axe"):
        return "axe"
    if kind == "offering":
        return "spirit_orb"
    if kind == "key":
        # ★ 鍵の種類を id の接頭辞で判定
        if str(item_id).startswith("key_lab"):
            return "key_lab"
        if str(item_id).startswith("key_forest"):
            return "key_forest"
        # 不明な鍵はフォールバックで森鍵扱い（必要なら別既定に変更可）
        return "key_forest"
    # 既定: idをそのままtype扱い（unique小物など）
    return item_id or "misc"

def normalize_item_entry(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    アイテム定義を「描画・拾得処理に必要な最小共通形」に正規化します。
    返す形: {"id": str, "type": str, "tile": (x,y), "picked": bool}
    - 旧式: {"id","type","tile","picked"} をそのまま受け入れ
    - 新式: {"id","kind","name","pos"} を内部形式に変換
    """
    if "tile" in raw and "type" in raw:
        # 旧式：ほぼパススルー（pickedだけ安全化）
        return {
            "id": raw.get("id", ""),
            "type": raw["type"],
            "tile": tuple(raw["tile"]),
            "picked": bool(raw.get("picked", False)),
        }

    # 新式
    kind = raw.get("kind", "misc")
    type_name = infer_internal_type(raw.get("id", "misc"), kind)
    return {
        "id": raw.get("id", ""),
        "type": type_name,
        "tile": tuple(raw.get("pos", (0, 0))),
        "picked": bool(raw.get("picked", False)),
    }