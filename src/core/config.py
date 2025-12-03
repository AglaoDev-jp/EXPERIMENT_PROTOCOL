# core/config.py

WIDTH = 640
HEIGHT = 480
HALF_HEIGHT = HEIGHT // 2
FOV = 3.14159265 / 3  # math.pi / 3
NUM_RAYS = 120
MAX_DEPTH = 800
TILE = 64
MAP_SIZE = 10
PLAYER_SPEED = 3

DELTA_ANGLE = FOV / NUM_RAYS  # FOV（視野角）とNUM_RAYS（レイ本数）から計算される定数

# ---  開発時の自己診断の厳格度（Trueで警告や例外を多めに） ---
DEV_STRICT_VALIDATION = True

# ---  ミニマップの配色（ここだけ変えれば全体が付いてくる） ---
MINIMAP_COLORS = {
    "wall":      (40, 160, 60, 255),   # 壁/障害物
    "floor":     (220, 220, 220, 80),  # 床
    "exit":      (235, 205, 40, 220),  # '>' 進む出口
    "entrance":  (90, 210, 255, 220),  # '<' 戻る入口
    "border":    (0, 0, 0, 180),       # 目立たせる細枠
}