# core/video_player.py
# -*- coding: utf-8 -*-
"""
OpenCV + pygame で動画を再生する共通モジュール。
- 映像: OpenCV (cv2.VideoCapture) でフレームを取り出し、pygame.Surface 化して描画
- 音声: pygame.mixer.Sound で WAV を並行再生（任意）
- フレーム間隔は「再生開始からの経過時間 × fps」による“壁時計基準”でスキップ追従
- 画面比率はレターボックスで保持
- Enter/Space/左クリック/ESC でスキップ（ESC は確認ダイアログは上位シーンで）
"""

from __future__ import annotations
from pathlib import Path
import io
import time
import pygame
import cv2
import numpy as np

from core.config import WIDTH, HEIGHT
from core.transitions import fade_in, fade_out
from core.sound_manager import fernet  # ← 復号に使う（キーの二重管理を避ける）

# --- ユーティリティ: フルスクリーンの黒下地を描く（レターボックス用） ---
def _fill_black(surface: pygame.Surface):
    surface.fill((0, 0, 0))

def _make_letterbox_rect(video_w: int, video_h: int) -> pygame.Rect:
    """画面(WIDTH, HEIGHT)に対し、動画のアスペクトを保って収める矩形を返す。"""
    if video_w <= 0 or video_h <= 0:
        return pygame.Rect(0, 0, WIDTH, HEIGHT)
    scale = min(WIDTH / video_w, HEIGHT / video_h)
    w = int(video_w * scale)
    h = int(video_h * scale)
    x = (WIDTH - w) // 2
    y = (HEIGHT - h) // 2
    return pygame.Rect(x, y, w, h)

def _frame_to_surface(frame_bgr: np.ndarray, target_size: tuple[int, int]) -> pygame.Surface:
    """OpenCV(BGR) → RGB → pygame.Surface（ターゲットサイズにリサイズ）"""
    if frame_bgr is None:
        return None
    # BGR → RGB
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    # リサイズ（高品質）
    if target_size is not None and (frame_rgb.shape[1], frame_rgb.shape[0]) != target_size:
        frame_rgb = cv2.resize(frame_rgb, target_size, interpolation=cv2.INTER_AREA)
    # 連続メモリに
    frame_rgb = np.ascontiguousarray(frame_rgb)
    surf = pygame.image.frombuffer(frame_rgb.tobytes(), target_size, "RGB")
    return surf

