---
name: release
description: >-
  Cut a release of one plugin in this repository (dirstat or wdtagger): pick
  the next version from what changed in that plugin's folder since its last
  tag, write English release notes, bump plugin.json, build, pack the zip into
  dist/, unpack it and check it runs, then tag. Nothing is pushed or uploaded --
  publishing the zip is done by hand. `/release dirstat` or
  `/release wdtagger 0.2.0`; with no plugin given it asks. Stops for approval
  once, on the version and the notes. Use only when cutting a release.
---

# /release — プラグインのリリースを 1 本切る

引数は `<plugin> [X.Y.Z]`。`<plugin>` は `dirstat` か `wdtagger`。版は省略可で、省略時は 1. で
自分で決める（`v` 付きなら剥がす）。プラグイン名が無ければ、前回タグ以降にフォルダへ変更の
あるプラグインを並べて `AskUserQuestion` で聞く。**人間が対話的に走らせるコマンド**で、
サブエージェントには出さない。

止まるのは **版とリリース文の承認（2.）の 1 箇所だけ**。それ以外は失敗しない限り進む。

**このスキルは何も push せず、何もアップロードしない。** このリポジトリは push しない決まりで
（`CLAUDE.md`）、リリースは zip を人間が手で公開する。スキルの成果物は `dist/` の zip と
リリース文、それにローカルのタグまで。本番のプラグインフォルダへのインストールもしない。

| `<plugin>` | フォルダ | 表示名 | タグ | zip |
| --- | --- | --- | --- | --- |
| `dirstat` | `dirstat_plugin/` | MegaDirStat | `dirstat-vX.Y.Z` | `dist/MegaDirStat-X.Y.Z.zip` |
| `wdtagger` | `wdtagger_plugin/` | WD Tagger | `wdtagger-vX.Y.Z` | `dist/WDTagger-X.Y.Z.zip` |

zip の中は `<plugin>/` 1 段で始める（`dirstat/plugin.json` …）。README の「Installation」が
示す `plugins\dirstat\plugin.json` という配置に、展開するだけでなるようにするため。

## 0. 前提確認（1 つでも欠けたら、何もせずに理由を言って終わる）

```
git rev-parse --abbrev-ref HEAD               # main であること
git status --porcelain                        # 空であること
git describe --tags --abbrev=0 --match '<plugin>-v*'   # 前回のタグ（無ければ初回）
git log --oneline <前回タグ>..HEAD -- <フォルダ>/        # 1 件以上であること（初回は不問）
```

- 前回タグ以降、そのフォルダに変更が無ければ出すものが無いので終わる。
- 変更が README・`docs/`・テストだけなら、それも出す理由にならない。そう言って、出すかを聞く。
- テストを通す。落ちたらそこで中断:
  - dirstat: `C:/Qt/Tools/CMake_64/bin/cmake.exe --preset msvc` →
    `--build --preset debug` → `C:/Qt/Tools/CMake_64/bin/ctest.exe --preset debug`。
    **自前の警告が 1 本でも出たら中断**（`/W4` で警告ゼロが前提）。
  - wdtagger: `uv run python -m unittest`（`wdtagger_plugin/` で）。

## 1. 次のバージョンを決める

引数で渡されていればそれを使う。**初回（前回タグが無い）なら `plugin.json` の今の版をそのまま
出す**——版上げはしない。それ以外は、前回タグ以降のそのフォルダのコミットから決める。人間に
聞かない（2. の承認で一緒に目に入る）。

```
git log <前回タグ>..HEAD --format='%h %s%n%b%n---' -- <フォルダ>/
```

| 前回タグ以降に入ったもの | 次の版 |
| --- | --- |
| ユーザーにできることが増えた（新しいコマンド、新しい表示、新しい設定キー） | MINOR（`0.1.3` → `0.2.0`） |
| 直しと改善だけ | PATCH（`0.1.0` → `0.1.1`） |

- 判断の基準は利用者から見た違い。リファクタ・テスト・README の書き直しは数えない。
- `plugin.json` の `permissions` が増えたら MINOR、と扱う——利用者がアプリで許可を出し直す
  ことになるから。
- MAJOR は人間が明示的に指示したときだけ。

版が決まったら重複を確認する。埋まっていたら中断:

```
git tag -l <plugin>-vX.Y.Z               # 空であること
ls dist/<zip 名>                         # 無いこと（あれば前回の残骸。消すか聞く）
```

## 2. リリース文を書く（承認）

