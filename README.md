
---

# EXPERIMENT PROTOCOL_v1
"── The Experiment continues ──"  
コード、シナリオ、READMEなどのテキスト、画像の作成において、OpenAIの対話型AI「ChatGPT」を使用しています。  
ムービー素材は、OpenAI が提供する映像生成 AI「Sora」および「Sora 2」により生成しています。  
このリポジトリでは、ゲームの**ソースコード**と**実行ファイル**を公開しています。  
ゲームマニュアルは[こちら](./README_PLAY.md)  
ゲームファイル（実行ファイル）のダウンロードは[こちら]()  

---

本プロジェクトの制作にあたり、OpenAIの対話型AI「ChatGPT」のサポートを受けて、画像生成、アイデア出し、コード修正、文章の表現の改善、翻訳などをスムーズに行うことができました。  
    
* **GPT-5　GPT-5.1（ChatGPT Plus / 画像生成・シナリオ・テキスト制作・技術文書の校正・翻訳などで活用）**
* **GPT-4.1（コード生成・修正）**
* **GPT-o4 mini high（コードの修正で補助的に使用）**

※使用内容は、画像生成の指示、セリフやシナリオ表現の改善、コード設計、ライセンス文の調整、READMEや概要文の添削など多岐にわたります。　　

■ 動画素材について  

本作で使用しているムービー素材は、OpenAI が提供する映像生成 AI「Sora」および「Sora 2」により生成し、さらに本作の演出に合わせて編集したオリジナル映像です。  
Sora / Sora 2 による生成・利用は OpenAI の利用規約を遵守して行われています。  
映像の著作権は本ゲームの作者に帰属しますが、「Sora」「Sora 2」の名称および商標権は OpenAI に帰属します。  

AI生成映像は、現実映像との誤認・出典の混同・権利関係の混乱・第三者による不正利用、その他さまざまな誤解を招くリスクがあり、制作者・プレイヤー双方にとって重大なトラブルの原因となり得ます。  
そのため今回は本作に使用している動画をゲーム内でのみ視聴できる限定コンテンツとして扱っており、外部での使用を前提としていません。  

**本作で使用している動画の抽出・転載・再配布・二次利用・加工・アップロードを一切禁止します。**
ご理解とご協力をお願いいたします。  

開発に携わったすべての研究者、開発者、関係者の皆様に、心より感謝申し上げます。  

---

## 免責事項
本ゲームの利用や環境設定に起因するいかなる損害や不具合について、作者は一切の責任を負いません。  

---

**製作期間**

- **v1**: 2025年7月22日 ~ 2025年12月日

---

※ このリポジトリは個人学習のために使用しています。そのため、プルリクエスト（Pull Request）は、お受けすることができません。ご了承ください。  

---

## 使用言語とライブラリ

### 使用言語
- **Python 3.12.5**

---

### 使用モジュール・ライブラリ

#### 標準モジュール（Python 標準ライブラリ）

* **sys**

  * `sys.exit()` による安全なアプリ終了処理
  * 未処理例外捕捉フックでクラッシュログを出力

* **math**

  * レイキャスティング演算 / ビルボード投影 / プレイヤー回転処理で三角関数を使用

* **os**

  * カレントディレクトリ取得
  * 環境変数 `DEV_MODE` の参照
  * エラーログの出力

* **copy**

  * マップレイアウト・テクスチャ辞書などの“原本”保持のためディープコピーを使用

* **traceback**

  * 例外発生時に詳細ログをコンソール／ログファイルへ出力しデバッグを容易にする

* **json**

  * セーブ／ロード機能でフラグ・所持アイテム・位置情報などを JSON 形式で保存／読み込み

* **pathlib**

  * OS依存のないファイルパス操作に使用
  * `BASE_DIR` やアセットパス解決で広く利用

* **dataclasses**

  * `MovieSegment / ScriptSegment / EndRollSegment`
  * 会話制御系 `DialogueConfig / DialogueState`
  * これらをデータクラスとして定義し、初期化処理やデバッグ表示を自動化
  * ムービー・シナリオ構成・テキスト表示設定を「構造化オブジェクト」として管理し、可読性と保守性を向上

* **typing**

  * 型ヒントに使用し、可読性・安全性・IDE補完精度を向上

* **collections.deque / collections.abc**

  * カットシーン / ムービー再生キューの管理
  * コールバック指定や順序処理に使用

* **time**

  * セーブデータの内部保存用時刻として `time.time()`（UNIX タイムスタンプ）を記録
  * `saved_at` フィールドで並び替えや更新判定に利用

