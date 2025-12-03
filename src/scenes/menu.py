# -*- coding: utf-8 -*-
"""
統一UIメニュー：
- メイン項目：ステータス / アイテム / セーブ/ロード / 閉じる
- セーブ/ロード：3スロット、左：一覧、右：詳細。結果は右下固定に短時間表示。
"""

from __future__ import annotations
from pathlib import Path
from datetime import datetime
import json, sys
from typing import Optional, List, Tuple

import pygame
import core.game_state as gs
from core.ui import draw_label
from core.fonts import render_text, get_font
from core.items import display_name, get_item_meta, ending_score, collect_rate
from core.save_system import save_game, load_game
from core import toast_bridge
from core.maps import MAPS
from core.sound_manager import SoundManager

# ---- テーマ色など ----
BG_TINT = (0, 0, 0, 120)
PANEL_BG = (12, 12, 18)
ACCENT   = (255, 210, 50)

# ---- スロット表記 ----
def _label_for_slot(slot: str) -> str:
    return {"slot1": "スロット1（クイック）", "slot2": "スロット2", "slot3": "スロット3"}.get(slot, slot)

# メニューの「ロード決定」処理
def on_select_load(self, slot_name: str) -> None:
    toast_bridge.bind_toast(self.toast)  # ★ロード前にブリッジ
    ok = load_game(slot_name)            # save_system._toast(...) → まずキュー/またはUIへ
    toast_bridge.bind_toast(self.toast)  # 念押し
    # 毎フレームどこかで
    toast_bridge.drain_queue()           # ★取りこぼしがあれば即UIへ
    if ok:
        toast_bridge.show("ロードしました。", ms=3500)  
    # ※ draw() の最後で self.toast.draw(screen) を呼ぶ

# =========================
# 折り返し/省略 ユーティリティ
# =========================
def _wrap_text_by_width_render(text: str, *, size: int, max_w: int, outline: bool = True) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split('\n'):
        if not paragraph:
            lines.append(""); continue
        buf = ""; last_space = -1
        for ch in paragraph:
            test = buf + ch
            w = render_text(test, size=size, color=(255,255,255), outline=outline).get_width()
            if w <= max_w:
                buf = test
                if ch.isspace(): last_space = len(buf)-1
            else:
                if last_space >= 0:
                    lines.append(buf[:last_space].rstrip()); buf = buf[last_space+1:]+ch; last_space = -1
                else:
                    if buf: lines.append(buf)
                    buf = ch
        if buf: lines.append(buf)
    return lines

def _ellipsize_to_width(text: str, font: pygame.font.Font, max_w: int) -> str:
    if font.size(text)[0] <= max_w: return text
    ell = "…"; s = text
    while s and font.size(s + ell)[0] > max_w: s = s[:-1]
    return (s + ell) if s else ell

def _draw_wrapped_into_rect(surface: pygame.Surface, text: str, rect: pygame.Rect,
                            *, size: int = 16, color=(220,220,220),
                            line_gap: int = 4, outline: bool = True,
                            align: str = "left", max_lines: int | None = None) -> int:
    inner_w = max(0, rect.width - 20)
    lines = _wrap_text_by_width_render(text, size=size, max_w=inner_w, outline=outline)
    if max_lines is not None and len(lines) > max_lines:
        font = get_font(size)
        lines = lines[:max_lines]
        lines[-1] = _ellipsize_to_width(lines[-1], font, inner_w)
    y = rect.top + 10
    for ln in lines:
        img = render_text(ln, size=size, color=color, outline=outline)
        x = rect.centerx - img.get_width()//2 if align=="center" else rect.left + 10
        surface.blit(img, (x, y))
        y += img.get_height() + line_gap
    return y

# =========================
# セーブプレビュー（中身だけ読む）
# =========================
def _resolve_saves_dir() -> Path:
    try: return Path(sys.argv[0]).resolve().parent
    except Exception: return Path.cwd()

def _fmt_playtime(sec) -> str:
    if not isinstance(sec, (int, float)): return "00:00:00"
    sec = max(0, int(sec)); h = sec//3600; m=(sec%3600)//60; s=sec%60
    return f"{h:02d}:{m:02d}:{s:02d}"

def _fmt_timestamp(ts) -> str:
    if isinstance(ts, (int, float)): return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    if isinstance(ts, str):
        try: return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
        except Exception: return ts
    return "-"

