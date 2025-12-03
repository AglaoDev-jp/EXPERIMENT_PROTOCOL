
---

# EXPERIMENT PROTOCOL_v1  
"── The Experiment continues ──"  
コード、シナリオ、READMEなどのテキスト、画像の作成において、OpenAIの対話型AI「ChatGPT」を使用しています。  
ムービー素材は、OpenAI が提供する映像生成 AI「Sora」および「Sora 2」により生成しています。  

---

本プロジェクトの制作にあたり、OpenAIの対話型AI「ChatGPT」のサポートを受けて、画像生成、アイデア出し、コード修正、文章の表現の改善、翻訳などをスムーズに行うことができました。  
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

## 使用上の注意  
本ソフトウェアには以下の制限事項があります。利用者はこれを承諾した上で利用してください。  

1. **暗号化技術に関する法規制の遵守**  
   本ソフトウェアには、暗号化の為`cryptography`ライブラリが使用されています。再配布の際には、暗号化技術に関する輸出規制を含む法規制を遵守してください。  
2. **ライセンス条件の遵守**  
   **再配布を行う場合**は、ライブラリなどのライセンス条件に従ってください。  

---

### 注意事項  

- **セーブデータについて**  
  セーブデータは、実行ファイルと同じフォルダ（`main.py`ファイルと同じディレクトリ）に`json`ファイルで作成されます。
  実行ファイルやセーブフォルダを移動するとデータが共有されなくなりますので、必ず同じフォルダ内に配置してください。  
  また、ゲームを削除する時には実行ファイルを削除するだけでなく、セーブフォルダの削除も忘れずに行ってください。

---

### セキュリティおよび禁止事項について

**セキュリティと禁止事項**  
本ゲームの実行ファイルは、**PyInstaller** を使用して作成されています。  
実行ファイルを逆アセンブル、逆コンパイル、リバースエンジニアリングなどを行い、内部のリソース（音源、画像、フォント、スクリプト、シナリオなど）を取り出す行為を**固く禁止**します。

---

### オープンソースについて

* コードおよび画像素材は**オープンソース**です。
* 本ゲームのフォントは、"Noto Sans JP"フォントファミリー (NotoSansJP-Regular.otf) を使用しています。

---

### 音源の保護について

* 本ゲームに使用されている**すべての音源ファイル**は、`cryptography`ライブラリによる**AES暗号化**を施しています。
* 暗号化キーを含むコードは、**Cython** によって難読化されています。

> 使用音源は、著作権フリーの音源配布サイトより提供されているものを採用しています。
> 利用をご希望の場合は、**必ず各サイトの正規の方法に従って入手してください。**

---

## ゲームファイル(実行ファイル)のセキュリティに関する注意事項
  本ソフトウェアは、**悪意のあるコード（ウイルス・マルウェア）は含まれていません。**  
  しかし、一部のアンチウイルスソフト（Norton,Avast,AVG,SecureAge,Zillya など）により、**誤検出**されることがあります。  
  これはファイルサイズや圧縮方法による影響であり、悪意のある動作はありません。

### **※誤検出が気になる場合や、安全性に不安がある場合は、実行を控えてください。**

---

## 動作環境

* Windows 10 / 11 （64bit推奨）
* Python 3.12.5
* 画面解像度：800×600以上推奨
* サウンド再生環境必須（効果音・BGMあり）

---

## あらすじ

深い闇に包まれた森の中で、主人公は冷たい土の感触とともに目を覚まします。  
そこがどこなのか、自分が誰なのか――最も根源的な記憶すら思い出せず、頭の中は霧のようにぼやけています。  
身体には無数の傷と痣。何かから逃げていたのか、それとも襲われたのか――確かなことは何ひとつ分かりません。  
そのとき、静寂を破るように森の奥から低いうなり声が響きます。  
ここに留まってはいけない――本能だけを頼りに、主人公は暗い森の中を進み始めます。  
記憶を失った主人公は、やがてこの場所の秘密と、自分自身の真実へと辿り着いていくことになります。  

---

# 📘 あそびかたガイド

本作は **「ムービー → シナリオ → 3Dマップ探索」** を軸に進行するアドベンチャーゲームです。
ストーリーを追いながらフィールドを探索し、アイテム収集・仕掛けの解読・危険からの回避を通して物語の真相へと迫っていきます。

---

## 🎬 ゲームの流れ

1. **ムービー**

   * 重要シーンではフルスクリーンムービーが再生されます。
   * `Enter`キーでスキップ可能です。