* **datetime**

  * セーブデータの表示用日時（`timestamp` フィールド）を生成
  * メニュー画面のセーブスロット一覧に「YYYY-MM-DD HH:MM」形式で整形

* **functools**

  * `@lru_cache` によるフォント生成結果のキャッシュ
  * 文字描画を多用するシーンでのパフォーマンス向上と描画一貫性を担保
  * タイピングエフェクト（句読点ポーズ含む）／オート／スキップ／高速モードの制御にも寄与

* **io**（`core/sound_manager.py`, `core/video_player.py`）

  * 暗号化された BGM／SE／ボイスの復号後に `io.BytesIO` を利用しメモリ上の擬似ファイルとして扱う
  * 一時ファイルを作成せず、デコード済みバイナリをそのまま
    `pygame.mixer.Sound` / `pygame.mixer.music.load()` に渡す中間レイヤとして使用

---

#### 外部ライブラリ

* **Pygame**

  * GUIフレームワークとして使用
  * 2D描画・ウィンドウ生成・テクスチャ描画・フォント描画・入力処理など
  * レイキャスト描画・ビルボードアニメーション・インタラクション処理を一括管理
  * BGM／SE／ボイス管理機能と UI 演出の同期
    → **ゲームの画面・操作系・UI/UXの主軸となるライブラリ**

* **NumPy**

  * レイキャスティングの各種演算を高速化（ベクトル化演算）
  * テクスチャの配列化・ピクセル単位処理
  * 床／天井描画（フロアキャスティング）処理
    → **フレームレートの維持と描画処理の最適化に大きく寄与**

* **OpenCV（cv2）**

  * ムービー再生処理の中核
  * `cv2.VideoCapture` を用いて動画をフレーム単位で読み取り、色変換・リサイズ後に `pygame.Surface` に変換して描画  
  * `time.perf_counter()` を併用して **フレーム単位の高精度再生タイミング制御**  
  * 旧 Pygame に存在した pygame.movie は現在廃止されています。  
    コーデック互換性の問題から動画再生は非推奨となったため、  
    安定して使用できる動画再生基盤を確保する目的で本作では
    **OpenCV によるフレーム単位制御＋Pygame 描画を採用しています。**
    → **Sora などで生成した高品質ムービー素材を、ゲームシーンにシームレスに統合可能**

---

### データの暗号化・復号化
- **cryptography**  

### 難読化
- **Cython**

### 実行ファイル化
- **PyInstaller**

### 使用エディター
- **Visual Studio Code (VSC)**  

---

### 著作権表示とライセンス

## 📂 ライセンスファイルまとめ[licenses](./licenses/)
- Python [LICENSE-PSF.txt](./licenses/LICENSE-PSF.txt)
- Pygame [LGPL_v2.1.txt](./licenses/third_party/LGPL_v2.1.txt) 
- NumPy [NumPy License](./licenses/third_party/LICENSE_NumPy.txt)
- NumPy(Bundled) [LICENSES_NumPy_Bundled](./licenses/third_party/LICENSES_NumPy_Bundled.txt) 
- OpenCV 4.10.0 [LICENSE_OpenCV.txt](./licenses/third_party/LICENSE_OpenCV.txt) 
- cryptography_LICENSE.APACHE [cryptography_LICENSE.APACHE](./licenses/third_party/cryptography_LICENSE.APACHE)  
- cryptography_LICENSE.BSD [cryptography_LICENSE.BSD](./licenses/third_party/cryptography_LICENSE.BSD)  
- OpenSSL_Apache.License 2.0 [OpenSSL_Apache.License 2.0.txt](./licenses/third_party/openssl_APACHE_LICENSE.txt) 
- Cython_Apache.License 2.0 [Cython_Apache.License 2.0.txt](./licenses/third_party/Cython_Apache.License_2.0.txt) 
- Cython_COPYING [Cython_COPYING.txt](./licenses/third_party/Cython_COPYING.txt) 
- PyInstaller [GNU GPL v2 or later（例外付き）](./licenses/third_party/LICENSE_PyInstaller.txt)
- Noto Sans JP [SIL Open Font License, Version 1.1](./licenses/third_party/OFL.txt) 

---

