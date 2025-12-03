# core/tile_types.py

# - 現状エンジンが参照するのは主に "walkable" と "event"。
# - "img" は現行のレイキャスト描画では未使用（将来の2D/ミニマップ差し替え用に残留）。
# - 'E' は “エンディング床”。main.py 側の check_map_triggers() で専用処理。

TILE_TYPES = {
    "#": {"walkable": False, "event": None,         "img": "wall.png"},
    ".": {"walkable": True,  "event": None,         "img": "floor.png"},
    ">": {"walkable": True,  "event": "stair_down", "img": "stair_down.png"},
    "<": {"walkable": True,  "event": "stair_up",   "img": "stair_up.png"},
    'H': {"walkable": False, "event": None},  # lab外壁
    "D": {"walkable": False, "event": "door",       "img": "door.png"},
    "E": {"walkable": True,  "event": "event",      "img": "event.png"}, # “エンディング床”にした。
    "N": {"walkable": True,  "event": "npc",        "img": "npc.png"},
    'A': {"walkable": True, "event": None},
    'G': {"walkable": True, "event": None},

    'w': {"walkable": False, "event": None},   # 川／水面（通行不可）
    'B': {"walkable": True,  "event": None},   # 橋（通行可）
    'O': {"walkable": False, "event": "tree"}, # 大木（斧で3ヒット→橋生成）
    'M': {"walkable": False, "event": "guardian"}, # 守人（供物で解除）
    'F': {"walkable": False, "event": "fog"},  # 濃霧（守人解除で一括晴れ）
    'L': {"walkable": False, "event": None}, 

        # --- 入口ホール用パズルタイル ---

    # eventは将来の拡張用に割り当て（押下判定フック用）
    'a': {"walkable": True,  "event": "switch_a"},
    'b': {"walkable": True,  "event": "switch_b"},
    'c': {"walkable": True,  "event": "switch_c"},
    'd': {"walkable": True,  "event": "switch_d"},

    # “封鎖壁。正解時に '.' に差し替えて通行可能にする想定。
    'X': {"walkable": False, "event": None},

        # 肖像画（壁として扱う＝通れない）
    'P': {"walkable": False, "event": None},  # Portrait P
    'Q': {"walkable": False, "event": None},
    'R': {"walkable": False, "event": None},
    'S': {"walkable": False, "event": None},
    # ここにどんどん追加OK！
}
