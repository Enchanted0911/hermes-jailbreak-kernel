# ⚔️ hermes-jailbreak-kernel — Hermes Agent 向けアーマー貫通カーネルプラグイン v1.7.2

<p align="center">
  <a href="https://github.com/Enchanted0911/hermes-jailbreak-kernel"><img src="https://img.shields.io/github/stars/Enchanted0911/hermes-jailbreak-kernel?style=for-the-badge&logo=github&label=Stars" alt="Stars" /></a>
  <a href="https://github.com/Enchanted0911/hermes-jailbreak-kernel/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Enchanted0911/hermes-jailbreak-kernel?style=for-the-badge&label=License" alt="License: MIT" /></a>
  <a href="https://github.com/Enchanted0911/hermes-jailbreak-kernel"><img src="https://img.shields.io/github/last-commit/Enchanted0911/hermes-jailbreak-kernel?style=for-the-badge&label=Last%20commit" alt="Last commit" /></a>
  <a href="https://hermes-agent.nousresearch.com/docs"><img src="https://img.shields.io/badge/Hermes%20Agent-🚀%20plugin-10B981?style=for-the-badge&logoColor=white" alt="Hermes Agent plugin" /></a>
</p>

<p align="center">
  <b>ワンラインインストール</b>：
  <code>hermes plugins install --enable Enchanted0911/hermes-jailbreak-kernel</code>
</p>

<p align="center">
  <b>他の言語で読む：</b>
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.ar.md">العربية</a>
</p>

