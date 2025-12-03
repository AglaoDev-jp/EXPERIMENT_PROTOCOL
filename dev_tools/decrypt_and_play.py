"""
暗号化MP3ファイル（.mp3.enc）をFernetで複合し、Pygameでそのまま再生するスクリプト
おためしで再生して確認ができます。
- 複合データは一時的にメモリ上で扱うためファイルは残しません
- Pygameのmixer.musicを利用して再生します

"""

import pygame
from pathlib import Path
from cryptography.fernet import Fernet
import io

# ========= 設定 =========
# 複合・再生したい暗号化ファイルのパス
ENCRYPTED_FILE = Path("")  
# 暗号化キーのファイル
KEY_FILE = Path("")


def load_key(key_file):
    """
    暗号化キー(secret.key)を読み込む
    """
    if not key_file.exists():
        raise FileNotFoundError(f"暗号化キーが見つかりません: {key_file}")
    with open(key_file, "rb") as f:
        return f.read()


def decrypt_file(enc_path, fernet):
    """
    暗号化ファイル(.enc)をFernetで復号してバイトデータとして返す
    """
    with open(enc_path, "rb") as f:
        encrypted_data = f.read()
    decrypted_data = fernet.decrypt(encrypted_data)
    return decrypted_data


def play_mp3_from_bytes(mp3_bytes):
    """
    バイトデータのMP3をPygameで再生
    """
    # Pygame初期化
    pygame.mixer.init()
    # バイトデータをBytesIOに格納（擬似ファイル化）
    mp3_file = io.BytesIO(mp3_bytes)
    # Pygame 2.x以降: mixer.music.loadでファイルオブジェクトも読める
    pygame.mixer.music.load(mp3_file)
    pygame.mixer.music.play()
    print("再生開始（Enterキーで終了）")
    input()
    pygame.mixer.music.stop()
    pygame.mixer.quit()


def main():
    # キーをロード
    key = load_key(KEY_FILE)
    fernet = Fernet(key)
    # 複合化
    mp3_bytes = decrypt_file(ENCRYPTED_FILE, fernet)
    # 再生
    play_mp3_from_bytes(mp3_bytes)
    print("再生終了")


if __name__ == "__main__":
    main()