def play_video(
    screen: pygame.Surface,
    base_dir: Path,
    video_rel_path: str,
    audio_rel_path: str | None = None,
    *,
    allow_skip: bool = True,
    fade_ms: int = 600,
    bg_color=(0, 0, 0),
    playback_speed: float = 1.0,        # ←現実的な既定（少しゆっくり）
    override_fps: float | None = 24.0,   # ←CFR固定推奨（素材がVFRでも安定）
    sound_manager=None,                  # ← SoundManager を受け取り
    se_cues: list[tuple[float, str]] | None = None, # ムービーと同期して鳴らすワンショットSE（秒指定）
) -> bool:
    """True=最後まで再生 / False=途中スキップ"""

    # ① まずは SoundManager 経由で足音・SE・BGM・環境音を静音
    #    （ここまではこれまでと同じ処理）
    try:
        sm = sound_manager
        if sm is None:
            from core import sound_manager as _global_sm
            sm = getattr(_global_sm, "sound_manager", None) or _global_sm
        if sm:
            # 足音・環境音・BGM・SE をまとめてフェードアウト
            sm.hush_effects_for_cutscene(fade_ms=160)
    except Exception:
        pass

    # ② 念のため pygame.mixer 全体も一度完全停止する（最終手段）
    #    - これで SoundManager を経由していないチャンネルも含めて
    #      すべての再生をストップさせる
    try:
        if pygame.mixer.get_init():
            # すべてのチャンネルで鳴っている音を止める
            pygame.mixer.stop()
            # BGM（pygame.mixer.music）も確実に止める
            pygame.mixer.music.stop()
    except Exception:
        # ここで失敗してもゲームを止めない
        pass

    # --- 0) パス確認＆ログ ---
    video_path = base_dir / video_rel_path
    print(f"[VIDEO] try open: {video_path}")
    if not video_path.exists():
        print(f"[VIDEO][ERR] file not found: {video_path}")
        return False
    
    # 既定の“環境音マップ”：audio_path が渡されていない時だけ自動適用 ---
    # ムービーに環境音を付けたいときはここに1行足すだけで音を紐づけできます👍
    if audio_rel_path is None:
        default_audio_map = {
            # fogムービー専用の環境音（暗号化/非暗号化いずれもOK拡張子は合わせて💦）
            "assets/movies/fog_block_intro.mp4": "assets/sounds/se/死後の世界.mp3",
            "assets/movies/river_warning.mp4":"assets/sounds/se/河原.mp3.enc",
            "assets/movies/trunk_intro.mp4":"assets/sounds/se/河原.mp3.enc",
             # ★追跡者導入ムービー：デフォルトで警告系の効果音を付与
            "assets/movies/chaser_intro.mp4":"assets/sounds/se/狂気.mp3.enc",
            "assets/movies/chaser_caught.mp4":"assets/sounds/se/狂気.mp3.enc",
            "doctor_burst_out.mp4":"映写機.mp3.enc",
        }
        audio_rel_path = default_audio_map.get(str(video_rel_path))

    # --- 1) OpenCVで動画を開く ---
    try:
        cap = cv2.VideoCapture(str(video_path))
    except Exception as e:
        print(f"[VIDEO][ERR] cv2.VideoCapture failed: {e}")
        return False
    if not cap or not cap.isOpened():
        print(f"[VIDEO][ERR] cannot open video: {video_path}")
        return False

    # メタ情報
    vid_w  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)  or 0)
    vid_h  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps_src = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if fps_src <= 1e-3:
        fps_src = 24.0  # フォールバック

    # 目標FPS = (override があればそれ) × 再生速度
    fps_base   = override_fps or fps_src
    fps_target = max(5.0, min(120.0, fps_base * max(0.1, playback_speed)))
    frame_period = 1.0 / fps_target
    print(f"[VIDEO] src_fps={fps_src:.3f}, target_fps={fps_target:.3f}, speed={playback_speed}x")

    dst_rect = _make_letterbox_rect(vid_w, vid_h)

    # --- 2) 音声（任意） ---
    sound = None
    channel = None
    audio_started = False
    if audio_rel_path:
        # --- 2-1) パス解決（拡張子省略時のオート補完に対応） -------------------
        cand = []
        p = base_dir / audio_rel_path
        if p.suffix:  # すでに拡張子あり
            cand.append(p)
        else:
            # よく使う順で探索（mp3→wav→ogg→mp3.enc）
            for suf in (".mp3", ".wav", ".ogg", ".mp3.enc"):
                cand.append(p.with_suffix(suf))

        real_path = None
        for cp in cand:
            if cp.exists():
                real_path = cp
                break

        # --- 2-2) ロード処理（暗号化なら復号、通常ならそのまま） --------------
        try:
            if real_path is None:
                raise FileNotFoundError(f"no candidate found for {audio_rel_path!r}")
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)

            if str(real_path).endswith(".enc"):
                # 暗号化データを復号してメモリから読み込む
                with open(real_path, "rb") as f:
                    encrypted = f.read()
                decrypted = fernet.decrypt(encrypted)
                sound = pygame.mixer.Sound(io.BytesIO(decrypted))
            else:
                # 通常ファイル（mp3/wav/ogg）をそのまま読み込み
                sound = pygame.mixer.Sound(str(real_path))
        except Exception as e:
            print(f"[VIDEO] Audio load failed ({audio_rel_path} -> {real_path}): {e}")
            print("[VIDEO] HINT: If MP3 codec is not available on your SDL_mixer, try WAV/OGG instead.")
            sound = None

    # --- 3) フェードイン（黒背景で下地を描画） ---
    def draw_under():
        _fill_black(screen)
        pygame.display.flip()
    fade_in(screen, fade_ms, draw_under=draw_under)

    # ムービー開始前に、足音など既存SEを静かに消す
    try:
        if sound_manager is not None and hasattr(sound_manager, "stop_all_se"):
            sound_manager.stop_all_se(fade_ms=0)  # 0～200ms程度
    except Exception as e:
        print(f"[VIDEO] stop_all_se failed: {e}")

    # --- 4) 再生ループ（“時刻が来たら1枚だけ読む”） ---
    start_time = time.perf_counter()

    # 最初のフレームを読む（失敗なら終了）
    ret, frame = cap.read()
    if not ret:
        cap.release()
        if channel: channel.stop()
        fade_out(screen, fade_ms, draw_under=draw_under)
        return True

    current_surf = _frame_to_surface(frame, (dst_rect.width, dst_rect.height))
    next_frame_time = start_time  # 次フレーム切り替え時刻（現在＝即切替OK）
    finished = True

    fired = set()  # どのキューを鳴らしたかのインデックス集合

    while True:
        # 1) 入力（スキップ）
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                cap.release(); pygame.quit(); raise SystemExit
            if allow_skip:
                if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                    finished = False
                    cap.release()
                    if channel: channel.stop()
                    fade_out(screen, fade_ms, draw_under=draw_under)
                    return finished
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    finished = False
                    cap.release()
                    if channel: channel.stop()
                    fade_out(screen, fade_ms, draw_under=draw_under)
                    return finished

        # 2) 音声（最初に一度だけ）
        if sound and not audio_started:
            if sound_manager is not None:
                # --- SoundManager の voice チャンネルで再生 ---
                #   ・voice_volume の現在値を適用（実行中に set_voice_volume しても効く）
                sound.set_volume(getattr(sound_manager, "voice_volume", 1.0))
                sound_manager.voice_channel.stop()  # 念のため前の音を止める
                sound_manager.voice_channel.play(sound)
                channel = sound_manager.voice_channel   # Skip時のstop対象にする
            else:
                # 従来：デフォルトチャンネルで再生
                channel = sound.play()
            audio_started = True

        # 3) 時刻を取得（←★必ずループの先頭側で毎回セット）
        now = time.perf_counter()
        elapsed = now - start_time

        # 3.5) SEキューの処理（指定秒を過ぎたら一度だけ鳴らす）
        if se_cues and sound_manager is not None and hasattr(sound_manager, "play_se"):
            try:
                for i, (t_sec, se_key) in enumerate(se_cues):
                    if i in fired:
                        continue
                    if elapsed >= float(t_sec):
                        if hasattr(sound_manager, "has_se"):
                            if sound_manager.has_se(se_key):
                                sound_manager.play_se(se_key)
                                print(f"[VIDEO] se_cue fired: t={elapsed:.3f}s key={se_key}")
                        else:
                            sound_manager.play_se(se_key)
                            print(f"[VIDEO] se_cue fired: t={elapsed:.3f}s key={se_key}")
                        fired.add(i)
            except Exception as e:
                print(f"[VIDEO] se_cues failed: {e}")

        # 4) 時刻が来たら次フレームを“1枚だけ”読む
        if now >= next_frame_time:
            ret, frame = cap.read()
            if not ret:
                break  # 終端
            current_surf = _frame_to_surface(frame, (dst_rect.width, dst_rect.height))
            next_frame_time += frame_period

        # 5) 描画（時刻前なら同じフレームを保つ）
        _fill_black(screen)
        if current_surf:
            screen.blit(current_surf, dst_rect.topleft)
        pygame.display.flip()

        # 6) CPU負荷を軽く抑える（最大10msだけ眠る）
        sleep_sec = max(0.0, min(0.010, next_frame_time - now))
        if sleep_sec > 0:
            time.sleep(sleep_sec)

    # --- 5) 正常終了 → フェードアウト ---
    cap.release()
    if channel: channel.stop()
    fade_out(screen, fade_ms, draw_under=draw_under)
    return True



