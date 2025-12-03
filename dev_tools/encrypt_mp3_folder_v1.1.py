"""
MP3音源ファイル一括暗号化スクリプト
- スクリプトと同じ場所にある全MP3を暗号化
- 暗号化済みファイルは「.enc」拡張子付きで"sounds_encrypted"フォルダとしてスクリプトと同じ場所に保存
- 暗号化キー（Fernetキー）は「secret.key」としてスクリプトと同じ場所に保存
"""

import os
from pathlib import Path
from cryptography.fernet import Fernet

# ========================
# --- 設定項目 ---
# ========================
# スクリプトファイルのあるディレクトリを基準とする
BASE_DIR = Path(__file__).parent.resolve()

# 暗号化対象となるフォルダのパス（このスクリプトを音源のある場所へ移動してください）
INPUT_FOLDER = BASE_DIR 
# 暗号化済みファイルの出力先フォルダ（BASE_DIR直下の"assets_encrypted"）
OUTPUT_FOLDER = BASE_DIR / "sounds_encrypted"
# 暗号化キーのファイル名（BASE_DIR直下）
KEY_FILE = BASE_DIR / "secret.key"


def generate_key(key_file):
    """
    Fernet用の暗号化キーを生成してファイルに保存
    すでに存在する場合は何もしない
    """
    if key_file.exists():
        print(f"[INFO] 既にキーが存在します: {key_file}")
        return
    key = Fernet.generate_key()
    with open(key_file, "wb") as f:
        f.write(key)
    print(f"[INFO] 暗号化キーを保存しました: {key_file}")


def load_key(key_file):
    """
    ファイルからFernetキーを読み込む
    """
    if not key_file.exists():
        raise FileNotFoundError(f"暗号化キーが見つかりません: {key_file}")
    with open(key_file, "rb") as f:
        return f.read()


def encrypt_file(input_path, output_path, fernet):
    """
    指定されたファイル（MP3）を暗号化し、出力パスに保存
    """
    with open(input_path, "rb") as f:
        data = f.read()
    encrypted_data = fernet.encrypt(data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(encrypted_data)
    print(f"[SUCCESS] 暗号化: {input_path} → {output_path}")


def encrypt_mp3_files(input_folder, output_folder, fernet):
    """
    フォルダを再帰的に探索し、すべてのMP3ファイルを暗号化
    """
    for root, dirs, files in os.walk(input_folder):
        for file in files:
            if file.lower().endswith(".mp3"):
                src_path = Path(root) / file
                rel_path = src_path.relative_to(input_folder)
                dest_path = output_folder / rel_path.with_suffix(rel_path.suffix + ".enc")
                encrypt_file(src_path, dest_path, fernet)


def main():
    # --- 暗号化キーを生成または読み込み ---
    generate_key(KEY_FILE)
    key = load_key(KEY_FILE)
    fernet = Fernet(key)

    # --- MP3ファイルを一括暗号化 ---
    encrypt_mp3_files(INPUT_FOLDER, OUTPUT_FOLDER, fernet)
    print("\nすべてのMP3ファイルの暗号化が完了しました。")


if __name__ == "__main__":
    main()
