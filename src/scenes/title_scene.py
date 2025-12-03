# scenes/title_scene.py
# -*- coding: utf-8 -*-
"""
タイトル画面シーン
- 黒背景にタイトル（画像があれば画像、なければフォント描画）
- メニューは Start / Load（画像があれば画像、なければテキスト）
- ↑↓で選択、Enter/Space/Z で決定（※ Esc / q での終了処理は本クラスから削除）
- エフェクト:
  - タイトルはゆるい明滅（sin 波でアルファ乗算）
  - 選択中は 0.5 秒周期で点滅
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional, Callable
import pygame, math
import traceback
import sys

# 画像が無いときのフォールバックに使う（既存プロジェクトのフォントヘルパ）
from core.fonts import render_text  # Noto Sans JP を使った縁取りテキスト
from core.transitions import fade_in, fade_out  # フェードアウト演出

# エンディングクリアフラグをここから読む
import core.game_state as game_state

class TitleScene:
    def __init__(self,
                 base_dir: Path,
                 sound_manager=None,
                 on_start: Optional[Callable[[pygame.Surface], None]] = None,
                 on_toggle_fullscreen: Optional[Callable[[], None]] = None):
        """
        base_dir            : データフォルダのルート
        sound_manager       : 効果音・BGM用のマネージャ
        on_start            : "start" が選ばれたときに実行する任意コールバック
        on_toggle_fullscreen: F11 が押されたときに呼び出すフルスクリーン切替関数
                              （main.py 側の toggle_fullscreen を渡してもらう）
        """
        # -----------------------------------------
        # 内部状態の初期化
        # -----------------------------------------
        self.base_dir = Path(base_dir)
        # メニュー項目　基本は Start / Load / Audio
        # 内部キーは小文字、画面表示は opt.upper() で "START" / "LOAD" / "AUDIO" になります。
        self.options = ["start", "load", "audio"]

        # ★ エンディングクリア済みなら「Afterword」を追加
        #   - game_state.afterword_unlocked が True のときだけ表示
        try:
            if getattr(game_state, "afterword_unlocked", False):
                self.options.append("afterword")
        except Exception as e:
            # フラグ取得で何かあってもタイトル自体は動いてほしいので握りつぶす
            print(f"[TitleScene][WARN] cannot read afterword flag: {e}")
        # 現在選択中のインデックス（0=Start,1=Load,2=Audio, …）
        self.cursor = 0                    

        self.snd = sound_manager
        self.on_start = on_start          # START選択時の任意コールバック
        self.on_toggle_fullscreen = on_toggle_fullscreen  # F11用コールバック

        # -----------------------------------------
        # サウンド再生用。None の場合は無音で動作するフォールバック。
        # 型は循環参照を避けるために緩く扱います（duck typing）。
        # -----------------------------------------
        self.snd = sound_manager
        self.on_start = on_start  # ★ START選択時に呼び出す任意コールバック
        # ★ sound_manager が None なら“どこから呼ばれたか”を出力（犯人特定用）
        if self.snd is None:
            print("[TitleScene][ERROR] sound_manager is None. Call stack follows:")
            traceback.print_stack(limit=10)  # ← 呼び出し元のファイル/行が出ます

        # サウンドの事前チェック（あればログ。無ければ原因追跡のヒントに）
        if self.snd is None:
            print("[TitleScene][INFO] sound_manager is None (silent fallback).")
        else:
            try:
                has_cur = getattr(self.snd, "has_se", None)
                if callable(has_cur):
                    if not self.snd.has_se("cursor"):
                        print("[TitleScene][WARN] SE 'cursor' is not loaded.")
                    if not self.snd.has_se("select"):
                        print("[TitleScene][WARN] SE 'select' is not loaded.")
                else:
                    # 旧版 SoundManager 互換：キー存在を直接辞書で推測
                    keys = getattr(self.snd, "se", {})
                    if not isinstance(keys, dict):
                        print("[TitleScene][WARN] sound_manager.se is not a dict.")
                    else:
                        if "cursor" not in keys:
                            print("[TitleScene][WARN] SE 'cursor' is not loaded.")
                        if "select" not in keys:
                            print("[TitleScene][WARN] SE 'select' is not loaded.")
            except Exception as e:
                print(f"[TitleScene][WARN] sound_manager pre-check failed: {e}")

        # -----------------------------------------
        # タイトル画像・アイコン画像のロード
        # 画像が無ければ None（→ テキスト描画にフォールバック）
        # -----------------------------------------
        # タイトルロゴ画像
        self.title_img: Optional[pygame.Surface] = self._try_load("assets/ui/title.png")

        # メニューアイコン（通常時）
        # "afterword" 用の画像も追加しておく。
        # 画像ファイルが存在しない場合は _try_load() が None を返し、
        # のちの描画処理でテキストフォールバックするので安全。
        self.icon = {
            "start":     self._try_load("assets/ui/start.png"),
            "load":      self._try_load("assets/ui/load.png"),
            "audio":     self._try_load("assets/ui/audio.png"),
            "afterword": self._try_load("assets/ui/afterword.png"),
        }

        # メニューアイコン（選択時）
        # なければ通常版アイコンで補うので、最低限どちらか1つあれば描画可能。
        self.icon_sel = {
            "start":     self._try_load("assets/ui/start_sel.png"),
            "load":      self._try_load("assets/ui/load_sel.png"),
            "audio":     self._try_load("assets/ui/audio_sel.png"),
            "afterword": self._try_load("assets/ui/afterword_sel.png"),
        }

        # -----------------------------------------
        # タイトル画像のレイアウト設定
        # -----------------------------------------
        self.title_scale_mode = "cover"  # "contain"=はみ出さない / "cover"=画面を満たす
        self.title_max_h_ratio = 0.42      # 画面高さに対する最大比（例: 0.42 = 画面高の42%）
        self.title_max_w_ratio = 0.90      # 画面幅に対する最大比（左右に少し余白）
        self.title_center_y_ratio = 1.0/3.0  # 画像の縦位置（画面高の1/3あたり）
        

        # -----------------------------------------
        # START/LOAD 画像のスケーリング設定
        # -----------------------------------------
        # まず“目標高さ”を決める（画面高の何割にするか）
        self.menu_icon_target_h_ratio = 0.8  # 例: 画面高の 80%（値はプロジェクト側で調整）
        # でかくなりすぎを防ぐ“絶対上限”
        self.menu_icon_max_w_ratio = 0.60      # 幅の上限（画面幅の60%）
        self.menu_icon_max_h_ratio = 0.25      # 高さの上限
        # 画面サイズが変わったときに一度だけ再スケールしたいので、キャッシュを持つ
        
        self._scale_cache_key = None # サイズ＋比率の複合キー
        self._scaled_icon_normal = {}  # opt -> Surface
        self._scaled_icon_sel = {}     # opt -> Surface
        
        # -----------------------------------------
        # エフェクト・アニメ用のパラメータ
        # -----------------------------------------
        # タイトルの明滅：最小～最大の明るさを 2.4 秒周期で往復
        self.title_min_alpha = 0.6    # 一番暗いとき（乗算 0.6）
        self.title_max_alpha = 1.0    # 一番明るいとき（乗算 1.0）
        self.title_period_ms = 2400   # 周期 2.4 秒

        # 選択中の点滅（0.5 秒ごとに ON/OFF）
        self.blink_period_ms = 500

    def _show_disclaimer(self, screen: pygame.Surface) -> None:
        """
        起動直後などに一度だけ表示する「本作品はフィクションです」注意書き。
        - 黒背景に日本語＋英語のテキストを描画
        - fade_in → 一定時間表示 → fade_out という流れ
        - キー入力によるスキップなどは付けず、数秒で自動的にタイトルへ遷移させる
        """
        clock = pygame.time.Clock()

        # 表示するテキスト行（必要に応じて改行位置を調整）
        lines = [
            "本作品はフィクションです。",
            "実在の人物・団体・名称・事件とは一切関係ありません。",
            "",
            "This work is a piece of fiction.",
            "Any resemblance to actual persons, organizations,",
            "or events is purely coincidental.",
        ]

        # 画面中央付近に整列させるための簡単なレイアウト計算
        w, h = screen.get_size()
        line_height = 28  # 1行あたりの高さ（フォントサイズに合わせて調整）
        total_height = line_height * len(lines)
        base_y = (h - total_height) // 2  # 一番上の行のY座標

        def _draw_disclaimer() -> None:
            """注意書きテキストを描画する関数（fade_in/out の draw_under からも呼ぶ）"""
            screen.fill((0, 0, 0))  # 完全な黒背景

            # 各行を中央揃えで描画
            for i, text in enumerate(lines):
                if not text:
                    continue  # 空行はスキップ（行間としてだけカウント）
                # render_text は既存プロジェクトのフォントヘルパーを使用
                surf = render_text(
                    text,
                    size=20,                  # フォントサイズ（お好みで調整）
                    color=(255, 255, 255),    # 白文字
                    shadow=True,              # うっすら影を付けて読みやすく
                    outline=False,
                )
                rect = surf.get_rect(center=(w // 2, base_y + i * line_height))
                screen.blit(surf, rect)

        # --- 1) フェードイン（黒→注意書き） ---
        fade_in(screen, duration_ms=600, draw_under=_draw_disclaimer)

        # --- 2) 一定時間そのまま表示（例: 2000ms = 2秒） ---
        stay_ms = 2000
        start = pygame.time.get_ticks()
        while True:
            now = pygame.time.get_ticks()
            if now - start >= stay_ms:
                break
            # QUIT イベントを拾っておく（ウィンドウ×で落とせるように）
            for event in pygame.event.get():
                # ◆ ウィンドウ×ボタン
                if event.type == pygame.QUIT:
                    try:
                        pygame.quit()
                    except Exception:
                        pass
                    sys.exit(0)

                # ◆ F11 でフルスクリーン切り替えを許可
                if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    if self.on_toggle_fullscreen is not None:
                        try:
                            self.on_toggle_fullscreen()
                        except Exception as e:
                            print(f"[TitleScene][WARN] on_toggle_fullscreen() failed in disclaimer: {e}")
                    else:
                        # コールバックが無い場合は直接トグル
                        try:
                            pygame.display.toggle_fullscreen()
                        except Exception as e:
                            print(f"[TitleScene][WARN] pygame.display.toggle_fullscreen() failed in disclaimer: {e}")
                    # フルスクリーンを切り替えたあとも、注意書きの表示自体は続けたいので
                    # ここでは break / return せずそのままループ継続します。
                    continue

            _draw_disclaimer()
            pygame.display.flip()
            clock.tick(60)

        # --- 3) フェードアウト（注意書き→黒） ---
        fade_out(screen, duration_ms=600, draw_under=_draw_disclaimer)

        # 最後に真っ黒な状態で揃えておく（このあとタイトルが描画される）
        screen.fill((0, 0, 0))
        pygame.display.flip()

    def _open_audio_menu_from_title(self, screen: pygame.Surface) -> None:
        """
        タイトル画面から音量調整メニュー（MenuScene）だけをモーダルに開くヘルパー。

        - MenuScene をそのまま使い回しつつ、
          メニュー項目は「音量調整」「閉じる」の2つだけに絞る。
        - 終了するまでここでループし、終了したらタイトル画面に戻る。
        """
        # ★ 遅延インポートで循環依存を避ける
        from scenes.menu import MenuScene

        # MenuScene 本体を生成（ゲーム本編と同じ SoundManager を共有）
        menu = MenuScene(sound_manager=self.snd)

        # ★ タイトルからの「音量専用モーダル」であることを知らせる
        menu.modal_audio_only = True

        # タイトル経由なので、メインメニューは最低限の2項目だけにする
        # 0:「音量調整」 1:「閉じる」
        menu.options = ["音量調整", "閉じる"]
        menu.cursor = 0

        # いきなり音量調整画面から開始する
        # （必要であれば一度 ESC でメイン項目に戻れます）
        menu.state = "audio"
        menu.audio_cursor = 0  # 0=BGM から

        clock = pygame.time.Clock()
        width, height = screen.get_size()

        while True:
            # ----------------------------
            # 入力処理
            # ----------------------------
            for event in pygame.event.get():
                # ウィンドウ右上×ボタン
                if event.type == pygame.QUIT:
                    try:
                        pygame.quit()
                    except Exception:
                        pass
                    sys.exit(0)

                # MenuScene に処理を委譲
                result = menu.handle_event(event)
                if result == "close":
                    # 「閉じる」が選ばれた / ESC でメニューを閉じた
                    # → タイトル画面へ復帰
                    return

            # ----------------------------
            # 更新・描画
            # ----------------------------
            menu.update()
            menu.draw(screen, width, height)
            pygame.display.flip()
            clock.tick(60)

    # =========================================================
    # 画像ロードのヘルパ（失敗時は None を返す）
    # =========================================================
    def _try_load(self, rel_path: str) -> Optional[pygame.Surface]:
        """
        指定の相対パスから画像を読み込みます。
        - 成功: Surface を返す
        - 失敗: None を返す（フォールバックでテキスト描画）
        """
        p = (self.base_dir / rel_path)
        try:
            if not p.exists():
                print(f"[TitleScene] NOT FOUND: {p}")  # ★ これが出たらパス or 大小文字
                return None
            img = pygame.image.load(str(p))
            if pygame.display.get_surface() is not None:
                img = img.convert_alpha()
            print(f"[TitleScene] loaded: {p} size={img.get_width()}x{img.get_height()}")
            return img
        except Exception as e:
            print(f"[TitleScene] load fail: {p} ({e})")
            return None

    # =========================================================
    # メインループ（run）。必須：run_scene() から呼ばれます
    # 戻り値: "start" / "load" 
    # =========================================================
    def run(self, screen: pygame.Surface) -> str:
        """
        タイトル画面を表示し、ユーザーの選択結果を返す。
        - "start": スタートが選ばれた
        - "load" : ロードが選ばれた
        - "afterword": あとがきが選ばれた
        """
        clock = pygame.time.Clock()

        # ★★ 注意書き画面
        #    - ゲーム全体でまだ表示していない場合だけ表示する
        #    - フラグは core.game_state.disclaimer_shown に保存する
        #      （TitleScene を作り直しても共有される）
        if not getattr(game_state, "disclaimer_shown", False):
            self._show_disclaimer(screen)
            # モジュール側にフラグを立てる
            setattr(game_state, "disclaimer_shown", True)
            # ついでにインスタンス側も合わせておく（使うかどうかは任意）
            self._disclaimer_shown = True

                
        while True:
            # ----------------------------
            # 入力処理
            # ----------------------------
            for event in pygame.event.get():
                # ウィンドウの×ボタン（pygame.QUIT）
                # タイトル表示中は上位ループが動いていないため、
                # ここで確実にアプリを終了させる。
                # ※ sys.exit() を使うことで呼び出し元へ戻らず即終了。
                if event.type == pygame.QUIT:
                    try:
                        # pygame を先にクリーンアップ
                        pygame.quit()
                    except Exception:
                        # 失敗しても終了は続行
                        pass
                    import sys  # 念のためローカルでも解決可能に
                    sys.exit(0)
                 
                if event.type == pygame.KEYDOWN:

                    # ---------------------------------
                    # F11: フルスクリーン切り替え
                    # ---------------------------------
                    if event.key == pygame.K_F11:
                        # main.py 側から渡されたコールバックがあればそれを呼ぶ
                        if self.on_toggle_fullscreen is not None:
                            try:
                                self.on_toggle_fullscreen()
                            except Exception as e:
                                print(f"[TitleScene][WARN] on_toggle_fullscreen() failed: {e}")
                        else:
                            # 何も渡されていない場合のフォールバックとして、
                            # pygame.display.toggle_fullscreen() を直接呼んでおく
                            try:
                                pygame.display.toggle_fullscreen()
                            except Exception as e:
                                print(f"[TitleScene][WARN] pygame.display.toggle_fullscreen() failed: {e}")
                        # F11 ではメニュー操作はしないので continue
                        continue

                    # メニュー操作
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.cursor = (self.cursor - 1) % len(self.options)
                        # カーソル移動SE
                        if self.snd:
                            try:
                                self.snd.play_se("cursor")
                            except Exception as e:
                                print(f"[TitleScene][WARN] play_se('cursor') failed: {e}")

                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.cursor = (self.cursor + 1) % len(self.options)
                        # カーソル移動SE
                        if self.snd:
                            try:
                                self.snd.play_se("cursor")
                            except Exception as e:
                                print(f"[TitleScene][WARN] play_se('cursor') failed: {e}")

                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
                        # 決定SEを先に鳴らしてから暗転 → 選択結果を返す
                        if self.snd:
                            try:
                                self.snd.play_se("select")
                            except Exception as e:
                                print(f"[TitleScene][WARN] play_se('select') failed: {e}")

                        choice = self.options[self.cursor]  # "start" / "load" / "audio" / "afterword" ...

                        # ★ AUDIO（音量調整）の場合だけは
                        #    ・タイトルを閉じず
                        #    ・MenuScene の音量調整画面をモーダル表示して戻る
                        if choice == "audio":
                            self._open_audio_menu_from_title(screen)
                            # 音量調整が終わったら、再びタイトル画面のループに戻る
                            # （フェードアウトも戻り値も発生させない）
                            continue

                        # --- フェードアウト（現在のタイトル画面を毎フレーム描く）---
                        def _draw_under() -> None:
                            # ここでは flip しない（fade_out 側で行う）
                            screen.fill((0, 0, 0))
                            self._draw_title(screen)
                            self._draw_menu(screen)

                        # 600ms くらいが自然。必要なら調整可（ms=... でも可）
                        fade_out(screen, duration_ms=600, draw_under=_draw_under)

                        # 真っ黒にしておくと次シーンのフェードインにも優しい
                        screen.fill((0, 0, 0))
                        pygame.display.flip()
                        # ★ START 選択時だけ、必要ならコールバックを実行
                        if choice == "start" and self.on_start is not None:
                            try:
                                self.on_start(screen)
                            except Exception as e:
                                print(f"[TitleScene][WARN] on_start() failed: {e}")
                            # 互換性のため戻り値は従来どおり "start"
                            return "start"                        
                        return choice

            # ----------------------------
            # 描画処理
            # ----------------------------
            screen.fill((0, 0, 0))        # 黒背景
            self._draw_title(screen)      # タイトルの明滅
            self._draw_menu(screen)       # Start/Load の点滅

            pygame.display.flip()
            clock.tick(60)

    # ----------------------------
    # タイトル（明滅）描画
    # ----------------------------
    def _draw_title(self, screen: pygame.Surface):
        # --- 明滅係数（0.6～1.0） ---
        t = pygame.time.get_ticks() % self.title_period_ms
        phase = (t / self.title_period_ms) * 2.0 * math.pi
        k = (math.sin(phase) + 1.0) * 0.5
        k = self.title_min_alpha + (self.title_max_alpha - self.title_min_alpha) * k

        if not self.title_img:
            # 画像が無い場合は従来のフォント描画
            title = "Experiment Protocol"
            base = int(200 + 55 * k)  # 200～255
            img = render_text(title, size=48, color=(base, base, base),
                            outline=True, outline_color=(0, 0, 0), outline_px=2)
            rect = img.get_rect(center=(screen.get_width() // 2,
                                        int(screen.get_height() * self.title_center_y_ratio)))
            screen.blit(img, rect)
            return

        # 画像がある場合：スケーリングしてから明滅
        screen_w, screen_h = screen.get_size()
        max_w = int(screen_w * self.title_max_w_ratio)
        max_h = int(screen_h * self.title_max_h_ratio)

        src = self.title_img
        sw, sh = src.get_size()

        if self.title_scale_mode == "cover":
            # 画面を“満たす”ように拡大縮小（はみ出し前提）
            scale = max(max_w / sw, max_h / sh)
        else:
            # デフォルト："contain"＝はみ出さないように“収める”
            scale = min(max_w / sw, max_h / sh)

        # 実際の描画サイズ
        dw, dh = max(1, int(sw * scale)), max(1, int(sh * scale))

        # スムーズに縮小/拡大（ロゴ系は smoothscale が綺麗）
        img2 = pygame.transform.smoothscale(src, (dw, dh)).copy()

        # 明滅（アルファ乗算）
        alpha = int(255 * k)
        img2.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)

        rect = img2.get_rect(center=(
            screen_w // 2,
            int(screen_h * self.title_center_y_ratio)
        ))
        screen.blit(img2, rect)

    # ----------------------------
    # メニュー描画（↑↓で選択、選択中は点滅）
    # ----------------------------
    def _draw_menu(self, screen: pygame.Surface):
        # まずは必要ならスケーリング（1回だけ実行され、以降はキャッシュ）
        self._scale_icons_for_screen(screen)

        cx = screen.get_width() // 2
        cy = screen.get_height() // 2 + 80
        gap = 50  # 項目間隔

        ticks = pygame.time.get_ticks()
        blink_on = ((ticks // self.blink_period_ms) % 2) == 0

        for i, opt in enumerate(self.options):
            is_sel = (i == self.cursor)
            pos = (cx, cy + i * gap)

            # 1) 画像（スケール済み）があれば使う
            img = None
            if is_sel:
                img = self._scaled_icon_sel.get(opt) or self._scaled_icon_normal.get(opt)
            else:
                img = self._scaled_icon_normal.get(opt)

            if img is not None:
                rect = img.get_rect(center=pos)
                if is_sel:
                    # 点滅：α220↔255（コピーに乗算、原本は守る）
                    a = 255 if blink_on else 220
                    temp = img.copy()
                    temp.fill((255, 255, 255, a), special_flags=pygame.BLEND_RGBA_MULT)
                    screen.blit(temp, rect)
                else:
                    screen.blit(img, rect)
                continue  # 画像で描けたら次の項目へ

            # 2) 画像が無い場合はテキストフォールバック

            # メニュー文字列
            if opt == "start":
                label = "START"
            elif opt == "load":
                label = "LOAD"
            elif opt == "afterword": 
                # あとがき用のラベル
                label = "AFTERWORD"
            else:
                # 将来メニューを増やしたときのフォールバック
                label = opt.upper()

            color = (255, 255, 255) if (is_sel and blink_on) else (200, 200, 200)
            img_t = render_text(label, size=28, color=color,
                                outline=True, outline_color=(0, 0, 0), outline_px=2)
            rect_t = img_t.get_rect(center=pos)
            screen.blit(img_t, rect_t)

    def _scale_icons_for_screen(self, screen: pygame.Surface) -> None:
        """
        画面サイズに合わせて START/LOAD 画像を一度だけ縮尺。
        基本は“目標高さ”に合わせる。大きすぎる場合のみ上限で抑える。
        """
        size = screen.get_size()
        # ★ 複合キー（比率を変えたらキャッシュが更新される）
        key = (
            size,
            round(self.menu_icon_target_h_ratio, 6),
            round(self.menu_icon_max_w_ratio, 6),
            round(self.menu_icon_max_h_ratio, 6),
        )
        if self._scale_cache_key == key:
            return

        sw, sh = size
        target_h = max(1, int(sh * self.menu_icon_target_h_ratio))
        max_w    = max(1, int(sw * self.menu_icon_max_w_ratio))
        max_h    = max(1, int(sh * self.menu_icon_max_h_ratio))

        self._scaled_icon_normal.clear()
        self._scaled_icon_sel.clear()

        def _scale_to_target(src: pygame.Surface) -> pygame.Surface:
            w, h = src.get_size()
            if w <= 0 or h <= 0:
                return src.copy()

            # ① 目標高さへ
            scale = target_h / h
            dw, dh = int(w * scale), int(h * scale)

            # ② 上限でクリップ
            if dw > max_w:
                scale = max_w / w
                dw, dh = int(w * scale), int(h * scale)
            if dh > max_h:
                scale = max_h / h
                dw, dh = int(w * scale), int(h * scale)

            return pygame.transform.smoothscale(src, (max(1, dw), max(1, dh)))

        for opt in self.options:
            src_n = self.icon.get(opt)
            if src_n:
                self._scaled_icon_normal[opt] = _scale_to_target(src_n)
            src_s = self.icon_sel.get(opt) or src_n
            if src_s:
                self._scaled_icon_sel[opt] = _scale_to_target(src_s)

        self._scale_cache_key = key  # ★ 更新


