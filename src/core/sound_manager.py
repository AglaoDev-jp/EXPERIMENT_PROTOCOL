# core/sound_manager.py

import pygame
from pathlib import Path
import json
from cryptography.fernet import Fernet
import io

# ==========================================
# サウンド管理クラス
# ==========================================

# --- Fernet暗号化キー（secret.keyの中身を貼り付けてください） ---
FERNET_KEY = b"kokoga_secret_key_dayo"
fernet = Fernet(FERNET_KEY)

class SoundManager:
    
    # 音量のデフォルト値
    DEFAULTS = {
        "bgm_volume": 0.6,    # BGMはやや控えめ
        "se_volume": 0.8,     # 効果音は大きめ
        "voice_volume": 1.0,  # ボイス（音声）は最大
    }

    def __init__(self, base_path, use_encrypted=True):
        """
        サウンドマネージャの初期化
        :param base_path: "assets/sounds"を想定したPath
        :param use_encrypted: Trueなら暗号化ファイル(.mp3.enc)優先でロード
        """
        # サウンド関連のパス設定
        self.bgm_path = base_path / "bgm"
        self.se_path = base_path / "se"
        self.voice_path = base_path / "voice"
        self.settings_path = base_path.parent / "sound_settings.json"  # 設定ファイルの保存先 

        # サウンドチャンネル
        self.voice_channel = pygame.mixer.Channel(3)  # 独立したボイスチャンネルを確保
        self.current_bgm = None  # 再生中BGMのフルパス（重複再生防止用）

        # 音量パラメータ（初期値をセット）
        self.bgm_volume = self.DEFAULTS["bgm_volume"]
        self.se_volume = self.DEFAULTS["se_volume"]
        self.voice_volume = self.DEFAULTS["voice_volume"]

        # 効果音(SE)の辞書
        self.se = {}

        self.use_encrypted = use_encrypted

        # 効果音の読み込み（暗号化ファイル優先で復号→Soundオブジェクト化）
        self._load_se()

        # 音量設定ファイル（sound_settings.json）の読み込み（あれば上書き）
        self.load_settings()

        # 読み込んだ音量設定をすべてのサウンドに反映
        self.apply_volume()

    def _load_se(self):
        """効果音ファイルを辞書として読み込む（暗号化ファイル優先）"""
        files = {
            "cursor": "決定ボタンを押す13.mp3",      # カーソル移動
            "select": "決定ボタンを押す16.mp3",      # 決定・選択
            "cancel": "警告音2.mp3",         # キャンセル
            # map
            # --- ★足音（環境別）★ ---
            "step_forest": "砂利の上を歩く.mp3", # 森
            "step_lab":    "革靴で歩く.mp3",    # 研究所
            "step_tunnel": "アスファルトの上を歩く1.mp3", # 地下道
            # ------------------------
            "get_item":"決定ボタンを押す38.mp3", # アイテム取得
            "kazamidori_y":"キャンセル9.mp3",
            "kazamidori_n":"キャンセル1.mp3",
            # menu
            "menu_open":"メニューを開く2.mp3",
            "menu_close":"メニューを開く3.mp3",
            # セーブ/ロード 成功専用SE
            "save_ok": "メニューを開く4.mp3",
            "load_ok": "メニューを開く5.mp3",
            # intro_event
            "growl_hint":"ゴブリンの鳴き声3.mp3",

            # 霧シーン※使えてない
            "fog_intro": "死後の世界.mp3",
            "fog_intro": "魔法陣を展開.mp3",
            # 河原シーン
            "tree_crash": "木が倒れる.mp3",  
            "river_loop": "河原.mp3",
            "tree_chop": "打撃5.mp3",
            # ドア
            "door_unlock": "鉄の扉を開ける.mp3",
            # スイッチ系
            "switch_ok":      "決定ボタンを押す52.mp3", # 正解
            "switch_ng":      "ビープ音4.mp3",          # 誤答
            "switch_solved":  "巨大シャッターが開く.mp3",  # 全問正解で封鎖が外れる
        }
        self.se = {}
        for key, fname in files.items():
            # 暗号化ファイル優先
            enc_path = self.se_path / (Path(fname).stem + ".mp3.enc")
            try:
                if self.use_encrypted and enc_path.exists():
                    # --- 暗号化SEファイルを復号しSoundオブジェクト化 ---
                    with open(enc_path, "rb") as f:
                        encrypted_data = f.read()
                    decrypted_data = fernet.decrypt(encrypted_data)
                    sound = pygame.mixer.Sound(io.BytesIO(decrypted_data))
                    sound.set_volume(self.se_volume)
                    self.se[key] = sound
                else:
                    # --- 通常ファイル（暗号化されていないSE） ---
                    path = self.se_path / fname
                    sound = pygame.mixer.Sound(str(path))
                    sound.set_volume(self.se_volume)
                    self.se[key] = sound
            except Exception as e:
                print(f"[SoundManager] 効果音の読み込み失敗: {key}: {fname} ({e})")

    def apply_volume(self):
        """
        現在の音量パラメータをBGM/SE/Voiceに反映
        """
        pygame.mixer.music.set_volume(self.bgm_volume)
        for sound in self.se.values():
            sound.set_volume(self.se_volume)
        self.voice_channel.set_volume(self.voice_volume)
    # BGMの音量設定
    def set_bgm_volume(self, vol):
        self.bgm_volume = max(0.0, min(1.0, vol))
        pygame.mixer.music.set_volume(self.bgm_volume)
    # SEの音量設定
    def set_se_volume(self, vol):
        self.se_volume = max(0.0, min(1.0, vol))
        for sound in self.se.values():
            sound.set_volume(self.se_volume)
    # Voiceの音量設定
    def set_voice_volume(self, vol):
        self.voice_volume = max(0.0, min(1.0, vol))
        self.voice_channel.set_volume(self.voice_volume)

    def save_settings(self):
        """
        現在の音量設定をJSONファイルに保存
        """
        data = {
            "bgm_volume": self.bgm_volume,
            "se_volume": self.se_volume,
            "voice_volume": self.voice_volume,
        }
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"[SoundManager] 音量設定の保存に失敗: {e}")

    def load_settings(self):
        """
        JSONから音量設定を読み込み（なければデフォルト値のまま）
        """
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.bgm_volume = float(data.get("bgm_volume", self.DEFAULTS["bgm_volume"]))
                self.se_volume = float(data.get("se_volume", self.DEFAULTS["se_volume"]))
                self.voice_volume = float(data.get("voice_volume", self.DEFAULTS["voice_volume"]))
        except Exception:
            # ファイルがなければデフォルト値のまま
            pass

    # ----------------------------
    # BGM（音楽）再生・停止（暗号化ファイル対応）
    # ----------------------------
    def play_bgm(self, filename, loop=True, encrypted=None):
        """
        指定BGMファイルの再生。暗号化ファイル(.mp3.enc)なら復号して再生
        :param filename: .mp3 または .mp3.enc
        :param loop: ループ再生するか
        :param encrypted: Noneなら自動判定。Trueなら強制的に暗号化ファイルとして扱う
        """
        # 暗号化判定
        is_encrypted = encrypted if encrypted is not None else str(filename).endswith(".enc")
        full_path = self.bgm_path / filename

        # ★★ 修正ポイント ★★
        # 以前は「同じパスなら何もしない」最適化をしていたが、
        # 他所で pygame.mixer.music.stop() された場合に
        # current_bgm だけ残ってしまい、BGMが鳴り直らなくなる。
        # そのため、この早期 return を削除して、
        # 毎回きちんと load/play するようにする。
        # if self.current_bgm == str(full_path):
        #     return

        try:
            pygame.mixer.music.stop()
            if is_encrypted:
                # --- 暗号化BGM ---
                with open(full_path, "rb") as f:
                    encrypted_data = f.read()
                decrypted_data = fernet.decrypt(encrypted_data)
                mp3_file = io.BytesIO(decrypted_data)
                pygame.mixer.music.load(mp3_file)
            else:
                # --- 通常BGM ---
                pygame.mixer.music.load(str(full_path))
            pygame.mixer.music.set_volume(self.bgm_volume)
            pygame.mixer.music.play(-1 if loop else 0)
            self.current_bgm = str(full_path)
        except Exception as e:
            print(f"[SoundManager] BGM再生失敗: {filename} ({e})")
            self.current_bgm = None

    def stop_bgm(self):
        """BGMを停止"""
        pygame.mixer.music.stop()
        self.current_bgm = None

    def fadeout_bgm(self, ms=1000):
        """BGMをフェードアウトで停止"""
        pygame.mixer.music.fadeout(ms)
        self.current_bgm = None

    # ----------------------------
    # 効果音(SE)再生
    # ----------------------------
    def play_se(self, key):
        """
        効果音を再生（起動時に復号済みのSoundオブジェクトから）
        """
        if key in self.se:
            self.se[key].play()

    #----- 本プロジェクトでの☆新規追加☆ ------------
        else:
            # デバッグしやすいように警告を出す
            print(f"[SoundManager][WARN] SE key not loaded: {key!r}")

    def has_se(self, key: str) -> bool:
        """
        指定キーのSEがロード済みかを返す（デバッグ/事前確認用）
        """
        return key in self.se

    # ---------------------------------------------
    # ★追加: 効果音(SE)ループ専用チャンネル管理
    # ---------------------------------------------
    def _ensure_channel(self, name: str, channel_index: int | None = None) -> pygame.mixer.Channel:
        """
        任意の“論理名”に1つだけ pygame.mixer.Channel を割り当ててキャッシュする。
        - 明示 index が無い場合、**名前ごとに固有のチャンネル番号**を自動採番して衝突回避。
        """
        if not hasattr(self, "_named_channels"):
            self._named_channels = {}
            self._channel_indices = {}
        if name in self._named_channels:
            return self._named_channels[name]
        # 固定で使いたいものはここで割当（例: voice=3 は別で確保済み）
        if channel_index is not None:
            idx = int(channel_index)
        else:
            # 6番以降を順に使う（ambience/footstep/…の順で 6,7,8,...）
            base = 6
            idx = base + len(self._named_channels)
        # Mixerに十分なチャンネル数を確保
        try:
            cur = pygame.mixer.get_num_channels()
            if idx >= cur:
                pygame.mixer.set_num_channels(idx + 1)
        except Exception:
            pass
        ch = pygame.mixer.Channel(idx)
        self._named_channels[name] = ch
        self._channel_indices[name] = idx
        return ch

    def get_se(self, key: str) -> pygame.mixer.Sound | None:
        """SE辞書から Sound を取得（存在しなければ None）。"""
        try:
            return self.se.get(key)
        except Exception:
            return None

    def play_loop(self, *, name: str, se_key: str, fade_ms: int = 40) -> None:
        """
        指定SEを“name”チャンネルでループ再生。
        - すでに同じse_keyが鳴っていれば何もしない（多重起動を防ぐ）
        - 別のse_keyが鳴っていればフェードアウト→差し替え
        """
        if not hasattr(self, "_looping_now"):
            self._looping_now = {}   # name -> se_key
        snd = self.get_se(se_key)
        if snd is None:
            # ロードされていない場合は黙って何もしない
            return
        cur = self._looping_now.get(name)
        ch = self._ensure_channel(name)
        # 念のためループ系の音量をチャンネルにも反映
        try:
            ch.set_volume(self.se_volume)
        except Exception:
            pass
        if cur == se_key and ch.get_busy():
            # 同じ音を既にループ中：再生し直さない
            return
        # 異なる音が鳴っていれば切り替え
        if ch.get_busy():
            ch.fadeout(max(0, fade_ms))
        ch.play(snd, loops=-1, fade_ms=max(0, fade_ms))
        self._looping_now[name] = se_key

    def stop_loop(self, *, name: str, fade_ms: int = 60) -> None:
        """“name”チャンネルのループを停止（フェード付き）。"""
        ch = self._ensure_channel(name)
        if ch.get_busy():
            ch.fadeout(max(0, fade_ms))
        if hasattr(self, "_looping_now") and name in self._looping_now:
            del self._looping_now[name]

    def stop_all_se(self, fade_ms: int = 120):
        """
        すでに再生中の効果音(SE)をまとめて止めます。
        - 同じ Sound オブジェクトの stop()/fadeout() は、その音の再生を全て止められるため、
          足音の残響など“鳴りっぱなし”を一括で解消できます。
        - voice_channel（ムービー音声用）は止めません。
        """
        for key, snd in self.se.items():
            try:
                if fade_ms > 0:
                    snd.fadeout(int(fade_ms))
                else:
                    snd.stop()
            except Exception:
                # 読み込み失敗などで None の場合に備えて握りつぶし
                pass

    # --------------------------------------------
    # カットシーン等に入る直前に「音まわり」を静音するユーティリティ
    # ・足音ループ（"footstep" チャネル）
    # ・環境音ループ（"ambience" チャネル）
    # ・単発SE
    # ・BGM（追跡者BGMふくむ全BGM）
    # --------------------------------------------
    def hush_effects_for_cutscene(self, fade_ms: int = 120) -> None:
        """
        動画・イベントなどのブロッキング演出に入る直前に呼び出してください。

        ・足音などのループSEをフェードアウト
        ・環境音ループSEをフェードアウト
        ・単発SEをまとめてフェードアウト
        ・現在再生中のBGM（通常BGM／追跡者BGMを含む）もフェードアウト

        これにより、「カットシーン中に足音や環境音・BGMが鳴りっぱなし」
        という状態を確実に防ぎます。
        """

        # --- 足音ループ（プレイヤーの歩行音ループ） -------------------------
        try:
            # メインループ側で name="footstep" として管理しているループSE
            self.stop_loop(name="footstep", fade_ms=fade_ms)
        except Exception:
            # チャネル未初期化などで落ちないように握りつぶし
            pass

        # --- 環境音ループ（川の音など） ------------------------------------
        try:
            # _apply_map_ambience() で name="ambience" として再生しているループSE
            self.stop_loop(name="ambience", fade_ms=fade_ms)
        except Exception:
            pass

        # --- 単発SE（足音ワンショット等も含む） ----------------------------
        try:
            # すでに鳴っている効果音をまとめてフェードアウト
            self.stop_all_se(fade_ms=fade_ms)
        except Exception:
            pass

        # --- BGM（追跡者BGMを含むすべて） ----------------------------------
        try:
            # ここで一度すべてのBGMをフェードアウト
            # ・通常BGM
            # ・追跡者専用BGM「うしろからなにかが近づいてくる.mp3(.enc)」
            # どちらもまとめて静かに落とします。
            self.fadeout_bgm(ms=fade_ms)
        except Exception:
            pass

    # ----------------------------- ここまで☆新規追加☆

    # ----------------------------
    # ボイス（音声）再生・停止（暗号化ファイル対応）
    # ----------------------------
    def play_voice(self, filename, encrypted=None):
        """
        ボイス音声（mp3/wav/mp3.enc）を再生。暗号化ファイル(.mp3.enc)なら復号して再生
        :param filename: .mp3 / .wav / .mp3.enc
        :param encrypted: Noneなら自動判定。Trueなら強制的に暗号化ファイルとして扱う
        """
        self.stop_voice()
        is_encrypted = encrypted if encrypted is not None else str(filename).endswith(".enc")
        path = self.voice_path / filename
        try:
            if is_encrypted:
                with open(path, "rb") as f:
                    encrypted_data = f.read()
                decrypted_data = fernet.decrypt(encrypted_data)
                sound = pygame.mixer.Sound(io.BytesIO(decrypted_data))
            else:
                sound = pygame.mixer.Sound(str(path))
            sound.set_volume(self.voice_volume)
            self.voice_channel.play(sound)
        except Exception as e:
            print(f"[SoundManager] ボイス再生失敗: {filename} ({e})")

    def stop_voice(self):
        """ボイスチャンネルの音声を停止"""
        self.voice_channel.stop()

    # ★ここから新規追加 ----------------------------
    def is_voice_playing(self) -> bool:
        """
        現在、ボイス用チャンネルで音声が再生中かどうかを返します。

        オートモードで
        「ボイスが鳴り終わるまでは次の行に進まない」
        という判定に使うことを想定しています。
        """
        try:
            # get_busy() が True のとき、このチャンネルで何か再生中
            return self.voice_channel.get_busy()
        except Exception:
            # 万が一 voice_channel が初期化できていなくても、
            # ゲームが止まらないように False を返しておく
            return False
    # ★ここまで新規追加 ----------------------------

# 使い方例：
# sound_manager.play_bgm("test.mp3.enc")   # 暗号化BGM
# sound_manager.play_bgm("test.mp3")       # 通常BGM
# sound_manager.play_se("cursor")          # 効果音（SEはファイル形式自動判定）
# sound_manager.play_voice("voice1.mp3.enc") # 暗号化ボイス
# sound_manager.play_voice("voice1.mp3")     # 通常ボイス

# ==========================================
# サウンドマネージャの初期化例
# ==========================================
# このファイルはモジュールとして使う前提なので、
# ゲーム本体(main.pyなどメインスクリプト)で以下のように初期化してください。
# from sound_manager import SoundManager
# sound_manager = SoundManager(Path(__file__).resolve().parent / "assets" / "sounds")
# 必ず**Pygameの初期化後（pygame.mixer.init()後）**にSoundManagerを作ってください。

# BGM（音楽）は容量が大きいため、再生時にファイル名で都度ロードして使用しています。
# SE（効果音）は短く軽量なため、事前にSoundオブジェクトとして事前にメモリに読み込んでおくことで、
# 即時再生・レスポンス向上を図っています。
# ※この方式はPygameに限らず、一般的なゲーム開発でもよく用いられる手法のようです。

