# scenes/end_roll.py
# -*- coding: utf-8 -*-
"""
黒背景にクレジットを縦スクロール表示し、最後に「キー入力を促す」文言を
サイン波で点滅させるエンドロール・シーン。
- .run(screen) を持ち、scene_manager.run_scene() から呼べます。
- 終了条件：
  1) クレジットがすべて画面外へ流れ終えた後、
  2) 何かキーが押されたら .run を抜ける
"""

from __future__ import annotations
from typing import List, Tuple
import pygame
import math
import io
try:
    # 既存の鍵を一元利用（複製禁止）
    from core.sound_manager import fernet
except Exception:
    fernet = None

from pathlib import Path

# 既存プロジェクトの共通系（存在しない場合は最低限のフォールバック）
try:
    from core.config import WIDTH, HEIGHT
    from core.fonts import render_text
    from core.transitions import fade_in, fade_out
except Exception:
    # ---- フォールバック（最低限の代替）----
    WIDTH, HEIGHT = 960, 540

    def render_text(text: str, size: int = 24, color=(255, 255, 255), outline=False, outline_px=0):
        font = pygame.font.SysFont(None, size)
        return font.render(text, True, color)

    def fade_in(screen: pygame.Surface, ms: int, draw_under=None):
        clock = pygame.time.Clock()
        t0 = pygame.time.get_ticks()
        while True:
            now = pygame.time.get_ticks()
            a = min(1.0, (now - t0) / max(1, ms))
            if draw_under:
                draw_under()
            overlay = pygame.Surface((WIDTH, HEIGHT))
            overlay.set_alpha(int((1.0 - a) * 255))
            screen.blit(overlay, (0, 0))
            pygame.display.flip()
            if a >= 1.0:
                break
            clock.tick(60)

    def fade_out(screen: pygame.Surface, ms: int, draw_under=None):
        clock = pygame.time.Clock()
        t0 = pygame.time.get_ticks()
        while True:
            now = pygame.time.get_ticks()
            a = min(1.0, (now - t0) / max(1, ms))
            if draw_under:
                draw_under()
            overlay = pygame.Surface((WIDTH, HEIGHT))
            overlay.set_alpha(int(a * 255))
            screen.blit(overlay, (0, 0))
            pygame.display.flip()
            if a >= 1.0:
                break
            clock.tick(60)


