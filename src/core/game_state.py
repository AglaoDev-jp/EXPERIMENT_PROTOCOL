# core/game_state.py
from core.config import PLAYER_SPEED, TILE

# --- ゲーム状態変数 ---

# 現在のマップID
current_map_id = "forest_1"

# プレイヤー座標 (ピクセル単位)
# ↓ 通行可能なタイル (2,1) の中心に変更（layout[1][2] == 0）
player_x = TILE * 2 + TILE // 2  # タイル(2,1)の中心
player_y = TILE * 1 + TILE // 2  # タイル(2,1)の中心

# ▼インベントリ（所持数カウント方式）
inventory = {
    "rusty_key": 0,   # さびた鍵
}

# プレイヤーの向き (ラジアン)
player_angle = 0

# プレイヤーの移動速度 (configから取得)
player_speed = PLAYER_SPEED

# --- バウンス防止用：最後に発動したトリガー情報 ---
last_triggered_map = None           # 最後に移動した先のマップID
last_triggered_pos = None           # 最後に発動したタイル座標 (x_tile, y_tile)

# --- 現在使用中のテクスチャを保持する辞書 ---
# キー: "wall", "floor", "ceiling"
current_textures = {
    "wall": None,
    "floor": None,
    "ceiling": None,
}

# 一度開けたドアを記録（セーブ対応もしやすい）
opened_doors = {}   # key: (map_id, door_id) -> True

def is_door_opened(map_id: str, door_id: str) -> bool:
    """指定マップ・指定ドアIDのドアが既に開いているかを判定する。"""
    return opened_doors.get((map_id, door_id), False)


def mark_door_opened(map_id: str, door_id: str) -> None:
    """指定マップ・指定ドアIDのドアを開いた状態として記録する。"""
    if not door_id:
        return
    opened_doors[(map_id, door_id)] = True
    
# --- フロア移動用モードとトリガー ---
state = {
    "mode": "normal",           # "normal" or "map_confirm"
    "pending_trigger": None,    # 現在確認中のトリガー（辞書or None）
    
}

# === 差分フラグ（セーブ対象）============================
# ・MAPのベース定義(MAPS)は不変に保ち、進行の“差分だけ”をここで管理します。
# ・例：アイテムの取得済み個体ID、開けた宝箱ID、押したスイッチ、訪問済みマスなど。
# ・JSON保存のため、save_system.py 側で set→list→set の相互変換を行います。
try:
    FLAGS  # すでに他所で定義されていれば触らない（多重インポート対策）
except NameError:
    FLAGS = {}

# ▼アイテム取得済み“個体ID”の集合
#   個体IDの例: "forest_1:item:map_chart@3,3"
#   生成は interactions.py 内の make_entity_key() を利用します。
FLAGS.setdefault("picked_items", set())

# ▼（任意）宝箱を導入するなら：開封済み“個体ID”の集合

FLAGS.setdefault("chests_looted", set())

# ▼（任意）スイッチやドアなど、差分管理したいものが増えたらここに追加
# FLAGS.setdefault("doors_opened", set())
# FLAGS.setdefault("switches_pressed", set())
# ======================================================


# 画面にメッセージを一瞬表示（トースト）
ui_msg = ""
ui_msg_until = 0  # pygame.time.get_ticks() の値を入れる

# --- 累積プレイ時間（秒） ---
playtime_sec = 0.0

# 進行フラグ大辞典📕
FLAGS = globals().get("FLAGS", {})

# すでに他の set を使っている設計に合わせます
FLAGS.setdefault("fog_cleared", set())   
FLAGS.setdefault("doors_opened", set())  
FLAGS.setdefault("trees_chopped", set()) 
FLAGS.setdefault("puzzles_solved", set())

# ★ 新規：ムービー再生済み（mapごと / 動画IDごと）
#   例: ("forest_4", "fog_intro") を格納
FLAGS.setdefault("videos_played", set())
# ★ 新規：発火済みの近接トリガ（動画・追跡者スポーン・エンディング等）を一意IDで管理
#    例: "dungeon_2:chaser_spawn:chaser_at_split" のように <map_id>:<kind>:<id> で保存
FLAGS.setdefault("triggers_fired", set())

def make_trigger_id(kind: str, trig_id: str, map_id: str | None = None) -> str:
    """
    近接トリガの一意IDを統一フォーマットで生成:
      "<map_id>:<kind>:<trig_id>"
    - kind   : "video", "chaser_spawn", "ending" など
    - trig_id: マップ内で一意な任意の名前（"chaser_at_split" など）
    - map_id : 省略時は現在マップ（current_map_id）を使用
    """
    mid = (map_id or current_map_id)
    return f"{mid}:{kind}:{trig_id}"

def reset_for_new_run() -> None:
    """
    New Game 用に、1周分の状態をまるごと初期値へ戻す。
    - エンディング後に「Start」を選んだときなどで使用。
    - セーブデータそのものは消さない（周回とは独立）。
    """
    # 遅延インポートで循環依存を回避：
    # save_system 側は game_state を import 済みなので、
    # ここでは関数の中で import します。
    from core import save_system as _save_system

    global current_map_id, player_x, player_y, player_angle, player_speed
    global last_triggered_map, last_triggered_pos
    global current_textures, opened_doors
    global ui_msg, ui_msg_until, playtime_sec, state, FLAGS, inventory

    # 1) マップとプレイヤーの位置・向き・速度を初期値に戻す
    current_map_id = "forest_1"
    # ★ここはファイル先頭の初期値と揃えています
    player_x = TILE * 2 + TILE // 2  # タイル(2,1)の中心
    player_y = TILE * 1 + TILE // 2  # タイル(2,1)の中心
    player_angle = 0
    player_speed = PLAYER_SPEED

    # 2) 直近トリガ情報もクリア
    last_triggered_map = None
    last_triggered_pos = None

    # 3) 現在使用中テクスチャをクリア（次のマップ読込で再設定）
    current_textures.clear()
    current_textures.update({
        "wall": None,
        "floor": None,
        "ceiling": None,
    })

    # 4) ドア開閉情報をリセット
    opened_doors.clear()

    # 5) インベントリは「持ち物の個数」だけを 0 に戻す
    #    キーの種類はそのまま残すことで、後からアイテムが増えても安全。
    for k in list(inventory.keys()):
        inventory[k] = 0

    # 6) UI トースト関連とプレイ時間のリセット
    ui_msg = ""
    ui_msg_until = 0
    playtime_sec = 0.0

    # 7) ランタイム state を初期状態へ
    #   - chaser などの一時情報もまとめて消える
    state.clear()
    state.update({
        "mode": "normal",        # 通常探索モード
        "pending_trigger": None, # 近接トリガ確認中なし
        # 他の一時キーは必要になったタイミングで setdefault されます
    })

    # 8) 進行フラグ（FLAGS）のベースラインを初期化
    #    doors_opened / fog_cleared / videos_played 等が全部まっさらになります。
    _save_system._reset_flags_baseline()

    # 9) 念のため runtime 専用の triggers_fired も明示的にクリア
    FLAGS.setdefault("triggers_fired", set())
    FLAGS["triggers_fired"].clear()
