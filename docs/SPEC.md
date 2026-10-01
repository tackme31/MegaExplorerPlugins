# WD Tagger プラグイン 仕様

> **状態（2026-10-02）**: 機能を詰めている段階。§1 は決定、§2 は MEGA 側の制約、§3 は処理の流れ、§4 は未決（選択肢と推奨つき）、§5 は
> このプラグインを作るのに MegaExplorer 側のプラグイン基盤で足りないもの。未決が決まったら §1 に移す。

WD14 系のタグ付けモデル（ONNX）で MEGA 上の画像・動画を推論し、結果を MEGA のノードタグとして
付けるプラグイン。推論部分は以前作ったローカル用タグ付けツール（`ImagePreprocessor` / `TagModel`）を
移植する。

## 1. 決定事項

- コンテキストメニューに 2 コマンド（表示は英語）
  - ファイルを右クリック: **Tag this item**
  - フォルダを右クリック: **Tag everything in this folder**（配下を再帰的に）
- 対象は画像と動画。**`items.fetchPreview` でプレビューが取れないものは対象外**（スキップ）
  - 動画もプレビュー（MEGA が持つ代表フレームの JPEG）で推論する。動画をダウンロードして
    フレームを抜く、ということはしない
- 実行すると推論し、結果をアイテムのタグに設定する
- 何件設定するかは要検証。§2 の上限があるので §4-1 で決める

## 2. 前提となる MEGA 側の制約（SDK v10.17.0 で確認）

| 制約 | 値 | 出典 |
| --- | --- | --- |
| 1 ノードあたりのタグ数 | **最大 10**（超えると `API_ETOOMANY`） | `MegaClient::MAX_NUMBER_TAGS` |
| タグ全体の長さ | `,` 区切りで連結して **3000 バイト以内** | `MegaClient::MAX_TAGS_SIZE` |
| 使えない文字 | `,`（区切り文字） | `megaapi.h` `addNodeTag` |
| 重複判定 | 大文字小文字・アクセントを無視 | `getTagPosition` |
| description の長さ | 3000 バイト以内 | `MAX_NODE_DESCRIPTION_SIZE` |

**10 個という上限は、ユーザーが手で付けたタグと共有になる。**WD のモデルは一般タグだけで 20〜40 個は
平気で出すので、「推論結果を全部タグにする」はそもそもできない。

## 3. 処理の流れ（案）

```
command "tag-item" / "tag-folder":
    targets = 選択アイテム                       # tag-folder なら配下を再帰列挙してファイルだけ
    targets = [t for t in targets if 拡張子が画像/動画]      # §4-4
    progress(0, len(targets))
    model = load_model()                          # 初回はダウンロード（§4-6）
    for item in targets:
        check_cancelled()
        try:
            jpg = fetch_preview(item)             # NoPreview → skip
        except NoPreview: skipped += 1; continue
        scores = model.predict(jpg); delete jpg
        tags = select_tags(scores, item.tags)     # §4-1, §4-2, §4-3
        update(item, tags_add=..., tags_remove=...)
        progress(i, len(targets))
    return "Tagged N, skipped M (no preview), failed K"
```

## 4. 未決事項

### 4-1. 何件付けるか ― 10 枠の配分

- 案 A: 「10 − 既存のユーザータグ数」を上限に、スコア上位から埋める
- 案 B: プラグインが使う枠を固定（例: 最大 7 個）し、ユーザー用に 3 枠は空けておく
- 案 C: タグには上位数件だけを付け、閾値を超えたものは全部 description に書く（検索用）
  - description はユーザーのメモ欄と共有なので、上書きしてよいかという問題がある

推奨: **B**。結果が予測しやすい。C は、MegaExplorer の検索が description を対象にするかどうか次第。

### 4-2. 再実行したときの扱い

MEGA のタグには「誰が付けたか」が残らない。そのため、何もしないとプラグインが付けたタグと
ユーザーのタグを区別できず、再実行のたびに古い推論タグが溜まって枠を食う。

- 案 A: プラグインのタグにプレフィックスを付ける（例: `wd:long_hair`）。付いているものを消してから付け直す
- 案 B: 付けたタグをプラグイン側のローカル記録（handle → tags）に残す。別の PC からでは分からない
- 案 C: 既に推論タグがあるアイテムはスキップする（上書きオプションは別コマンドにする）