**英語**、利用者視点。公開先のリリースページに出るもの。材料は 1. の `git log`。

- 冒頭 1 行で「何のリリースか」。初回は機能を 2〜3 行で紹介する（README の冒頭が材料）。
- 見出しは中身のあるものだけ: `### New features` / `### Improvements` / `### Bug fixes`。
- **コミットを 1 行ずつ並べない。** 一つの機能に付随する細部はその機能の 1 行に畳む。
  箇条書きが全部で 5 行を超えたら畳み方を疑う。気づかれないような細かい修正は、本当に有る
  ときだけ "Fixed several other minor issues." の 1 行にまとめる。
- 内部の設計判断・リファクタ・テスト・ドキュメント更新は書かない。
- **このマシンや利用者のアカウントに固有のことを書かない**（ローカルパス、フォルダ名、
  アカウント名、使用量の数字）——`CLAUDE.md`「Writing docs and commits」。
- 末尾に動作要件の 1 行。数字はその場で確かめたものを書く:
  - dirstat: 必要なのは MEGA Explorer だけ（Qt と MSVC ランタイムは同梱）。Qt の版は
    `dirstat_plugin/CMakePresets.json` から。
  - wdtagger: NVIDIA GPU + CUDA 12 + cuDNN 9、uv、初回の `uv sync`（README の
    「Installation」と食い違わないこと）。
- `plugin.json` の `apiVersion` と、必要な MEGA Explorer 側の機能が前回から変わったなら
  その旨を 1 行。

`dist/release-notes-<plugin>-X.Y.Z.md` に書き（`dist/` は gitignore 済み）、**書いた文面を
ターミナルにも全文出す**。直したときも省略せず全文を出し直し、何を変えたかを 1 行添える。
そのうえで **`AskUserQuestion` で「この版・この文面で進む / 直す / 中止」** を聞く。版を
変えると言われたらそれに従う。

## 3. 版を上げてコミット

初回（版上げなし）ならこの節は飛ばす。

- dirstat: `dirstat_plugin/plugin.json` の `"version"` だけ。版の在処はそこだけ。
- wdtagger: `wdtagger_plugin/plugin.json` の `"version"` と `pyproject.toml` の `version`。
  そのあと `uv lock`（`wdtagger_plugin/` で）を回して `uv.lock` の版を追従させる。
  **`git diff` で、`uv.lock` の差分が自分のパッケージの版 1 行だけか見る。** 依存の版が
  動いていたら止まって理由を確かめる——リリースで依存を上げるのは別の作業。
  wdtagger のファイルは CRLF と LF が混在している。各ファイルの改行を保つこと
  （`git diff --stat` で全行差分になっていないか見る）。

```
git add <変えたファイルを名指しで>
git commit    # Subject: Bump MegaDirStat to X.Y.Z  /  Bump WD Tagger to X.Y.Z
```

本文は 1 行で足りる。trailer はこのリポジトリの他のコミットに合わせる。

## 4. ビルドして zip を作る

zip に入れるのは**コミット済みの中身**と（dirstat なら）`deploy.ps1` の出力だけ。作業木から
拾わない——`.venv` や `__pycache__`、`*.stackdump` が紛れ込む。

**dirstat:**

```
pwsh dirstat_plugin/scripts/deploy.ps1          # Release。-Config Debug は絶対に付けない
```

これで `dirstat_plugin/bin/` が Release の exe と Qt・MSVC ランタイムの DLL で作り直される
（起動中のプラグインは止められる）。zip の中身は `plugin.json`・`LICENSE`・`README.md`
（`git archive HEAD` から）＋ `bin/` 全体。ソース・テスト・CMake ファイルは入れない。

**wdtagger:**

```
git archive --format=zip --prefix=wdtagger/ -o dist/WDTagger-X.Y.Z.zip \
    HEAD:wdtagger_plugin -- . ':!test_*.py' ':!docs' ':!.gitignore'
```

実行時の `.py` 全部・`plugin.json`・`pyproject.toml`・`uv.lock`・`.python-version`・
`LICENSE`・`README.md` が入る。除外をパターンにしてあるのは、新しいモジュールを足したときに
入れ忘れないため。

dirstat は一時ディレクトリに `dirstat/` を組み立てて `Compress-Archive` で固める
（フォルダごと渡すと `dirstat/` が 1 段目になる）:

```powershell
$ver = 'X.Y.Z'
$stage = Join-Path $env:TEMP "plugin-release-dirstat-$ver"
Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force "$stage/dirstat" | Out-Null
git archive --format=tar HEAD:dirstat_plugin plugin.json LICENSE README.md | tar -x -C "$stage/dirstat"
Copy-Item -Recurse dirstat_plugin/bin "$stage/dirstat/bin"
New-Item -ItemType Directory -Force dist | Out-Null
Compress-Archive -Path "$stage/dirstat" -DestinationPath "dist/MegaDirStat-$ver.zip"
```

## 5. zip を展開して確かめる

確認対象は**展開した zip**。ビルド木や作業フォルダで代用しない。

```powershell
$dest = Join-Path $env:TEMP "plugin-release-check-<plugin>-$ver"
Remove-Item -Recurse -Force $dest -ErrorAction SilentlyContinue
Expand-Archive -LiteralPath <zip> -DestinationPath $dest
```

両方に共通:

- 1 段目が `<plugin>/` だけで、その直下に `plugin.json` があること。
- その `plugin.json` の `version` が X.Y.Z であること。
- 余計なものが無いこと: `.venv`・`__pycache__`・`*.pyc`・`*.pdb`・`*.stackdump`・`build/`・
  テスト・`docs/`。

**dirstat** — Qt の無いマシンで動くかを見る:

- `run.command`（`bin/MegaDirStatPlugin.exe`）が存在すること。
- デバッグ版の DLL が無いこと（`Qt6*d.dll`、`*140d.dll`、`ucrtbased.dll`）——デバッグ CRT は
  再配布できない。
- `dirstat_plugin/tests/test_protocol.py` を、**展開した exe に向けて**、Qt の `bin` を
  `PATH` から外した環境で走らせる。`QT_QPA_PLATFORM=offscreen`、
  `MEGADIRSTAT_PLUGIN_EXE=<展開先>\dirstat\bin\MegaDirStatPlugin.exe`、カレントは
  `dirstat_plugin/tests`、`python -m unittest -v test_protocol`。**skip が出たら成功扱いに
  しない**（exe のパスが違っている）。

**wdtagger** — GPU 推論までは確かめない（それは人間がアプリで試す）:

- 展開先で `uv lock --check`——`pyproject.toml` と `uv.lock` が食い違っていないこと。
- 展開先で `uv run --no-project python -m py_compile <全 .py>`——同梱の `.py` が全部揃って
  構文が通ること。`main.py` が import するモジュールが zip に全部あるかも目で見る。

落ちたら原因を直す。zip の作り方の問題なら 4. からやり直す。コードの問題なら、版上げ
コミットを 8. の手順で戻してから直し、`/release` をやり直す。

## 6. タグを打つ

5. が通ってから。注釈付きで、HEAD（3. の版上げコミット、初回なら今の HEAD）に打つ。

```
git tag -a <plugin>-vX.Y.Z
```

注釈は「`MegaDirStat X.Y.Z`」（または `WD Tagger X.Y.Z`）＋空行＋リリース文の要約 2〜3 行
＋ zip 名。英語。**push しない。**

## 7. 後片付けと報告

一時ディレクトリ（`plugin-release-*`）を消す。`dirstat_plugin/bin/` は残す——dev プロファイルの
ジャンクションが今もそれを起動するので、消すとプラグインが動かなくなる。

報告は数行: zip のパスとサイズ、リリース文のパス、タグ名、含まれるコミット数。最後に
**人間がやること**を書く: リリースページで新しいリリースを作り、リリース文を本文に貼り、
zip を添付する。本番フォルダへの入れ替えは頼まれたときだけ。

## 8. 途中で落ちたとき / 中止のとき

全部ローカルなので戻せる。**戻す操作は破壊的なので、実行前に何をするか見せて確認を取る。**

```
git tag -d <plugin>-vX.Y.Z      # 6. まで進んでいたら
git reset --hard HEAD~1         # 3. の版上げコミットを捨てるとき（HEAD がそれであることを先に見る）
```

`dist/` の zip とリリース文は消すか残すか聞く。

## 禁止事項

- **承認の前にコミットもタグもしない。** 5. が通る前にタグを打たない。
- push しない、リリースページへ上げない、本番のプラグインフォルダを触らない。
- `deploy.ps1 -Config Debug` の `bin/` を zip にしない。
- 作業木を丸ごと zip にしない（コミット済みの中身 ＋ `bin/` だけ）。
- リリースで依存の版を上げない（`uv.lock` の差分は自分の版 1 行だけ）。
- リリース文にコミットを 1 行ずつ並べない。
