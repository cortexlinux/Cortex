# 実装計画: スマートクリーンアップとディスクスペース最適化

## 目標
不要なファイル（パッケージキャッシュ、orphanパッケージ、ログ、一時ファイル）をインテリジェントに削除し、ディスク使用量を最適化する機能を追加する。

## ユーザーレビューが必要な事項
- `apt-get autoremove` などのコマンドを実行するため、sudo権限が必要になる場合がある。現状のCortexの権限モデルに従い、コマンド生成時に `sudo` を付与するか、ユーザーが `sudo cortex` で実行することを前提とするか確認が必要。（現状 `packages.py` は `apt install` を生成しており、sudoを含んでいないため、ユーザーが特権で実行するか、実行時にsudoが必要になる）
- 安全第一のため、デフォルトでは確認を求めるか、`scan` モードを推奨する。

## 提案する変更

### `cortex/packages.py`
- `PackageManager` クラスに以下のメソッドを追加:
    - `get_cleanable_items()`: キャッシュサイズや不要パッケージのリストを取得。
    - `get_cleanup_commands()`: 実際にクリーンアップを行うコマンドを生成。

### `cortex/optimizer.py` (新規作成)
- `DiskOptimizer` クラス:
    - `scan()`: システム全体のスキャンを統括し、`CleanupOpportunity`（種別、サイズ、説明）のリストを返す。
    - `clean(opportunities)`: クリーンアップを実行。**重要なファイルのバックアップを作成し、Undo可能にする。**
    - `compress_logs()`: `/var/log` 内の古いログを圧縮。
    - `restore(cleanup_id)`: クリーンアップ操作を元に戻す（バックアップからの復元、パッケージの再インストール）。
    - `schedule_cleanup(frequency)`: cron/systemdタイマーを用いた自動実行の設定。

### `cortex/cli.py`
- `cleanup` コマンドハンドラの追加。
    - `scan`: 診断と見積もり。
    - `run`: 実行（`--safe`でバックアップ必須、デフォルトで有効）。
    - `schedule`: 自動実行スケジュールの設定（例: `cortex cleanup schedule --daily`）。
    - `undo`: 直前のクリーンアップを取り消す。


## 検証計画

### 自動テスト
- `tests/test_optimizer.py` を作成。
    - `scan` メソッドがパッケージマネージャーやファイルシステムから情報を収集するロジックをテスト（モックを使用）。
    - ログ圧縮機能が正しいファイルを対象にするかテスト。

### 手動検証手順
1. `cortex cleanup scan` を実行し、エラーなく結果が表示されるか確認。
2. `cortex cleanup run --dry-run` (もし実装すれば) または `run` で実行されるコマンドを確認。
3. 実際に `cortex cleanup run` を実行し、ディスク空き容量が増えるか確認。
