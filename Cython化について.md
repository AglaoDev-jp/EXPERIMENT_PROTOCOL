# Cython化によるコード難読化ガイド

- Pythonがインストールされている環境が必要です。
- 使用ライブラリの内、外部ライブラリは別途インストールが必要です。
---

## Cython化に必要な環境の整備

Cython化を行うためには、Pythonだけでなく、C/C++コードをコンパイルするための環境が必要です。  
Windows環境では、**Visual Studio Build Tools** のインストールが必須となります。

### **1. Visual Studio Build Tools のインストール**

1. **公式サイトからインストーラーをダウンロード**  
   [Visual Studio Build Tools ダウンロードページ](https://visualstudio.microsoft.com/visual-cpp-build-tools/) にアクセスします。  
   「Build Tools」のダウンロードボタンをクリックしてください。

2. **インストーラーを起動**  
   ダウンロードしたインストーラーを開きます。

3. **必要なコンポーネントを選択**  
   インストール画面が表示されたら、次の項目を選択してください：
   - **C++ Build Tools**
    ※ versionによって表記が違うのかわかりませんが、ChatGPTのログを見ると、私は`C++によるデスクトップ開発`というところをクリックしたようです。  
    覚えてない...

   私の場合このような項目にチェックが入っていたようです。私はすべてインストールしました。
   - MSVCv143-VS2022 C++ x64/x86ビルド (必須のC++コンパイラです)
   - windows 11 SDK (OSに対応する開発キット。必須)
   - Windows用C++CMakeツール   
     (C/C++プログラムのビルド構成を記述して、プラットフォームやコンパイラに応じた適切なビルドファイルを自動生成します。  
     Cython化だけなら必須ではないそうです)
   - ツールのコア機能のテストビルドツール (デバッグ用らしいです、必須ではないです)
   - C++Addresssanitizer (メモリリーク検出ツール、通常のビルドでは不要です。)

4. **インストールを実行**  
   インストールボタンをクリックすると、必要なコンポーネントがダウンロードされ、環境が構築されます。

### **2. Cythonのインストール**

   Visual Studio Build Tools のインストールが完了したら、Cython本体をインストールします。  
   以下のコマンドをコマンドプロントやターミナルで実行してください：

   ```bash
   pip install cython
   ```

---

### ** 注意点 **

- **エラーが出る場合**  
   Visual Studio Build Tools のインストールが途中で失敗していたり、Pythonのバージョンが古い場合にエラーが発生することがあるようです。  
   次の項目を確認してください：  
   - Pythonのバージョンが最新であるか（推奨：3.7以降）。
   - `pip` が最新であるか（`python -m pip install --upgrade pip` で更新）。

- **インストールに時間がかかる**  
   Visual Studio Build Tools のインストールや必要なコンポーネントのダウンロードは、サイズが大きいためか環境によって時間がかかる場合があるようです。
   初回インストール時は時間に余裕をもって準備してください。(私はかなり時間がかかりました)  

- **環境変数 PATH の設定**  
   今回、環境変数PATHの設定は行っていません。以下の状況ではPATH設定が便利になる場合があります：  
   - コマンドプロンプトのどこからでも cl を呼び出す必要がある場合。
   - 複数のディレクトリやスクリプトで cl.exe を直接使うケースが増えた場合。
   - 外部ビルドツールが cl.exe を自動的に認識しない場合。

## 前準備
1. **キーのハードコーディング**  
   あらかじめ `secret.key` の内容を `sound_manager.py` にハードコーディングしておいてください。

2. **コメントアウトの削除**  
   必須ではありませんが、Cython化の前にコード内のコメントアウトを削除しておくと、クラックの難易度が上がるようです。  

### コメントアウトの削除手順 (Visual Studio Code)
1. **検索と置換を開く**  
   - Windows/Linux: `Ctrl + H`  
   - Mac: `Command + H`  

2. **正規表現を入力**  
   検索バーに以下を入力します：
   ```
   ^\s*#.*$
   ```
   置換バーは空欄のままにします。

3. **正規表現モードを有効化**  
   検索バー右の `.*` アイコンをクリックして有効にします。

4. **一括置換**  
   **すべて置換** (`Alt + Enter`) をクリックして、コメントアウトを削除します。

### 余計な空行の削除手順
1. **検索と置換を開く**  
   - Windows/Linux: `Ctrl + H`  
   - Mac: `Command + H`  

2. **正規表現を入力**  
   検索バーに以下を入力します：
   ```
   ^\s*\n
   ```
   置換バーは空欄のままにします。

3. **正規表現モードを有効化**  
   検索バー右の `.*` アイコンをクリックして有効にします。

4. **一括置換**  
   **すべて置換** (`Alt + Enter`) をクリックして、余計な空行を削除します。


## Cython化の手順

### 1. ファイル拡張子を変更
Cython化したいPythonファイル（例: `sound_manager.py`）の拡張子を `.pyx` に変更します。

**変更例：**
- 変更前: `sound_manager.py`
- 変更後: `sound_manager.pyx`

2. setup.pyを作成する
Cython化したファイルをコンパイルするために`setup.py`が必要です。
以下の内容で`setup.py`を作成してください(このプロジェクトでは既に作成済みです)

```python
from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules=cythonize("sound_manager.pyx", compiler_directives={'language_level': "3"})
)
```

- **`cythonize("sound_manager.pyx")`**: Cython化するファイルを指定します。
- **`language_level`**: Pythonのバージョンに対応します（Python 3の場合は `"3"` に設定）。

`setup.py` は通常、Cython化したいスクリプトと同じディレクトリ、またはプロジェクトのルートディレクトリに配置するそうです。  
今回は `src` フォルダ内に配置しました。(ディレクトリを変更したい場合は`setup.py`の記述を変更してください。)  

例：`setup.py`をルートディレクトリに置いた場合
```python
from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules=cythonize("src/sound_manager.pyx", compiler_directives={'language_level': "3"})
)
```

---

### 3. プロジェクトフォルダ構成
以下のようなフォルダ構成を推奨します：

```
プロジェクトフォルダ/
~~~

├── src/
│   ├── sound_manager.pyx  <- Cython化したいスクリプト
│   └── setup.py  <- `setup.py` はここに配置

~~~
```

## コンパイル手順

1. **`src` フォルダに移動**  
   コマンドプロントやターミナルで `src` フォルダに移動してください。
   ※ デスクトップにある場合

   ```bash
   cd ~/Desktop/プロジェクトフォルダ/src
   ```

   - `~` はユーザーのホームディレクトリ。
   - フォルダ名やパスは環境に合わせて変更してください。

2. **`setup.py` を実行してコンパイル**  
   以下のコマンドでCython化を実行します：
   ```bash
   python setup.py build_ext --inplace
   ```

3. **生成物の確認**  
   実行後、以下のファイルが `src` 内に生成されます：
   - **`sound_manager.c`**: コンパイル前のC言語のコード(デバックを行う場合には必要な情報になることもあるようです)
   - **Linux/macOS**: `sound_manager.cpython-<バージョン>-<プラットフォーム>.so`
   - **Windows**: `sound_manager.cp<バージョン>-<プラットフォーム>.pyd`  

   **例 (Windows環境の場合):**
   ```
   sound_manager.c
   sound_manager.cp312-win_amd64.pyd
   ```
   
   ### 実行ファイル化に必要なファイル
   実行ファイル化に必要なのは以下のファイルだけです：
   - **`sound_manager.cp312-win_amd64.pyd`**（環境に応じた名前に変更されます）

   他のファイル（`sound_manager.c`,`setup.py`,`sound_manager.pyx`）は、実行ファイル化には必要ありません。実行ファイル化の際にはフォルダ内に含めないようにしてください。

---

以上、私が行ったPythonコードのCython化の方法です。