推奨: **A**（再実行で置き換え）に、C のスキップを足す。プレフィックスは文字数を食うが、3000 バイトの
上限には遠い。

### 4-3. どのタグを・どんな表記で付けるか

- カテゴリ: general / character / rating のどれを入れるか。rating（`general`/`sensitive`/
  `questionable`/`explicit`）は 1 枠で済み、絞り込みに便利
- 表記: WD の生のタグ（`long_hair`、`hatsune_miku_(vocaloid)`）か、`_` を空白に置き換えるか
- 閾値: 旧ツールの既定値は general 0.30 / character 0.50 / rating 0.40。ただし枠が 10 しかないので、
  実際には閾値よりも「上位 N 件」のほうが効く

### 4-4. 画像・動画の判定

ItemRef にあるのは `name`/`type`（file/folder）だけで、種別は分からない。かといって
`fetchPreview` が成功するかどうかで決めると、PDF などプレビューを持つ非画像も推論してしまう。

- 案 A: プラグイン側で拡張子リストを持つ（旧ツールのリストを流用）
- 案 B: アプリが ItemRef に種別（`kind: image|video|audio|document|…`）を載せる（→ §5-3）

推奨: まず **A**。B は汎用的に役立つので、基盤の改善候補として残す。

### 4-5. 大きいフォルダ

- 数千件を想定する。進捗（`ui.progress`）とキャンセルは必須
- アイテム単位のエラー（プレビュー取得や更新の失敗）では止めず、数えて最後にまとめて報告する
- `fetchPreview` を 1 件ずつ待つと遅いかもしれない。先読み（パイプライン化）は計測してから決める

### 4-6. モデルと実行環境

- モデル: 旧ツールの既定は `SmilingWolf/wd-eva02-large-tagger-v3`（約 1.2 GB）。初回の実行で
  Hugging Face から取得する。その間も進捗を出す（ダウンロード中は不定、のような表示）
- 置き場所は HF のキャッシュ（`~/.cache/huggingface`）のままでよいか
- GPU（CUDA）が使えなければ CPU で動かす。CUDA を読めなかったら警告を出す
- 設定（モデル・閾値・件数）はプラグイン自身が持つ。アプリは場所を決めない（v1 の方針どおり）。
  プラグインフォルダの `config.json` を想定

## 5. プラグイン基盤（MegaExplorer 側）への宿題

このプラグインを作るのに今の基盤で足りないもの。直すのは本体リポジトリの `feature/plugin-v1` で行う。

| # | 内容 | 必須度 | 現状 |
| --- | --- | --- | --- |
| 5-1 | **ファイルとフォルダでメニューを出し分ける**（manifest の `when` など） | 必須（§1 の 2 コマンド） | 未実装。今は全コマンドがファイルにもフォルダにも出る |
| 5-2 | フォルダ配下の再帰列挙（`items.descendants`） | あれば楽 | 未実装。`items.children` を再帰で呼べば代わりになる |
| 5-3 | ItemRef / items.get に種別（`kind`）を載せる | 任意（§4-4） | なし |
| 5-4 | 結果の詳細表示（スキップ・失敗の一覧） | 任意 | トーストの 1 行だけ |
| 5-5 | タグの一致判定を SDK に合わせる（大文字小文字・アクセントを無視） | 推奨 | アプリの事前チェック（`PluginHostApi::itemsUpdate`）は完全一致で比べている。SDK と食い違うので、`Long_Hair` があるところへ `long_hair` を add すると SDK が `API_EEXIST` を返して -32010 になり、remove は「無い」と判断されて黙って何もしない |
| 5-6 | 10 個の上限に当たったときのエラーを、-32010 以外の分かる形で返すか | 要確認 | `API_ETOOMANY` は今 -32010（MegaError）として返る |
| 5-7 | **items.update でタグの remove を add より先に実行する** | 必須（§4-2 の置き換え） | 今の実行順は add → remove。10 個埋まっているアイテムで推論タグを付け替えると、add の時点で `API_ETOOMANY` になり、何も消えないまま途中で止まる |