2. **シナリオパート（会話・イベント）**

   * 一枚絵の背景＋テキストウインドウで進行します。
   * 手動送り／スキップ送り／オート送りを切り替えられます。
   * シナリオ中にムービーが挿入されることもあります。

3. **3Dマップ探索パート**

   * フィールドを自由に歩き、調査・アイテム取得・ギミック操作を行います。
   * 仕掛けの作動にはアイテムが必要な場合があります。
   * 一部のマップでは「追跡者」が出現し、追跡を回避して脱出を目指す展開があります。

追跡者に見つかるとプレイヤーを追いかけてきます。  

* 距離を取る
* 遮蔽物を使う
* 回り道をする

などで振り切ることができます。

> 追いつかれてしまった場合
> → **「追跡者」エリアの入り口付近まで戻されます。ゲームオーバーにはなりません。**  

焦らず安全なルートを探し、脱出を目指してください。  

▼ 進行イメージ  
> **ムービー → シナリオ →（自動で）探索 →（特定地点で）ムービー／シナリオ → 探索再開…**  
> このサイクルを繰り返し、物語は核心へ近づいていきます。  

---

## ⌨ 操作説明（キーボード）

---

### 1️⃣ 基本操作（共通）

| 操作内容      | キー（デフォルト） | 説明                            |
| --------- | --------- | ----------------------------- |
| 決定・会話を進める | `Enter`   | 会話送り、選択肢の決定、メニュー内の決定。         |
| キャンセル     | `Esc`     | ひとつ前に戻る、メニューを閉じる。（使用できない場面あり） |
| メニューを開く   | `M`       | 音量調節・アイテム・セーブ/ロードを開きます。      |
| フルスクリーン切替 | `F11`     | フルスクリーン／ウィンドウを切り替えます。         |

---

### 2️⃣ シナリオシーン（会話・イベント中）

| 操作内容    | キー（デフォルト）         | 説明                           |
| ------- | ----------------- | ---------------------------- |
| テキスト送り  | `Enter` | 次の文章を表示します。                  |
| スキップモード | `S`      | テキストを高速で送ります。（解除：もう一度 `S`）           |
| オートモード  | `A`               | 自動で文章が進行します。（解除：もう一度 `A`）    |

> 状態バッジ（AUTO / SKIP）は、テキストウインドウ右上付近に小さく表示されます。  
> `Esc`キーでイベント全スキップ可能（y / n で選択）

---

### 3️⃣ マップ移動シーン（3D探索中）

| 操作内容          | キー（デフォルト）     | 説明                       |
| ------------- | ------------- | ------------------------ |
| 前進・後退         | `↑` / `↓`     | プレイヤーの移動。                |
| 左右回転          | `←` / `→`     | 視点の回転。                   |
| 調べる/アイテム取得/アイテム使用| `E` | 扉・スイッチ・調べられるものに使用。       |
| メニュー          | `M`           | 音量調節・アイテム・セーブ/ロードを開きます。 |
| クイックセーブ    | `F5`           | スロット1へ即座にセーブ。   |
| クイックロード    | `F9`           | スロット1のデータを即座にロード。      |

> クイックセーブ/クイックロードは、スロット1で行われます。  
> スロット1へのセーブ・ロードは、メニューから行うことも可能です。  
> 「追跡者」出現マップでは、クイックセーブを行うことができません。  

---

#### 🔹「E」キーのアクションについて

フィールド上で対象に近づくと、画面下部にアクションのトーストが表示されます。

例：

| 状況 | 表示例 |
| --- | --- |
| アイテムの前 | **「E：拾う」** |
| 扉の前 | **「E：開ける」** |
| スイッチの前 | **「E：押す」** |

`E` を押すことで表示中のアクションが実行されます。

> トーストが表示されている時のみアクション可能です。  
> トーストが出ても反応がない場合は、距離や角度を少し調整してください。  

⚠ 「E」トーストが表示されない場合 → **必要なアイテムを持っていない可能性あり**  
例：**「銅の鍵が必要」** など、未所持時専用トーストが表示されます。  
必要アイテム入手後に再接近すると、Eアクションが表示されます。

---

#### 🔹風見鶏（マップ移動ポイント）

フィールド上の **風見鶏** に近づくとマップ移動トーストが表示されます。

| 移動する | `Y` |
| 移動しない | `N` |

選択後、新しいマップの入口付近から探索が再開されます。

---

### 4️⃣ メニュー画面（ステータス／アイテム／セーブ／ロード）