def _peek_save(slot: str) -> dict | None:
    p = _resolve_saves_dir() / f"{slot}.json"
    if not p.exists(): return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"exists": True, "slot": slot, "broken": True}
    map_id = (data.get("map") or {}).get("id", "-")
    ts     = data.get("saved_at") or data.get("timestamp")
    play_s = (data.get("systems") or {}).get("playtime_sec")
    return {
        "exists": True, "slot": slot, "map_id": map_id,
        "timestamp": _fmt_timestamp(ts),
        "playtime":  _fmt_playtime(play_s),
    }

# =========================
# メニュー本体
# =========================
class MenuScene:
    def __init__(self, sound_manager=None):
        self.sound = sound_manager
        self.state = "main"       
        self.cursor = 0
        self.items_cursor = 0
        self.items_scroll = 0
        self.options = ["音量調整", "アイテム", "セーブ/ロード", "閉じる"]

        # セーブ/ロード
        self.save_slots = ["slot1", "slot2", "slot3"]
        self.save_cursor = 0
        self.saveload_mode = "save"        # "save" / "load"
        self.result_text = ""               # 右下の実行結果（固定位置）
        self.result_until_ms = 0           # いつまで出すか（自動消去）

        self.list_row_h = 36
        self.visible_rows = 9
        self.pad = 12
        # タイトル用
        self.did_load_success = False  # ロード成功したかどうかのフラグ
        self.modal_load_only: bool = False # ロード専用モーダルかどうか（タイトルから呼ぶとき True に）

        # 音量調整 
        # audio_cursor: 調整対象 0=BGM / 1=SE / 2=音声
        self.audio_cursor = 0
        # スライダーの1回あたり増減量（左/右キー）
        self.audio_step = 0.05  # 5%刻み（必要なら 0.02 などに調整OK）
        # 画面レイアウト用キャッシュ（描画関数で使う）
        self._audio_slider_rects = []  # type: list[pygame.Rect]

        # ★ タイトルなどから「音量調整だけ」のモーダルとして呼ぶ場合 True
        #   - このときは audio 画面から Esc/Enter/M でそのままメニューを閉じる
        self.modal_audio_only: bool = False

    def update(self, dt: float = 0.0) -> None:
        """
        メニューの毎フレーム更新処理用のダミー関数。
        現状は特に更新処理はないため、何もしません。
        将来アニメーションなどを追加する際はここに処理を書きます。
        """
        return
    
    # ---------- 効果音（存在チェック込み・安全再生） ----------
    def _se(self, key: str) -> None:
        """
        ・効果音キーが未登録でもクラッシュしない用
        """
        try:
            if self.sound and getattr(self.sound, "has_se", None) and self.sound.has_se(key):
                self.sound.play_se(key)
        except Exception:
            # SEまわりで例外が出てもゲーム進行は止めない
            pass

    # ---------- 入力 ----------
    def handle_event(self, event) -> Optional[str]:
        # ★ F11: フルスクリーン切り替え
        #   - メニュー表示中もフルスクリーンをオン/オフできるようにする。
        #   - ここでは main.py を import せず、pygame.display.toggle_fullscreen() を直接呼ぶ。
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
            try:
                pygame.display.toggle_fullscreen()
                # 念のため、現在の display Surface を取り直す（必要であれば main 側で参照）
                pygame.display.get_surface()
            except Exception as e:
                print(f"[MenuScene] fullscreen toggle failed: {e}")
            # F11 はメニューの操作（カーソル移動/決定など）には使わないので、そのまま終了。
            return None
        
        if event.type != pygame.KEYDOWN:
            return None

        if self.state == "main":
            if event.key == pygame.K_UP:
                self.cursor = (self.cursor - 1) % len(self.options)
                self._se("cursor")  # カーソル音
            elif event.key == pygame.K_DOWN:
                self.cursor = (self.cursor + 1) % len(self.options)
                self._se("cursor") # カーソル音

            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                chosen = self.options[self.cursor]
                if chosen == "閉じる":
                    # select を鳴らさず、main.py の "menu_close" だけ鳴らす
                    return "close"
                # それ以外は決定音を鳴らして遷移
                self._se("select")
                if   chosen == "音量調整":
                        # 音量調整画面へ
                        self.state = "audio"
                        # 現在値に応じてカーソル初期化（とりあえず0=BGMから）
                        self.audio_cursor = 0
                elif chosen == "アイテム":   self.state = "items"
                elif chosen == "セーブ/ロード":
                    self.state = "saveload"
                    self.save_cursor = 0
                    self.saveload_mode = "save"
                    self._clear_result()
                
            elif event.key in (pygame.K_ESCAPE, pygame.K_m): # キー入力でメニュー画面を閉じる場合
                return "close"

        elif self.state == "audio":
            # ------------------------
            # 音量調整 画面のキー操作
            # ↑↓ : 行（BGM/SE/音声）の選択
            # ←→ : 音量を増減（0.0～1.0）
            # Enter/Esc/M :
            #   - 通常時  : メインに戻る（保存して反映）
            #   - タイトルからのモーダル呼び出し時(self.modal_audio_only=True) :
            #              メニュー自体を閉じて "close" を返す
            # ------------------------
            if   event.key == pygame.K_UP:
                self.audio_cursor = (self.audio_cursor - 1) % 3
                self._se("cursor")
            elif event.key == pygame.K_DOWN:
                self.audio_cursor = (self.audio_cursor + 1) % 3
                self._se("cursor")
            elif event.key == pygame.K_LEFT:
                self._adjust_volume(-self.audio_step)
            elif event.key == pygame.K_RIGHT:
                self._adjust_volume(+self.audio_step)
            elif event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_m):
                # 設定を保存
                try:
                    if self.sound and hasattr(self.sound, "save_settings"):
                        self.sound.save_settings()
                except Exception:
                    pass
                self._se("cancel")

                if self.modal_audio_only:
                    # ★ タイトルからの音量専用モーダルの場合は、
                    #    メニュー自体を閉じるシグナルを返す
                    return "close"
                else:
                    # 通常はメインメニューへ戻る
                    self.state = "main"

        elif self.state == "items":
            inv_list = self._inventory_items()
            if not inv_list:
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_m):
                    self._se("cancel")
                    self.state = "main"
            else:
                if   event.key == pygame.K_UP:
                    # アイテムリストのカーソルを上へ移動 → カーソルSE
                    self._move_items_cursor(-1, len(inv_list))
                    self._se("cursor")
                elif event.key == pygame.K_DOWN:
                    # アイテムリストのカーソルを下へ移動 → カーソルSE
                    self._move_items_cursor(1, len(inv_list))
                    self._se("cursor")
                elif event.key in (pygame.K_ESCAPE, pygame.K_m):
                    # アイテム画面からメインに戻る → 戻るSE
                    self._se("cancel")
                    self.state = "main"

                # アイテム使用の挙動（使わなかった）
                # elif event.key in (pygame.K_RETURN, pygame.K_SPACE): 
                #     item_id, cnt = inv_list[self.items_cursor]
                #     meta = get_item_meta(item_id)
                #     if meta.get("usable", False) and cnt > 0: 
                #         # self._se("select") # アイテム使用の音
                #         return f"use:{item_id}"

        elif self.state == "saveload":
            if   event.key == pygame.K_UP:
                # セーブ/ロード一覧のカーソルを上へ → カーソルSE
                self.save_cursor = (self.save_cursor - 1) % len(self.save_slots); self._clear_result()
                self._se("cursor")
            elif event.key == pygame.K_DOWN:
                # セーブ/ロード一覧のカーソルを下へ → カーソルSE
                self.save_cursor = (self.save_cursor + 1) % len(self.save_slots); self._clear_result()
                self._se("cursor")

            elif event.key == pygame.K_LEFT:  # ★ モーダル時は ←→ 無効（ロード固定）
                if not self.modal_load_only:
                    # モードを保存側へ ← カーソルSE
                    self.saveload_mode = "save"; self._clear_result()
                    self._se("cursor")
            elif event.key == pygame.K_RIGHT: # ★ モーダル時は ←→ 無効（ロード固定）
                if not self.modal_load_only:
                    # モードを読込側へ → カーソルSE
                    self.saveload_mode = "load"; self._clear_result()
                    self._se("cursor")

            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                # ★セーブ/ロードの「実行時」は select を鳴らさず、成功/失敗の専用SEを後で鳴らす
                slot = self.save_slots[self.save_cursor]
                try:
                    if self.saveload_mode == "save":
                        # ★ モーダル時は save にならないはずだけど、念のため
                        if self.modal_load_only:
                            return None
                        ok = save_game(slot, meta_comment=None, notify=False)
                        # 成否で専用SE：成功→save_ok / 失敗→cancel（または save_fail に差し替え可）
                        self._se("save_ok" if ok else "cancel")  # ★セーブ音/失敗音
                        if ok:
                            self._show_result("保存しました：" + _label_for_slot(slot))
                        else:
                            # 現在地が no_save なら理由を明示
                            try:
                                cur_map_id = getattr(gs, "current_map_id", "")
                                if cur_map_id and isinstance(MAPS.get(cur_map_id), dict) and MAPS[cur_map_id].get("no_save"):
                                    self._show_result("ここではセーブできません。")
                                else:
                                    self._show_result("保存に失敗しました")
                            except Exception:
                                self._show_result("保存に失敗しました")
                    else:
                        ok = load_game(slot, notify=True, notify_ms=3500)
                        # 成否で専用SE：成功→load_ok / 失敗→cancel（または load_fail に差し替え可）
                        self._se("load_ok" if ok else "cancel") # ★ロード音/失敗音
                        self._show_result("ロードしました：" + _label_for_slot(slot) if ok else "ロードに失敗しました")
                        # ★ 保険：UIに確実に出す（ブリッジが切れていても次フレームで拾える）
                        if ok:
                            self.did_load_success = True # ★ 成功フラグON
                            return "close" # 成功時は閉じる
                except Exception as e:
                    self._show_result(f"失敗：{e}")
            elif event.key in (pygame.K_ESCAPE, pygame.K_m):
                # ★ロード専用モーダルの場合はメニューを閉じる（SEは main.py 側の "menu_close" のみ）
                if self.modal_load_only:
                    return "close"
                # ★通常のセーブ/ロード画面から“1段戻る” → 戻るSE
                self._se("cancel")
                self.state = "main"
                self._clear_result()             

        return None

    def _show_result(self, text: str, ms: int = 2400):
        self.result_text = text
        self.result_until_ms = pygame.time.get_ticks() + ms

    def _clear_result(self):
        self.result_text = ""
        self.result_until_ms = 0

    def _move_items_cursor(self, delta: int, n: int):
        self.items_cursor = (self.items_cursor + delta) % n
        top = self.items_scroll; bottom = self.items_scroll + self.visible_rows - 1
        if self.items_cursor < top: self.items_scroll = self.items_cursor
        elif self.items_cursor > bottom: self.items_scroll = self.items_cursor - (self.visible_rows - 1)

    def _inventory_items(self) -> List[Tuple[str, int]]:
        return [(k, v) for k, v in gs.inventory.items() if v > 0]

    # ---------- 描画 ----------
    def draw(self, surface: pygame.Surface, WIDTH: int, HEIGHT: int):
        # save_system 側が積んだ __toast_queue を UI へ流す
        toast_bridge.drain_queue()
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA); dim.fill(BG_TINT); surface.blit(dim, (0, 0))
        if   self.state == "main":     self._draw_main(surface, WIDTH, HEIGHT)
        elif self.state == "audio":    self._draw_audio(surface, WIDTH, HEIGHT)
        elif self.state == "items":    self._draw_items(surface, WIDTH, HEIGHT)
        elif self.state == "saveload": self._draw_saveload(surface, WIDTH, HEIGHT)

    def _panel_rect(self, WIDTH: int, HEIGHT: int) -> pygame.Rect:
        w = min(560, int(WIDTH * 0.84))
        h = min(380, int(HEIGHT * 0.80))
        rect = pygame.Rect(0, 0, w, h); rect.center = (WIDTH // 2, HEIGHT // 2); return rect

    def _draw_panel(self, s: pygame.Surface, rect: pygame.Rect, title: str):
        pygame.draw.rect(s, PANEL_BG, rect, border_radius=16)
        pygame.draw.rect(s, (255, 255, 255), rect, width=1, border_radius=16)
        draw_label(s, title, size=24, pos=(rect.centerx, rect.top + 12), anchor="midtop", bg_color=(0,0,0,0))

    def _draw_main(self, s: pygame.Surface, W: int, H: int):
        rect = self._panel_rect(W, H); self._draw_panel(s, rect, "メニュー")
        x = rect.left + self.pad; y = rect.top + 56
        for i, opt in enumerate(self.options):
            hl = (i == self.cursor); color = ACCENT if hl else (255, 255, 255)
            s.blit(render_text(opt, size=22, color=color, outline=True), (x, y)); y += 44
        hint_area = pygame.Rect(rect.left + self.pad, rect.bottom - 56, rect.width - self.pad*2, 44)
        _draw_wrapped_into_rect(s, "↑↓：選択　Enter：決定　Esc/M：閉じる", hint_area,
                                size=14, color=(230,230,230), line_gap=2, outline=True, align="center")

    # ------------------------------
    # 新規: 音量調整（BGM/SE/音声）
    # ------------------------------
    def _draw_audio(self, s: pygame.Surface, W: int, H: int):
        rect = self._panel_rect(W, H); self._draw_panel(s, rect, "音量調整")
        # 現在値（0.0～1.0）を取得。SoundManagerが未接続でも落ちないようにfallback
        bgm = getattr(self.sound, "bgm_volume", 0.6)
        se  = getattr(self.sound, "se_volume",  0.8)
        vce = getattr(self.sound, "voice_volume", 1.0)

        labels = [("BGM", bgm), ("SE", se), ("音声", vce)]
        x = rect.left + self.pad
        y = rect.top + 64
        line_h = 70

        # スライダー領域（枠内で左右に伸びるバー）
        slider_w = rect.width - (self.pad*2 + 180)  # ラベル幅ぶんを差し引く
        slider_h = 20
        self._audio_slider_rects = []

        for idx, (name, val) in enumerate(labels):
            # ラベル（選択中は強調色）
            hl = (idx == self.audio_cursor)
            color = ACCENT if hl else (255, 255, 255)
            s.blit(render_text(f"{name}", size=20, color=color, outline=True), (x, y))

            # スライダー背景
            bx = x + 110
            by = y + 8
            bar_rect = pygame.Rect(bx, by, slider_w, slider_h)
            pygame.draw.rect(s, (60, 60, 70), bar_rect, border_radius=6)
            # フィル（現在値％）
            fill_w = int(slider_w * max(0.0, min(1.0, float(val))))
            if fill_w > 0:
                pygame.draw.rect(s, (240, 210, 80), (bx, by, fill_w, slider_h), border_radius=6)
            # 数値（0～100%）
            pct = int(round(max(0.0, min(1.0, float(val))) * 100))
            s.blit(render_text(f"{pct:3d}%", size=18, color=(230,230,230), outline=True),
                   (bx + slider_w + 12, y - 2))

            self._audio_slider_rects.append(bar_rect)
            y += line_h

        hint = "↑↓：項目選択　←→：音量±5％　Enter/Esc/M：戻る（保存）"
        hint_area = pygame.Rect(rect.left + self.pad, rect.bottom - 56, rect.width - self.pad*2, 44)
        _draw_wrapped_into_rect(s, hint, hint_area, size=14, color=(230,230,230),
                                line_gap=2, outline=True, align="center")

    # 音量の加減を行い、即時反映＋軽い確認SE（SE選択時のみ）を鳴らす
    def _adjust_volume(self, delta: float) -> None:
        if not self.sound:
            return
        try:
            if self.audio_cursor == 0:
                # BGM
                self.sound.set_bgm_volume(getattr(self.sound, "bgm_volume", 0.6) + delta)
            elif self.audio_cursor == 1:
                # SE
                self.sound.set_se_volume(getattr(self.sound, "se_volume", 0.8) + delta)
                # 調整時は短い確認音（cursor）を軽く鳴らすと分かりやすい
                if getattr(self.sound, "has_se", None) and self.sound.has_se("cursor"):
                    self.sound.play_se("cursor")
            else:
                # 音声
                self.sound.set_voice_volume(getattr(self.sound, "voice_volume", 1.0) + delta)
            # 値を保存しておくと、クラッシュ時にも反映されやすい（確定は戻る時にも実施）
            if hasattr(self.sound, "save_settings"):
                self.sound.save_settings()
        except Exception:
            # 音周りの例外でゲームが止まらないように握りつぶす
            pass

    def _draw_items(self, s: pygame.Surface, W: int, H: int):
        rect = self._panel_rect(W, H); self._draw_panel(s, rect, "アイテム")
        inv = self._inventory_items()
        x = rect.left + self.pad; y = rect.top + 56
        if not inv:
            s.blit(render_text("所持アイテムはありません。", size=18, color=(200,200,200), outline=True), (x, y))
            draw_label(s, "Enter / Esc で戻る", size=14, pos=(rect.centerx, rect.bottom - self.pad),
                       anchor="midbottom", bg_color=(0,0,0,90))
            return
        start = self.items_scroll; end = min(start + self.visible_rows, len(inv))
        list_w = int(rect.width * 0.58)
        list_rect = pygame.Rect(rect.left + self.pad, rect.top + 52, list_w - self.pad, rect.height - 96)
        pygame.draw.rect(s, (18, 18, 26), list_rect, border_radius=8)
        cy = list_rect.top + 8
        for idx in range(start, end):
            item_id, cnt = inv[idx]; meta = get_item_meta(item_id)
            name = f"{display_name(item_id)} × {cnt}"; sel = (idx == self.items_cursor)
            row_rect = pygame.Rect(list_rect.left + 4, cy, list_rect.width - 8, self.list_row_h)
            if sel:
                pygame.draw.rect(s, (36, 36, 56), row_rect, border_radius=6)
                pygame.draw.rect(s, ACCENT, row_rect, width=1, border_radius=6)
            color = ACCENT if sel else (255,255,255)
            font_row = get_font(18); max_w = row_rect.width - 16
            name_draw = _ellipsize_to_width(name, font_row, max_w)
            s.blit(render_text(name_draw, size=18, color=color, outline=True), (row_rect.left + 8, row_rect.top + 6))
            cy += self.list_row_h + 2
        detail_rect = pygame.Rect(rect.left + list_w, rect.top + 52, rect.width - list_w - self.pad, rect.height - 96)
        pygame.draw.rect(s, (18, 18, 26), detail_rect, border_radius=8)
        sel_id, sel_cnt = inv[self.items_cursor]; sel_meta = get_item_meta(sel_id)
        dy = detail_rect.top + 10
        s.blit(render_text(display_name(sel_id), size=20, color=(255,255,255), outline=True),
               (detail_rect.left + 10, dy)); dy += 30
        s.blit(render_text(f"カテゴリ：{sel_meta['cat']}", size=16, color=(220,220,220), outline=True),
               (detail_rect.left + 10, dy)); dy += 24
        if sel_meta.get("desc"):
            inner = pygame.Rect(detail_rect.left, dy, detail_rect.width, detail_rect.bottom - dy)
            _draw_wrapped_into_rect(s, sel_meta["desc"], inner, size=16, color=(220,220,220),
                                    line_gap=4, outline=True, align="left", max_lines=6)
        hint_area = pygame.Rect(rect.left + self.pad, rect.bottom - 56, rect.width - self.pad*2, 44)
        hint = "↑↓：選択　Esc/M：戻る"
        if sel_meta.get("usable", False) and sel_cnt > 0: hint += "　Enter：使う"
        _draw_wrapped_into_rect(s, hint, hint_area, size=14, color=(230,230,230),
                                line_gap=2, outline=True, align="center")

    def _draw_saveload(self, s: pygame.Surface, W: int, H: int):
        if self.modal_load_only:
            self.saveload_mode = "load"  # ★描画/ロジックともに常に読込扱い
        rect = self._panel_rect(W, H)

        # ★モーダル時は見出しを「読込」に固定（通常は「セーブ／ロード」）
        title_text = "読込" if self.modal_load_only else "セーブ／ロード"
        self._draw_panel(s, rect, title_text)

        # --- モード表示（タブ＆←→ヒント）---
        if not self.modal_load_only:
            mode_l = render_text("保存", size=20,
                                color=(255,255,255) if self.saveload_mode=="save" else (180,180,180),
                                outline=True)
            mode_r = render_text("読込", size=20,
                                color=(255,255,255) if self.saveload_mode=="load" else (180,180,180),
                                outline=True)
            s.blit(mode_l, (rect.left + self.pad, rect.top + 52))
            s.blit(mode_r, (rect.left + self.pad + 80, rect.top + 52))

            _draw_wrapped_into_rect(
                s, "←→：保存/読込 切替",
                pygame.Rect(rect.left + self.pad + 160, rect.top + 50, 180, 28),
                size=14, color=(230,230,230), line_gap=0, outline=True
            )

        # 左：一覧
        list_w = int(rect.width * 0.52)
        list_rect = pygame.Rect(rect.left + self.pad, rect.top + 84, list_w - self.pad, rect.height - 120)
        pygame.draw.rect(s, (18, 18, 26), list_rect, border_radius=8)
        row_h = 58; cy = list_rect.top + 8
        for idx, slot in enumerate(self.save_slots):
            sel = (idx == self.save_cursor)
            row_rect = pygame.Rect(list_rect.left + 6, cy, list_rect.width - 12, row_h)
            if sel:
                pygame.draw.rect(s, (36, 36, 56), row_rect, border_radius=6)
                pygame.draw.rect(s, ACCENT, row_rect, width=1, border_radius=6)
            color = ACCENT if sel else (255,255,255)
            s.blit(render_text(_label_for_slot(slot), size=18, color=color, outline=True),
                   (row_rect.left + 10, row_rect.top + 6))
            sub_rect = pygame.Rect(row_rect.left + 12, row_rect.top + 28, row_rect.width - 24, 24)
            info = _peek_save(slot)
            if info and not info.get("broken"):
                sub = f"{info['map_id']}／{info['timestamp']}／{info['playtime']}"
            elif info and info.get("broken"):
                sub = "ファイルを読み取れません"
            else:
                sub = "（空）"
            font14 = get_font(14)
            draw_text = _ellipsize_to_width(sub, font14, sub_rect.width)
            s.blit(render_text(draw_text, size=14, color=(210,210,210), outline=True),
                   (sub_rect.left, sub_rect.top))
            cy += row_h

        # 右：詳細
        detail_rect = pygame.Rect(rect.left + list_w, rect.top + 84, rect.width - list_w - self.pad, rect.height - 120)
        pygame.draw.rect(s, (18, 18, 26), detail_rect, border_radius=8)

        slot = self.save_slots[self.save_cursor]
        info = _peek_save(slot)

        y = detail_rect.top + 10
        # 見出し
        hdr = render_text(f"{_label_for_slot(slot)}", size=18, color=(255,255,255), outline=True)
        s.blit(hdr, (detail_rect.left + 20, y)); y += hdr.get_height() + 8

        if info and not info.get("broken"):
            lines = [
                f"場所: {info['map_id']}",
                f"時刻: {info['timestamp']}",
                f"時間: {info['playtime']}",
            ]
            for ln in lines:
                y = _draw_wrapped_into_rect(s, ln, pygame.Rect(detail_rect.left + 10, y, detail_rect.width - 15, 200),
                                            size=16, color=(220,220,220), line_gap=4, outline=True, align="left")
        elif info and info.get("broken"):
            _draw_wrapped_into_rect(s, "このスロットのファイルは読み取れません。",
                                    pygame.Rect(detail_rect.left + 10, y, detail_rect.width - 20, 60),
                                    size=16, color=(255,200,200), line_gap=4, outline=True, align="left")
        else:
            _draw_wrapped_into_rect(s, "このスロットにはまだ保存がありません。",
                                    pygame.Rect(detail_rect.left + 10, y, detail_rect.width - 20, 60),
                                    size=16, color=(220,220,220), line_gap=4, outline=True, align="left")

        # 固定フッター領域（位置を“常に一定”に）
        hint_rect = pygame.Rect(detail_rect.left + 10, detail_rect.bottom - 80, detail_rect.width - 20, 38)
        msg_rect  = pygame.Rect(detail_rect.left + 10, hint_rect.top - 28,    detail_rect.width - 20, 24)

        # 実行結果（期限切れなら出さない）
        now = pygame.time.get_ticks()
        if self.result_text and now < self.result_until_ms:
            _draw_wrapped_into_rect(s, self.result_text, msg_rect, size=14, color=(255,255,180),
                                    line_gap=2, outline=True, align="left")
        elif self.result_text and now >= self.result_until_ms:
            self._clear_result()

        hint_text = (
            "↑↓：スロット選択　Enter：読込　Esc：戻る"
            if self.modal_load_only
            else "↑↓：スロット選択　←→：保存/読込 切替　Enter：実行　Esc/M：戻る"
        )
        _draw_wrapped_into_rect(
            s, hint_text,
            hint_rect, size=14, color=(230,230,230),
            line_gap=2, outline=True, align="left"
        )