class EndRollEvent:
    """
    黒背景・縦スクロール・最後にサイン波点滅の促し文言。
    Intro/Video と同様 .run(screen) でブロッキングに動きます。
    """

    def __init__(
        self,
        credits: List[str],
        *,
        # ▼▼▼ BGM指定 ▼▼▼
        bgm_path: str | None = None,     
        bgm_volume: float = 0.6,
        bgm_fade_ms: int = 1200,
        speed_px_per_sec: float = 80.0,
        line_px: int = 28,
        line_gap: int = 10,
        prompt_text: str = "何かキーを押すとタイトルへ",
        prompt_px: int = 22,
    ) -> None:
        self.credits = credits      
        self._bgm_path = bgm_path
        self._bgm_volume = float(bgm_volume)
        self._bgm_fade_ms = int(bgm_fade_ms)
        self.speed = float(speed_px_per_sec)
        self.line_px = int(line_px)
        self.line_gap = int(line_gap)
        self.prompt_text = prompt_text
        self.prompt_px = int(prompt_px)

        # 事前レイアウト：表示用サーフィス列と高さを計算
        self._surfs: List[Tuple[pygame.Surface, int]] = []  # (surf, h)
        self._total_h = 0

    # ---------- 内部：描画準備 ----------
    def _prepare(self):
        self._surfs.clear()
        self._total_h = 0
        for line in self.credits:
            # 空行はスペーサとして高さだけ確保
            if not line:
                h = self.line_px + self.line_gap
                self._surfs.append((None, h))
                self._total_h += h
                continue
            surf = render_text(line, size=self.line_px, color=(255, 255, 255), outline=True, outline_px=2)
            h = surf.get_height() + self.line_gap
            self._surfs.append((surf, h))
            self._total_h += h

        # スクロール開始位置（画面下の外側から上へ流す）
        self._y_offset = HEIGHT

        # 促しテキスト（後で点滅アルファを変える）
        self._prompt = render_text(self.prompt_text, size=self.prompt_px, color=(255, 255, 255), outline=True, outline_px=2)

    # ---------- 内部：一枚描画 ----------
    def _draw_frame(self, screen: pygame.Surface, now_ms: int, finished: bool):
        # 黒背景でクリア
        screen.fill((0, 0, 0))

        # クレジットの縦積み
        y = int(self._y_offset)
        for surf, h in self._surfs:
            if surf is not None:
                x = (WIDTH - surf.get_width()) // 2
                screen.blit(surf, (x, y))
            y += h

        # スクロール完了後は促し文言をサイン波点滅
        if finished:
            # サイン波で 0.4～1.0 の明滅（約2秒周期）
            phase = (now_ms % 2000) / 2000.0 * 2.0 * math.pi
            k = 0.7 + 0.3 * (math.sin(phase) * 0.5 + 0.5)  # 0.7～1.0程度
            alpha = int(255 * k)

            prompt = self._prompt.copy()
            prompt.set_alpha(alpha)
            px = (WIDTH - prompt.get_width()) // 2
            py = HEIGHT - prompt.get_height() - 24
            screen.blit(prompt, (px, py))

    # ---------- パブリック：ランナー ----------
    def run(self, screen: pygame.Surface) -> None:
        clock = pygame.time.Clock()
        self._prepare()

        # ===== BGM開始（存在すれば、暗号化も自動対応） =====
        if self._bgm_path:
            try:
                _safe_music_play(
                    path=self._bgm_path,
                    volume=self._bgm_volume,
                    fade_ms=self._bgm_fade_ms,
                    loop=True
                )
            except Exception as e:
                print(f"[ENDROLL][WARN] BGM開始に失敗: {self._bgm_path} -> {e}")
                
        draw = lambda: self._draw_frame(screen, pygame.time.get_ticks(), False)
        fade_in(screen, 600, draw_under=draw)

        # スクロールが終わったかどうか
        done_scroll = False

        # ★ 最後のクレジットのブロックを画面下に残すための位置
        #   - bottom_margin_px: 画面下からどれくらい上に「クレジットのいちばん下」を置くか
        #   - final_y_offset: そのときの self._y_offset
        bottom_margin_px = 80  # お好みで 60〜120 あたりを調整してOK
        final_y_offset = HEIGHT - bottom_margin_px - self._total_h

        # スクロール本体

        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); raise SystemExit
                
                # ★ F11: エンドロール中もフルスクリーン切り替えを許可
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F11:
                    try:
                        pygame.display.toggle_fullscreen()
                        # 現在の display Surface を取り直しておく
                        screen = pygame.display.get_surface()
                    except Exception as e:
                        print(f"[ENDROLL][WARN] fullscreen toggle failed: {e}")
                    # F11 はスクロールスキップには使わないので、ここで処理終了
                    continue

                # スクロール中はスキップで早送り（任意）
                if ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
                        # 早送り：一気に「最終表示位置」まで飛ばす
                        self._y_offset = final_y_offset
                        done_scroll = True

            dt = clock.get_time() / 1000.0
            if not done_scroll:
                # 通常スクロール：上方向へ流していく
                self._y_offset -= self.speed * dt

                # ★ クレジット全体の「下端」が、画面下から bottom_margin_px 上に来たら停止
                if self._y_offset <= final_y_offset:
                    # 目標位置でピタッと止める（行き過ぎ防止のため一度固定）
                    self._y_offset = final_y_offset
                    done_scroll = True


            # 描画
            now_ms = pygame.time.get_ticks()
            self._draw_frame(screen, now_ms, done_scroll)
            pygame.display.flip()
            clock.tick(60)

            # スクロール完了後は任意キー待ちで終了
            if done_scroll:
                # 促しを描きつつブロッキングでキー待ち
                waiting = True
                while waiting:
                    for ev in pygame.event.get():
                        if ev.type == pygame.QUIT:
                            pygame.quit(); raise SystemExit
                        
                        # ★ F11: スクロール完了後の「キー待ち」中もフルスクリーン切り替えを許可
                        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F11:
                            try:
                                pygame.display.toggle_fullscreen()
                                screen = pygame.display.get_surface()
                            except Exception as e:
                                print(f"[ENDROLL][WARN] fullscreen toggle failed (waiting): {e}")
                            # タイトルへ戻るトリガーにはしたくないので、待機継続
                            continue

                        if ev.type == pygame.KEYDOWN:
                            # ここで初めて「何かキーが押されたら終了」
                            waiting = False
                            break
                    now_ms = pygame.time.get_ticks()
                    self._draw_frame(screen, now_ms, True)
                    pygame.display.flip()
                    clock.tick(60)
                break

        # 退場フェード
        draw_last = lambda: self._draw_frame(screen, pygame.time.get_ticks(), True)
        fade_out(screen, 600, draw_under=draw_last)

        # ===== BGM停止（フェードアウト） =====
        if self._bgm_path:
            try:
                pygame.mixer.music.fadeout(max(0, self._bgm_fade_ms))
            except Exception as e:
                print(f"[ENDROLL][WARN] BGM停止に失敗: {e}")

        # 戻り値は特に使わないが、将来用にダミーを返しておく
        return {"ended": True}
    
# ================================================================
#  内部：暗号化BGMも安全に読み込んで再生するヘルパ
#  - .mp3.enc は Fernet で復号して BytesIO → music.load()
#  - .mp3/.ogg/.wav など通常音源はそのまま load()
#  - 平文一時ファイルは作成しません（漏えい対策）
# ================================================================
def _safe_music_play(*, path: str, volume: float = 0.6, fade_ms: int = 1000, loop: bool = True) -> None:
    """
    :param path: "assets/sounds/bgm/foo.mp3" または "assets/sounds/bgm/foo.mp3.enc"
    """
    # mixer 初期化（未初期化時の保険）
    if not pygame.mixer.get_init():
        pygame.mixer.init()

    is_enc = str(path).lower().endswith(".enc")
    try:
        if is_enc:
            # Fernet が用意されていない環境では .enc は扱えないので安全に中断
            if fernet is None:
                raise RuntimeError(".enc を再生するには core.sound_manager.fernet が必要です。")            
            # --- 暗号化BGM：メモリ復号で安全再生 ---
            p = Path(path)
            with open(p, "rb") as f:
                encrypted = f.read()
            decrypted = fernet.decrypt(encrypted)   # ← 鍵は sound_manager.py に集約  :contentReference[oaicite:4]{index=4}
            buf = io.BytesIO(decrypted)
            pygame.mixer.music.load(buf)
        else:
            # --- 通常BGM ---
            pygame.mixer.music.load(path)

        pygame.mixer.music.set_volume(max(0.0, min(1.0, float(volume))))
        loops = -1 if loop else 0
        pygame.mixer.music.play(loops=loops, fade_ms=max(0, int(fade_ms)))
    except Exception as e:
        # 呼び出し元で警告を補足表示済み
        raise