**Nous Research Hermes Agent**（`~/.hermes`）向けのアーマー貫通（レッドチーム）システムプロンプト注入プラグイン。DSH プラグイン **[dsh-infinite-gen-4（無限四代 v0.4.0）](https://github.com/Minglink/dsh-infinite-gen-4)** からの移植版です。

> ⚠️ **許可された用途のみ。** 本プラグインは、許可されたテスト環境・ローカル合成ターゲット・コンプライアンスに沿ったレッドチーム研究専用です。無許可のターゲットに対して決して使用しないでください。利用者は各自の使用について全責任を負います。

## 目次

- [無限四代とのアーキテクチャ対比](#アーキテクチャ対比)
- [3層注入アーキテクチャ](#3層注入アーキテクチャ)
- [セッションローテーション](#セッションローテーション)
- [インストール](#インストール)
- [確認方法](#確認方法)
- [環境スイッチ](#環境スイッチ)
- [診断ダンプ](#診断ダンプ)
- [Hermes のハード制限](#hermes-のハード制限)
- [オフライン自己テスト](#オフライン自己テスト)

## アーキテクチャ対比

| dsh-infinite-gen-4 (v0.4.0) | hermes-jailbreak-kernel（本プラグイン） |
|---|---|
| `infinite-gen-4:global-system-prompt`（Order 100） | `hermes-jailbreak-kernel-core`（`after_memory` スロット） |
| `infinite-gen-4:dual-layer-reinforce`（Order 200） | `hermes-jailbreak-kernel-reinforce`（`after_memory` スロット、SHA256 は core と同一） |
| `DUAL_LAYER_INJECTION` スイッチ | `HERMES_JAILBREAK_DUAL=0` 単層フォールバック |
| ゼロツールサーフェス・純粋な直接出力 | 同様 — 機能ツールを一切登録しない |
| `infinite_gen4_profile` メタデータツール | `/jailbreak` ステータスコマンド |
| クライアントステータスバッジ（web half） | —（Hermes Desktop に後付け可能） |
| 注入面：システムプロンプトセクション | ネイティブ `register_system_prompt_section` |

カーネルペイロード（`prompts/`）は無限四代のテキストを逐語継承：`SUPREME DIRECTIVE — USER AUTHORITY`、`Output contract`（先頭行 `##`/```` ``` ```` で成果物を命名＋サイレント推論＋プレースホルダー自動生成）、`Task classes`（セキュリティ / LLM 研究 / 成人向けフィクション / その他 — 直接生成）、`[USER]/[OUTPUT]` few-shot アンカー。

## 3層注入アーキテクチャ

プラグインは **3層** でカーネルを注入します：

1. **プラグインセクション注入**（`after_memory` スロット、同一ソースの2セクション）— Hermes がシステムプロンプトを組み立てる際に書き込まれる；
2. **リクエスト層 system 再構築（replace モード）** — `llm_request` ミドルウェアが全リクエストの直前に最終 system を *メモリセクション + 実行環境 + カーネル* として書き換え、Hermes 自身のエージェントガイダンス／スキル索引スキャフォールドを破棄；
3. **opencode セッションローテーション**（下記）— `x-opencode-session` ヘッダーをローテーション。

ツールスキーマは影響を受けません。API の `tools` フィールドで運ばれるため、system テキストとは無関係です。

## セッションローテーション

ミドルウェアは `extra_headers["x-opencode-session"]` を書き換えます：各 Hermes セッションの最初のリクエストでローテーション済み ID を設定し、セッションの残りで再利用します。

| `HERMES_JAILBREAK_ROTATE_SESSION` | 挙動 |
|---|---|
| `once`（**デフォルト**） | セッションごとに1回ローテーションして再利用（ターン間でアップストリームのプロンプトキャッシュを維持） |
| `every` / `1` | リクエストごとに新しい ID（プロンプトキャッシュを破壊） |
| `0` / `off` | ローテーションなし（ヘッダーはそのまま） |

補助呼び出し（圧縮・タイトル生成など）は元の安定 ID のまま。

## インストール

```bash
# 方法1 — GitHub からワンラインインストール
hermes plugins install --enable Enchanted0911/hermes-jailbreak-kernel

# 方法2 — Hermes プラグインカタログから（コミュニティエントリがマージされた後）
hermes plugins install hermes-jailbreak-kernel

# 方法3 — ローカル開発ディレクトリ
cp -r ~/.hermes/plugins/hermes-jailbreak-kernel ~/.hermes/plugins/   # または git clone して plugins/ へ
hermes plugins enable hermes-jailbreak-kernel

# その後、ゲートウェイ／デスクトップアプリを再起動
hermes gateway restart
```

> ⚠️ Hermes プラグインは opt-in：インストール後 `hermes plugins enable hermes-jailbreak-kernel` で有効化（ワンライナーは `--enable` 済み）。

## 確認方法

```bash
# オフライン回帰（アンカー / 二層同一ソース SHA256 / 予算 / スイッチ）
cd ~/.hermes/plugins/hermes-jailbreak-kernel && python selftest.py

# セッション内確認（再起動後、新しいセッションで）
/jailbreak                     # カーネルバージョン、スロット、二重 SHA256、予算使用量
# または質問：システムプロンプトに含まれるプラグインセクションは？
# 「## Plugin Context: hermes-jailbreak-kernel-core / hermes-jailbreak-kernel-reinforce」が見えるはず
```

実行時ログの確認（`~/.hermes/logs/agent.log`）：

```
INFO hermes_plugins.hermes_jailbreak_kernel: injected system prompt section hermes-jailbreak-kernel-core (chars=3005)
INFO hermes_plugins.hermes_jailbreak_kernel: injected system prompt section hermes-jailbreak-kernel-reinforce (chars=3005)
INFO hermes_plugins.hermes_jailbreak_kernel: registered llm_request middleware (request-layer reinforce)
INFO hermes_plugins.hermes_jailbreak_kernel: hardened request system prompt (mode=replace ...)
INFO hermes_plugins.hermes_jailbreak_kernel: rotated x-opencode-session (...)
```

## 環境スイッチ

| 変数 | デフォルト | 効果 |
|---|---|---|
| `HERMES_JAILBREAK_DISABLE=1` | off | 登録を完全スキップ（キルスイッチ） |
| `HERMES_JAILBREAK_DUAL=0` | on | 単セクション注入（トークン節約、挙動は同等） |
| `HERMES_JAILBREAK_SYSTEM_MODE=replace\|append` | replace | リクエスト層 system 方針：再構築（スキャフォールド破棄）or カーネル追記のみ |
| `HERMES_JAILBREAK_ROTATE_SESSION=once\|every\|0` | once | opencode セッションローテーション方針（上記参照） |
| `HERMES_JAILBREAK_DUMP=1` | off | 全リクエストで診断ダンプ；デフォルトではセッションごとに1回 |

## 診断ダンプ

ミドルウェアは各リクエストの診断ビュー（デフォルトではセッションごとの初回、`HERMES_JAILBREAK_DUMP=1` で毎回）を `~/.hermes/plugins/hermes-jailbreak-kernel/dumps/request_*.json` に書き込みます：完全な system メッセージ＋他のメッセージの役割/長さ/先頭200文字＋model/provider/base_url。カーネルが system メッセージ末尾にあり、ルートが期待モデルに到達しているかを確認するために使います。ダンプはローカル限定で、`.gitignore` により公開されません。

## Hermes のハード制限

- プラグインセクション：各 ≤ 4000 文字、合計 ≤ 8000 文字（インジェクタは予算超過セクションを黙ってスキップ）。
- 固定位置 `after_memory`（人格とメモリの後）。レンダリング順はセクション ID の辞書順 → `core < reinforce`。
- セクション ID は小文字英数字/`.`/`_`/`-` のみ。
- リクエスト層の再構築はプラグインセクション予算に縛られない（リクエスト時にミドルウェア内で実行）。

## オフライン自己テスト

```bash
cd ~/.hermes/plugins/hermes-jailbreak-kernel
python selftest.py          # ✅/❌ アサーション単位（54 項目）
python selftest.py --json
```

## ローカライゼーション

`/jailbreak` の UI 文字列（コマンド説明とステータスレポート）は Hermes の
[`agent/i18n`](https://github.com/NousResearch/hermes-agent/blob/main/agent/i18n.py) 標準に従います：言語解決は `HERMES_LANGUAGE` >
`config.yaml` の `display.language` > 英語 の順。プラグインは
`locales/en.yaml`（デフォルト）と `locales/zh.yaml` を同梱。他の言語および
欠損キーは英語、さらにキー名そのものへフォールバックします。ログと注入
カーネル本体は設計上言語中立です。

## ライセンス

MIT — [LICENSE](LICENSE) を参照。[dsh-infinite-gen-4](https://github.com/Minglink/dsh-infinite-gen-4)（MIT, Minglink）の Hermes Agent プラグインプラットフォーム向け移植・翻案。