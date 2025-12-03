# run_preview.py
# ============================================================
# run_preview.py - 敵キャラ（追跡者）アニメーション確認用スクリプト
# ============================================================
# このスクリプトは、敵キャラクターの走りアニメーション用スプライト
# （連番 PNG 画像）を Pygame 上でループ再生し、動きやスケールを
# 確認するための「プレビュー専用ツール」です。
#
# 機能概要:
#   - FRAMES に列挙した PNG 画像を読み込み、順番に再生
#   - ウィンドウ中央に拡大・縮小して表示（ドット絵用ニアレスト拡大）
#   - 再生速度（FPS）やスケール倍率をキーボードで変更可能
#   - PingPong（往復）再生、背景色の明暗切り替えなどに対応
#
# 操作方法（キーボード）:
#   - Esc / Q      : 終了
#   - Space        : 一時停止 / 再開
#   - [ / ]        : 再生 FPS を 1〜60 の範囲で減少 / 増加
#   - ↑ / ↓        : スケール倍率を 0.1〜8.0 の範囲で拡大 / 縮小
#   - P            : PingPong（往復）再生の ON / OFF 切り替え
#   - B            : 背景を暗いグレー / 明るいグレーに切り替え
#   - 1〜9         : 該当番号のフレームへジャンプ（frame1 → 1 キー）
#
# 使い方:
#   1) run_preview.py と同じディレクトリに frame1.png 〜 frame6.png を配置します。
#   2) ターミナルから `python run_preview.py` を実行します。
#   3) 表示されたウィンドウ内で上記キー操作を使い、敵キャラの
#      アニメーションの見た目・タイミング・倍率などを調整しながら確認します。
#
# ============================================================
import os
import sys
import pygame
from pathlib import Path

# —— 1) このスクリプトがあるディレクトリを基準にする ——
BASE_DIR = Path(__file__).resolve().parent

FRAMES = [
    "frame1.png",
    "frame2.png",
    "frame3.png",
    "frame4.png",
    "frame5.png",
    "frame6.png",
]

# —— 2) 基本設定 ——
SCREEN_W, SCREEN_H = 600, 600         # プレビュー用の画面サイズ
BASE_SCALE = 0.6                       # 初期スケール（画像原寸×倍率）
PIXEL_ART_NEAREST = True               # Trueだとドットを保つ拡大（ニアレスト）

# —— 2) 実装 ——
def load_frames(names):
    imgs = []
    for name in names:
        path = BASE_DIR / name   # スクリプトと同じディレクトリを基準にする
        if not path.exists():
            print(f"[WARN] not found: {path}")
            continue
        img = pygame.image.load(str(path)).convert_alpha()
        imgs.append(img)
    if not imgs:
        raise SystemExit("No frames loaded. Check FRAMES paths.")
    return imgs

def scale_image(img, scale, nearest=True):
    if scale == 1.0:
        return img
    w, h = img.get_size()
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    if nearest:
        return pygame.transform.scale(img, new_size)  # ニアレスト
    else:
        return pygame.transform.smoothscale(img, new_size)  # スムース
       
def main():
    pygame.init()
    pygame.display.set_caption("Chaser Run – Sprite Preview")
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock = pygame.time.Clock()

    frames = load_frames(FRAMES)
    idx = 0
    fps = 10
    scale = BASE_SCALE
    paused = False
    pingpong = False
    forward = True
    bg_dark = True

    # 自動中心表示のためのヘルパ
    def blit_center(img):
        rect = img.get_rect()
        rect.center = (SCREEN_W // 2, SCREEN_H // 2)
        screen.blit(img, rect)

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); 
                sys.exit(0)
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_q):
                    pygame.quit()
                    sys.exit(0)
                elif e.key == pygame.K_SPACE:
                    paused = not paused
                elif e.key == pygame.K_LEFTBRACKET:   # '['
                    fps = max(1, fps - 1)
                    print(f"FPS: {fps}")
                elif e.key == pygame.K_RIGHTBRACKET:  # ']'
                    fps = min(60, fps + 1)
                    print(f"FPS: {fps}")
                elif e.key == pygame.K_UP:
                    scale = min(8.0, round(scale + 0.1, 2))
                    print(f"Scale: x{scale}")
                elif e.key == pygame.K_DOWN:
                    scale = max(0.1, round(scale - 0.1, 2))
                    print(f"Scale: x{scale}")
                elif e.key == pygame.K_p:
                    pingpong = not pingpong
                    print(f"PingPong: {pingpong}")
                elif e.key == pygame.K_b:
                    bg_dark = not bg_dark
                elif pygame.K_1 <= e.key <= pygame.K_9:
                    jump = e.key - pygame.K_1
                    if jump < len(frames):
                        idx = jump

        # 背景
        c = 18 if bg_dark else 60
        screen.fill((c, c, c))

        # 表示用スケール
        img = scale_image(frames[idx], scale, PIXEL_ART_NEAREST)
        blit_center(img)

        # インフォ小表示
        font = pygame.font.SysFont(None, 22)
        info = f"idx:{idx+1}/{len(frames)}  FPS:{fps}  Scale:x{scale:.2f}  PingPong:{pingpong}"
        txt = font.render(info, True, (200, 200, 200))
        screen.blit(txt, (10, 10))

        pygame.display.flip()

        # アニメ更新
        if not paused:
            if pingpong:
                if forward:
                    idx += 1
                    if idx >= len(frames):
                        idx = len(frames) - 2
                        forward = False
                else:
                    idx -= 1
                    if idx < 0:
                        idx = 1
                        forward = True
            else:
                idx = (idx + 1) % len(frames)

        clock.tick(fps)

if __name__ == "__main__":
    main()