### **Python**  
- Copyright © 2001 Python Software Foundation. All rights reserved.
Licensed under the PSF License Version 2.  
[Python license](https://docs.python.org/3/license.html)  
 ※ コードのみであればライセンス添付は不要ですが、PyInstallerを使って実行ファイル化する際にはPythonのライセンス（PSF License）の添付が必要です。  
   (内部にPythonの一部が組み込まれるため)

---

### このプロジェクトでは、以下のオープンソースライブラリを使用しています：

#### **Pygame**
- © 2000–2024 Pygame developers  

Pygameは、**GNU Lesser General Public License バージョン2.1 (LGPL v2.1)** の下でライセンスされています。  
このライセンスでは、以下の条件を満たす必要があります：  
- **ライセンス文を配布物に含めること。**  
- **ライブラリを改変した場合、その改変部分のソースコードを公開すること。（可能であれば改変内容を Pygame プロジェクトにフィードバックすることが推奨されています）**  
LGPL v2.1 により、Pygameは商用・非商用を問わず自由に利用・再配布することができます。  

### **PyInstallerを使った場合の対応**
- PyInstallerを使用してPygameをバンドルした場合でも、LGPLライセンスの条件を満たしています。  
  - ライブラリは動的リンクとして扱われます。
  - アプリケーションのソースコードを公開する義務はありません。
- ただし、以下の対応を行う必要があります：  
  - ライセンス文を配布パッケージに含める。  
  - Pygameを改変した場合、その改変部分のソースコードを公開する。  

詳細なライセンス条項については、以下を参照してください：  
- [Pygame License](https://github.com/pygame/pygame/blob/main/docs/LGPL.txt)  
 
> **備考:** PyInstallerでバンドルされた場合、ユーザーがライブラリを差し替える権利は担保されています。そのため、アプリケーション全体をオープンソースにする必要はありません。
### 静的リンクとの違い  
### **LGPLの基本ルール**
- 動的リンクが原則

  LGPLライセンスでは、ライブラリをアプリケーションに「動的リンク」することが前提です。  
  動的リンクとは、実行時にライブラリを別ファイルとして参照する方法を指します（例: .dll, .so）  
  LGPLライセンスでは、Pygameをリンクしているアプリケーションのソースコードを公開する必要はありません。  
  ただし、利用者がライブラリを差し替えられる仕組みを提供する必要があります。  

  Pygameを「静的リンク」してアプリケーションに組み込んだ場合、LGPLライセンスの適用範囲が広がり、  
  アプリケーション全体にLGPLが適用される可能性があります。  

- 静的リンク
  - 静的リンクでは、ライブラリのコードがアプリケーションのバイナリに直接埋め込まれるため、ライブラリの差し替えができなくなります。  
  この場合、アプリケーション全体がLGPLの影響を受ける可能性があります。

- 動的リンク（PyInstallerのケース）
  - PyInstallerはライブラリを個別のモジュールとして扱うため、実行時に動的にロードされます。
  この形式は、技術的にはPyInstallerで作成された実行ファイルの依存ライブラリ（例: Pygameの.dllファイル）を他のバージョンや改変版に置き換えることが可能です。  
  このため、アプリケーションがクローズドソースでも配布が可能のようです。　　

---

### NumPy

- **ライセンス**：BSD 3-Clause License（通称："NumPy License"）  
- **著作権表示**：© 2005–2025 NumPy Developers. All rights reserved.  
- **ライセンス原文**：[https://github.com/numpy/numpy/blob/main/LICENSE.txt](https://github.com/numpy/numpy/blob/main/LICENSE.txt)  
- **公式サイト**：[https://numpy.org](https://numpy.org)  
- **GitHub**：[https://github.com/numpy/numpy](https://github.com/numpy/numpy)

> NumPyは 基本的にはBSD 3-Clause License に準拠していますが、一部に NumPy Project 独自の補足説明が付いたカスタム表記（"NumPy License" と書かれることもある）を採用しています。  

> NumPy は、自由度の高い BSD ライセンスのもとに配布されており、活発で反応が早く、多様性に富んだコミュニティによって GitHub 上で開発・保守されています。  
> (*Distributed under a liberal BSD license, NumPy is developed and maintained publicly on GitHub by a vibrant, responsive, and diverse community.*)  
> — [NumPy公式サイトより引用](https://numpy.org/)
> NumPyには、一部内部で使用されている第三者ソフトウェアコンポーネントが存在します。  
> 必須ではないようですがライセンス情報を[LICENSES_NumPy_Bundled.txt](./licenses/third_party/LICENSES_NumPy_Bundled.txt) に記載しています。

### OpenCV 4.10.0  

- **ライセンス**：Apache License, Version 2.0  
- **著作権表示**：Copyright © 2000-2025 OpenCV Foundation and contributors  
- **ライセンス原文**：[https://opencv.org/license/](https://opencv.org/license/)  
- **公式サイト**：[https://opencv.org](https://opencv.org)  
- **GitHub**：[https://github.com/opencv/opencv](https://github.com/opencv/opencv)

---

#### **cryptography**  
- Copyright (c) Individual contributors. All rights reserved.  
このプロジェクトでは、音源データの暗号化・復号化に`cryptography`ライブラリを使用しています。  
このライブラリは以下のライセンスに基づき配布されています：  
- Apache License 2.0  
- 一部コンポーネントはBSDライセンス（3-Clause License）  

また、`cryptography`ライブラリのバックエンドとしてOpenSSLが使用されており、バージョンによりライセンスが異なります：  

- **OpenSSL 3.0以降**：Apache License 2.0  
- **OpenSSL 3.0未満**（1.1.1やそれ以前）：OpenSSL License および SSLeay License のデュアルライセンス  

今回使用しているバージョンは以下の通りです：  
**OpenSSL 3.4.0**  
このバージョンは**Apache License 2.0**に基づいて配布されています。
- Copyright (c) 1998-2025 The OpenSSL Project Authors  
- Copyright (c) 1995-1998 Eric A. Young, Tim J. Hudson  
- All rights reserved.  

詳しくは以下をご確認ください：  
- [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)  

**注意**:  
このソースコード(ソフトウェア)は、日本国内での使用を想定しています。  
国外配布を行う場合、該当国の暗号化技術に関する規制をご確認ください。  
暗号化技術は輸出規制や各国の法律の対象となる場合があります。  
特に、他国への配布時は適切な手続きが必要です。  

---

#### **Cython** 
このプロジェクトの実行ファイルは、Cythonを使用して難読化を行っています。  
- Cython © 2007-2025 The Cython Project Developers  
- Licensed under the Apache License 2.0.  
- [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)  

---

#### 📦 PyInstaller  

このプロジェクトは、**PyInstaller** を使用して実行ファイル化に対応しています。  
PyInstaller は GNU GPL ライセンスですが、例外規定により  
**生成される実行ファイル自体は GPL の制約を受けません**。
- Copyright (c) 2010–2023, PyInstaller Development Team  
- Copyright (c) 2005–2009, Giovanni Bajo  
- Based on previous work under copyright (c) 2002 McMillan Enterprises, Inc.

#### ⚖️ PyInstaller のライセンス構成について

PyInstaller は以下のように**複数のライセンス形態**で構成されています：

- 🔹 **GNU GPL v2 or later（例外付き）**  
  本体およびブートローダに適用されます。  
  → **生成された実行ファイルは任意のライセンスで配布可能**です（依存ライブラリに従う限り）。

- 🔹 **Apache License 2.0**  
  ランタイムフック（`./PyInstaller/hooks/rthooks/`）に適用されています。  
  → 他プロジェクトとの連携や再利用を意識した柔軟なライセンス。

- 🔹 **MIT License**  
  一部のサブモジュール（`PyInstaller.isolated/`）およびそのテストコードに適用。  
  → 再利用を目的としたサブパッケージに限定適用されています。

####  詳細情報へのリンク

- [PyInstallerのライセンス文書（GitHub）](https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt)  
- [PyInstaller公式サイト](https://pyinstaller.org/en/v6.13.0/index.html)  


---

## 使用フォントについて

このゲームでは、"Noto Sans JP"フォントファミリー（NotoSansJP-Regular.otf）を使用しています。

- **Noto Sans JP**  
  - © 2014-2025 Google LLC  
  - SIL Open Font License, Version 1.1   

### **ライセンスの概要と必要な対応**
Noto Sans JPは、SIL Open Font License (OFL) Version 1.1に基づき、以下の条件で使用できます：

#### **許可される行為**
1. **自由な利用**: フォントは商用・非商用問わず自由に使用できます。
2. **改変および再配布**: 改変後のフォントを含むパッケージを再配布することができます。
3. **埋め込み**: PDFやアプリケーションなどにフォントを埋め込むことが可能です。

#### **義務と禁止事項**
1. **ライセンス文書の添付**:
   - フォントを再配布または改変する場合は、必ずOFLライセンス文書（例: `OFL.txt`）を添付してください。
2. **フォント名の変更**:
   - 改変後のフォントを再配布する場合、フォント名を変更する必要があります。
3. **販売の禁止**:
   - フォントファイル自体を販売することは禁止されています。ただし、フォントを使用したプロダクト（例: 印刷物、アプリ）は販売可能です。

#### **ゲームにおける対応**
- **クレジット表記**:
  - ゲームのクレジットやドキュメント内で、フォント名およびライセンス情報を明記してください。
  - 表記例:  
    ```plaintext
    "Font: Noto Sans JP © 2014-2025 Google LLC, licensed under SIL Open Font License, Version 1.1."
    ```
- **ライセンスファイルの同梱**:
  - `OFL.txt`をゲームパッケージの適切な場所（例: `licenses/third_party/`フォルダ）に含めてください。  

詳しくは以下をご確認ください：  
- [OFL.txt](./licenses/third_party/OFL.txt)  

---

これらのプロジェクトの開発者の皆様、貢献者の皆様に、心より感謝申し上げます。

---

## 音源について
ソースコードフォルダには、音楽や効果音の音源自体は含まれておりません。  
ゲームで使用する音楽と効果音は、以下の提供元サイトからダウンロードをお願いします。  
ご利用にあたっては、各提供元サイトの規約をよくお読みいただき、適切な利用をお願いします。  

- **フリーBGM DOVA-SYNDROME**  
- **効果音ラボ**  

使用した具体的な曲目や効果音は、以下のリストをご確認ください。    

### フリーBGM DOVA-SYNDROME  

- [追跡者シーン] うしろからなにかが近づいてくる　東雄アモ
- [エンディング] Inside_the_Dying_Room　松浦洋介
- [あとがき] 私の部屋 Heitaro Ashibe

### 効果音ラボ   

- [選択・風見鶏] 決定ボタンを押す13
- [決定] 決定ボタンを押す16
- [キャンセル] 警告音2
- [足音：森] 砂利の上を歩く
- [足音：研究所] 革靴で歩く
- [足音：地下道] アスファルトの上を歩く1
- [アイテム取得] 決定ボタンを押す38
- [別マップ移動：決定] キャンセル9
- [別マップ移動：キャンセル] キャンセル1
- [メニューを開く] メニューを開く2
- [メニューを閉じる] メニューを開く3
- [セーブ] メニューを開く4
- [ロード] メニューを開く5
- [オープニング・エンディング（ムービー）] 恐怖
- [唸り声] ゴブリンの鳴き声3
- [恐怖におびえるシーン・博士拘束（ムービー）] 異次元空間
- [霧（ムービー）] 死後の世界
- [霧が晴れる（ムービー）] 魔法陣を展開
- [河原の音（ムービーとマップBGM）] 河原
- [木を切る音] 打撃5
- [木が倒れる音（ムービー）] 木が倒れる
- [博士登場（ムービー）] 映写機
- [ドアの開く音] 鉄の扉を開ける
- [絵画スイッチを押す：正解] 決定ボタンを押す52
- [絵画スイッチを押す：誤答] ビープ音4
- [全問正解でシャッターが開く] 巨大シャッターが開く
- [追跡者（ムービー）] 狂気
- [地下道脱出（ムービー）] 土の上を走る
- [ひやりとした風] 風に揺れる草木1
- [大勢で走るシーン] アスファルトの上を走る2

（敬称略）  

---

音源を提供してくださった制作者の皆様、貢献者の皆様に、心より感謝申し上げます。  

---

### 音声について

本作では、音声合成サービス **CoeFont（コエフォント）** を使用しています。
使用している音声はすべて合成音声であり、本作の内容は**実在の人物・団体とは一切関係ありません**。

#### 音声提供・作成

- **合成音声サービス：CoeFont**
- **Voiced by https://CoeFont.cloud**
- **使用プラン：Standard プラン**

#### 使用音声一覧

- [ユイ・ミナセ]：あかね大佐 \*
- [博士]：Canel（CV: 森川智之）
- [ナレーション・その他]：さのすけ（中低音ボイス）

（敬称略） 

---

音声提供者の皆様、関係者の皆様に、心より感謝申し上げます。

---

### 問題点・反省点
- モジュールを思いつきで分けすぎて管理がしづらくなった。
- 本来のステート管理ができずseve_system.pyで行ってしまっている。
- 音源の拡張子自動化が対応できていない部分がある。
- 音源の参照や動画の参照がバラバラ
- トースト表示もバラバラ
- 付け焼刃的に修正してもらったヘルパー関数でよりコードが煩雑になってしまった。
- 音源以外のアセット（画像・スクリプトなど）の保護（クラック対策）が未実装。

---

## ソースコードについて

### ※ 制作に必要なツールを`dev_tools`フォルダにまとめてあります。
### ※ 音源の暗号化を行わなくても起動できますが、ソースコードにある音源の記述に拡張子の変更が必要です。
### ※ Cython化を行わなくても起動できます。

1. **Pythonのインストール**  
   `.py`ファイルの実行には、Pythonがインストールされている環境が必要です。

### 必要なライブラリのインストール

   - インストールがまだの場合は、以下のコマンドを使用してください。
   
   Pygameのインストール
   ```shell
   pip install pygame numpy opencv-python cryptography
   ```

2. **音源の暗号化（任意）** 
   `dev_tools`フォルダ内の`encrypt_mp3_folder.py`を使用して音源の暗号化をおこなってください。  
   ※ 現在`assets`を参照して音源の暗号化を行い、`assets_encrypted`フォルダと`secret.key`が作成される記述になっています。  
   暗号化した音源は`assets`に移動するか`assets_encrypted`をリネーム等する必要がありますので、面倒ならば任意で変更してください。  

3. **`secret.key`のハードコーディング（暗号化の場合のみ）**
   `secret.key`の中身を`sound_manager.py`に貼り付けてください（場所はコード内に記述してあります）  

4. **ゲームの起動**  
   コマンドラインインターフェースを使用して、以下の手順でゲームを起動します。  

   - `cd`コマンドで`main.py`ファイルのディレクトリに移動します。  
   例: `main.py`ファイルを右クリックして「プロパティ」の「場所」をコピーなど。  
   ```shell
   # 例: デスクトップにフォルダがある場合 (パスはPC環境により異なります)
   cd C:\Users\<ユーザー名>\Desktop\mogura-no-bouken-rpg_v1\src
   ```

   - フォルダに移動後、以下のコマンドでゲームを起動します。  
   ```shell
   python main.py
   ```

5. **コードエディターでの実行**  
   一部のコードエディター（VSCなど）では、直接ファイルを実行することが可能です。  

---

## Pythonファイルのモジュール化とコンパイルについて

本プロジェクトでは、スクリプトを機能ごとに分割し、複数のPythonファイルとして**モジュール化**しています（例：`scenes/intro_event.py`など）。  

Pythonでは、スクリプトを**インポート**すると、自動的に以下のような処理が行われます：  

### モジュールのインポートと`.pyc`ファイルの生成

* モジュール（`.py`ファイル）をインポートすると、Pythonはその内容を\*\*バイトコード（中間コード）\*\*に変換して実行します。
* 初回のインポート時や更新があった際、`__pycache__`というディレクトリが自動で作られ、**`.pyc`（Python Compiled）ファイル**が生成されます。
* これは実行速度を高めるためのもので、次回以降はこのバイトコードが使用されるため、再コンパイルのコストが抑えられます。

> 例：`scenes/intro_event.py` をインポートすると、`__pycache__/intro_event.cpython-312.pyc` というファイルが作られます（Python 3.12 の場合）。

### `.pyc`ファイルとGit管理

* `.pyc`ファイルは**ソースコードではない**ため、通常は**バージョン管理（Gitなど）には含めません**。
* `.gitignore` に以下のような記述をすることで、誤ってGitに追加されることを防ぎます：

```gitignore
__pycache__/
*.pyc
```
### ポイント

* `.py` は人間が読む**ソースコード**
* `.pyc` は機械が読む**バイトコード**
* Pythonは動的言語なので、インポート時に**必要な部分だけコンパイルされる**
* `.pyc`は無理に消さなくても良いが、不要であれば削除しても自動で再生成される

### 補足

* `.pyc`ファイルの動作や保存場所はPythonのバージョンや環境によって多少異なります。

---

## PyInstallerによる実行ファイル化

このソースコードでは、**PyInstaller**を使用してPythonスクリプトを単一の実行ファイルに変換して使用することができました。  
この手順を実施することで、Python環境をインストールしていない環境でもゲームを実行できるようになります。配布にも適した形に仕上げることが可能です。  
### ※ 実行ファイル化の場合にはCython化を推奨します。[Cython化について](./Cython化について.md)  
以下に手順を示します：  

ディレクトリ構成：  

```

src/
├── assets/
│   ├── fonts/
│   │   └── NotoSansJP-Regular.ttf
│   ├── movies
│   ├── sounds
│   │   ├── bgm
│   │   ├── se
│   │   └── voice
│   ├── sprites/ 
│   │   └── chaser
│   ├── textures/
│   ├── ui
│   └── sound_settings.json
│   
├── core/
│   ├── asset_utils.py 
│   ├── cinematics.py 
│   ├── config.py 
│   ├── dialogue_flow.py 
│   ├── enemies.py             
│   ├── fonts.py  
│   ├── game_state.py             
│   ├── interactions.py   
│   ├── items.py                 
│   ├── maps.py  
│   ├── player.py
│   ├── save_system.py
│   ├── sound_manager.cp312-win_amd64.pyd
│   ├── texture_loader.py       
│   ├── tile_types.py 
│   ├── toast_bridge.py               
│   ├── transitions.py 
│   ├── ui.py 
│   └── video_player.py
│
├── scenes/
│   ├── afterword.py  
│   ├── doctor_event.py  
│   ├── end_roll.py
│   ├── ending_event.py
│   ├── intro_event.py 
│   ├── menu.py 
│   ├── scene_manager.py      
│   ├── startup.py        
│   ├── title_scene.py        
│   └── video_event.py
│
├── main.py   
│
└── icon.ico            ← アイコン画像（任意）

```

---

### 必要なライブラリのインストール

**依存ライブラリのインストール**  


   Pygameのインストール
   ```shell
   pip install pygame
   ```
   cryptographyのインストール
   ```shell
   pip install cryptography
   ```

   cythonのインストール
   ```shell
   pip install cython
   ```

   PyInstallerのインストール
   ```shell
   pip install pyinstaller
   ```

---

### 実行ファイルの作成方法

1. **音源の暗号化** 
   `dev_tools`フォルダ内の`encrypt_mp3_folder.py`を使用して音源の暗号化をおこなってください。  
   ※ 現在`assets`を参照して音源の暗号化を行い、`assets_encrypted`フォルダと`secret.key`が作成される記述になっています。  
   暗号化した音源は`assets`に移動するか`assets_encrypted`をリネーム等する必要がありますので、面倒ならば任意で変更してください。 

2. **`secret.key`のハードコーディング**
   `secret.key`の中身を`sound_manager.py`に貼り付けてください（場所はコード内に記述してあります）

3. **Cython化**
   `sound_manager.py`のファイル名を`sound_manager.pyx`に変更後`setup.py`を使用してコンパイルしてください。  
   詳しくは[Cython化について](./Cython化について.md)をご参照ください。   

   以下のコマンドでCython化を実行します：  

   ```
   python setup.py build_ext --inplace
   ```

  作成された`sound_manager.cp312-win_amd64.pyd`をディレクトリ構成を参考に配置してください。  
  ※他のファイル（`sound_manager.c`,`setup.py`,`sound_manager.pyx`）は、実行ファイル化には必要ありません。  
  実行ファイル化の際にはフォルダ内に含めないようにしてください。  
　　
4. **プロジェクトフォルダに移動する**  
   コマンドプロンプトまたはターミナルで、プロジェクトフォルダに移動します：

   ```shell
   cd <プロジェクトフォルダのパス>
   ```

   **例**: デスクトップにフォルダがある場合  
   ```shell
   cd C:\Users\<ユーザー名>\Desktop\EXPERIMENT PROTOCOL_v1\src
   ```

2. **実行ファイルの作成**  
   以下のコマンドを実行します：

   ```shell
    pyinstaller --onefile --windowed --icon=icon.ico --add-data "assets;assets" --add-data "scenes;scenes" main.py

   ```

---

### オプションの詳細説明

- **`--onefile`**: 単一の .exe ファイルにまとめます。
- **`--windowed`**: コンソールを表示しない。
- **`--icon=icon.ico`**: アプリのアイコンを設定します。
- **`--add-data`**必要な素材フォルダやサブモジュールを一緒に


---


### 実行ファイルの確認

PyInstallerが成功すると、以下のようなディレクトリ構成が作成されます：

```
プロジェクトフォルダ/
├── build/           <- 一時ファイル（削除してOK）
├── dist/            <- 実行ファイルが保存されるフォルダ
│   └── main.exe <- 出来上がった実行ファイル
├── main.py          <- メインコード
~~~
├── icon.ico         <- アイコン画像
└── *.spec           <- PyInstallerの設定ファイル（削除してOK）

```

実行ファイルは`dist`フォルダ内に出力されます。  
`dist`フォルダ内に作成された実行ファイル（例: `main.exe`）を使用してゲームを実行できます。  
生成された実行ファイルは、Python環境を必要とせずに動作します。  
ひとつのシステムファイルにまとめられていますので、配布にも適した形になっています。  
distフォルダ内に作成された実行ファイルをそのまま配布するだけで、他のユーザーがゲームをプレイできるようになります。  

### 注意事項
  ※この注意事項は、PyInstallerで生成された.exeファイルなどの実行ファイルについて記載しています。  
  Pythonスクリプト（.pyファイル）には該当しません。

- **セキュリティに関する注意**  
  PyInstallerはスクリプトを実行ファイルにまとめるだけのツールであり、コードの暗号化や高度な保護機能を提供するものではありません。  
  そのため、悪意のあるユーザーが実行ファイルを解析し、コードやデータを取得する可能性があります。  
  コードやデータなどにセキュリティが重要なプロジェクトで使用する場合は、**追加の保護手段を検討してください。**  

- **OSに応じた調整**  
  MacやLinux環境で作成する場合、`--add-data` オプションのセパレータやアイコン指定の書式が異なるようです。  
  詳細は[PyInstaller公式ドキュメント](https://pyinstaller.org)をご確認ください。  
  実行ファイル化において発生した問題は、PyInstallerのログを確認してください。  

- **ライセンスとクレジットに関する注意**   
    **推奨事項**  
     PyInstallerのライセンスはGPLv2（GNU General Public License Version 2）ですが、例外的に商用利用や非GPLプロジェクトでの利用を許可するための追加条項（特別例外）が含まれています。  
     実行ファイルを配布するだけであれば、PyInstallerの特別例外が適用されるため、GPLv2ライセンスの条件に従う必要はないようです。
     ライセンス条件ではありませんが、プロジェクトの信頼性を高めるため、READMEやクレジットに「PyInstallerを使用して実行ファイルを作成した」旨を記載することを推奨します。  

    **PyInstallerのライセンスが必要な場合**  
     PyInstallerのコードをそのまま再配布する場合、もしくは改変して再利用する場合は、GPLv2ライセンスに従う必要があります。  
     この場合、以下を実施してください：  
      - PyInstallerのライセンス文を同梱する。  
      - ソースコードを同梱するか、ソースコードへのアクセス手段を提供する。  

    **詳細情報**  
     PyInstallerのライセンスについて詳しく知りたい場合は、[公式リポジトリのLICENSEファイル](https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt)をご参照ください。  

---

## このゲームのライセンス

- **このゲームのコード**: MIT License。詳細は[LICENSE-CODE](./licenses/game/LICENSE-CODE.txt)ファイルを参照してください。
- **画像**: Creative Commons Attribution 4.0 (CC BY 4.0)。詳細は[LICENSE-IMAGES](./licenses/game/LICENSE-IMAGES.txt)ファイルを参照してください。
- **シナリオ**: Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0)。詳細は[LICENSE-SCENARIOS](./licenses/game/LICENSE-SCENARIOS.txt)ファイルを参照してください。


## ライセンスの簡単な説明

- **このゲームのコード**: （MIT License）
このゲームのコードは、MITライセンスのもとで提供されています。自由に使用、改変、配布が可能ですが、著作権表示とライセンスの文言を含める必要があります。

- **画像**: （Creative Commons Attribution 4.0, CC BY 4.0）
このゲームの画像は、CC BY 4.0ライセンスのもとで提供されています。自由に使用、改変、配布が可能ですが、著作権者のクレジットを表示する必要があります。

- **シナリオ**:（Creative Commons Attribution-ShareAlike 4.0, CC BY-SA 4.0）
このゲームのシナリオは、CC BY-SA 4.0ライセンスのもとで提供されています。自由に使用、改変、配布が可能ですが、著作権者のクレジットを表示し、改変後も同じライセンス条件を適用する必要があります。

※これらの説明はライセンスの概要です。詳細な内容は各ライセンスの原文に準じます。

---

## クレジット表示のテンプレート（例）  

### コード
```plaintext
Code by AglaoDev-jp © 2025, licensed under the MIT License.
```

### 画像
```plaintext
Image by AglaoDev-jp © 2025, licensed under CC BY 4.0.
```

### シナリオ
```plaintext
Scenario by AglaoDev-jp © 2025, licensed under CC BY-SA 4.0.
```

---
#### ライセンスの理由
現在のAI生成コンテンツの状況を踏まえ、私は本作品を可能な限りオープンなライセンス設定になるように心がけました。  
問題がある場合、状況に応じてライセンスを適切に見直す予定です。  

このライセンス設定は、権利の独占を目的とするものではありません。明確なライセンスを設定することにより、パブリックドメイン化するリスクを避けつつ、自由な利用ができるように期待するものです。  
  
© 2025 AglaoDev-jp