| 操作内容    | キー（デフォルト）   | 説明               |
| ------- | ----------- | ---------------- |
| カーソル移動  | `↑` / `↓`   | メニュー内の項目を選択します。  |
| 決定      | `Enter`     | 開く・実行します。 |
| キャンセル   | `Esc` / `M` | メニューを閉じます。       |
| セーブ／ロード |  `←` / `→` / `Enter` | `←` / `→`でセーブ／ロードを選択`Enter`で実行  |
| 音量調整    | `←` / `→`   | 音量スライダーの値を変更します。 |

> セーブスロットは **3つ** あります（上書き可）。  
> 「追跡者」出現マップでは、セーブを行うことができません。

---

## 使用言語とライブラリ

### 使用言語
- **Python 3.12.5**

---

### 使用モジュール・ライブラリ

#### 標準モジュール（Python 標準ライブラリ）

* **sys**
* **math**
* **os**
* **copy**
* **traceback**
* **json**
* **pathlib**
* **dataclasses**
* **typing**
* **collections.deque / collections.abc**
* **time**
* **datetime**
* **functools**
* **io**

---

#### 外部ライブラリ

* **Pygame**
* **NumPy**
* **OpenCV（cv2）**

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
- Python [LICENSE-PSF.txt](./licenses/Python_LICENSE.txt)
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
  
- [Python license](https://docs.python.org/3/license.html)  
- またはフォルダ内の [LICENSE-PSF.txt](./licenses/Python_LICENSE.txt) をご確認ください。  

---

### このプロジェクトでは、以下のオープンソースライブラリを使用しています：

#### **Pygame**
- © 2000–2024 Pygame developers  

Pygameは、**GNU Lesser General Public License バージョン2.1 (LGPL v2.1)** の下でライセンスされています。  
 
詳細なライセンス条項については、以下を参照してください：  
- [Pygame License](https://github.com/pygame/pygame/blob/main/docs/LGPL.txt)  
- プロジェクト内の [LGPL_v2.1.txt](./licenses/third_party/LGPL_v2.1.txt)   

### NumPy

- **ライセンス**：BSD 3-Clause License（通称："NumPy License"）  
- **著作権表示**：© 2005–2025 NumPy Developers. All rights reserved.  
- **ライセンス原文**：[https://github.com/numpy/numpy/blob/main/LICENSE.txt](https://github.com/numpy/numpy/blob/main/LICENSE.txt)  
- **公式サイト**：[https://numpy.org](https://numpy.org)  
- **GitHub**：[https://github.com/numpy/numpy](https://github.com/numpy/numpy)

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

今回使用しているバージョンは以下の通りです：  
**OpenSSL 3.4.0**  
このバージョンは**Apache License 2.0**に基づいて配布されています。
- Copyright (c) 1998-2025 The OpenSSL Project Authors  
- Copyright (c) 1995-1998 Eric A. Young, Tim J. Hudson  
- All rights reserved.  

詳しくは以下をご確認ください：  
- [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)  

---

#### **Cython** 
このプロジェクトの実行ファイルは、Cythonを使用して難読化を行っています。  
- Cython © 2007-2025 The Cython Project Developers  
- Licensed under the Apache License 2.0.  
- [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)  

---

#### PyInstaller  
このプロジェクトは、**PyInstaller** を使用して実行ファイル化に対応しています。  
PyInstaller は GNU GPL ライセンスですが、例外規定により  
**生成される実行ファイル自体は GPL の制約を受けません**。  
- **著作権表示：**  
  ```
  Copyright (c) 2010–2023, PyInstaller Development Team  
  Copyright (c) 2005–2009, Giovanni Bajo  
  Based on previous work under copyright (c) 2002 McMillan Enterprises, Inc.
  ```

####  詳細情報へのリンク

- [PyInstallerのライセンス文書（GitHub）](https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt)  
- [PyInstaller公式サイト](https://pyinstaller.org/en/v6.13.0/index.html)  

---

## 使用フォントについて

このゲームでは、"Noto Sans JP"フォントファミリー（NotoSansJP-Regular.otf）を使用しています。  

- **Noto Sans JP**  
  - © 2014-2025 Google LLC  
  - SIL Open Font License, Version 1.1   

詳しくは以下をご確認ください：  
- [OFL.txt](./licenses/third_party/OFL.txt)  

---

これらのプロジェクトの開発者および貢献者の皆様に、心より感謝申し上げます。

---

## 使用音源

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

（敬称略）  

---

これらの素晴らしい音源を提供してくださった制作者および貢献者の皆様に、心より感謝申し上げます。  

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

