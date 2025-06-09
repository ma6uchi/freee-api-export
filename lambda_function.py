import json
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# 各ファイルから必要な関数をインポート
from get_tokens import refresh_freee_tokens
from get_workloads import get_all_freee_workloads
from get_projects import get_all_freee_projects, create_project_lookup
from process_workloads_to_csv import process_workloads_to_csv_data, write_to_csv

# .env ファイルを読み込む
load_dotenv()

def main():
    """
    freee APIから工数データを取得し、CSVとしてエクスポートするメイン処理
    """
    print("--- freee 工数データエクスポート処理を開始します ---")

    # 環境変数の読み込み
    client_id = os.getenv("FREEE_CLIENT_ID")
    client_secret = os.getenv("FREEE_CLIENT_SECRET")
    company_id = os.getenv("FREEE_COMPANY_ID")

    if not client_id or not client_secret or not company_id:
        print("エラー: .env ファイルに CLIENT_ID, CLIENT_SECRET, または COMPANY_ID が設定されていません。")
        print("処理を終了します。")
        return

    try:
        # COMPANY_ID は文字列として取得されるのでintに変換
        company_id = int(company_id)
    except ValueError:
        print("エラー: COMPANY_ID が有効な数値ではありません。")
        print("処理を終了します。")
        return

    # 1. アクセストークンを更新 (または初回取得)
    access_token, _ = refresh_freee_tokens()
    if not access_token:
        print("アクセストークンの取得に失敗しました。処理を終了します。")
        return

    # 2. エクスポート対象年月を決定 (例: 先月)
    # Lambdaで月次実行することを想定し、常に「先月」のデータを対象とします。
    today = datetime.now()
    # 今月の1日を取得
    first_day_of_current_month = today.replace(day=1)
    # 先月の最終日を取得 (今月の1日から1日引く)
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
    # 先月のYYYY-MM形式を取得
    target_year_month = last_day_of_previous_month.strftime("%Y-%m")

    print(f"\nエクスポート対象年月: {target_year_month}")

    # 3. 全プロジェクト情報を取得
    all_projects = get_all_freee_projects(access_token, company_id)
    if all_projects is None: # Noneが返された場合はエラー
        print("プロジェクト情報の取得に失敗しました。処理を終了します。")
        return

    # プロジェクトルックアップ辞書を作成
    project_lookup = create_project_lookup(all_projects)

    # 4. 全工数実績データを取得
    all_workloads = get_all_freee_workloads(access_token, company_id, target_year_month)
    if all_workloads is None: # Noneが返された場合はエラー
        print("工数実績データの取得に失敗しました。処理を終了します。")
        return

    # 5. 工数実績データを整形・集計してCSV用のデータを作成
    print("\n工数実績データを整形・集計しています...")
    final_csv_data = process_workloads_to_csv_data(all_workloads, project_lookup)

    if not final_csv_data:
        print(f"対象年月 ({target_year_month}) のCSVデータが生成されませんでした。")
        return

    # 6. CSVファイルに書き出し
    # CSVファイル名に年月を含める
    csv_filename = f"freee_workloads_summary_{target_year_month}.csv"
    write_to_csv(final_csv_data, csv_filename)

    print("\n--- freee 工数データエクスポート処理が完了しました ---")

def lambda_handler(event, context):
    """
    Lambda関数が呼び出されたときに実行されるエントリポイント
    """
    print("--- Lambda関数実行開始 ---")

    # main()関数を実行
    main()

    print("--- Lambda関数実行終了 ---")
    return {
        'statusCode': 200,
        'body': json.dumps('処理が正常に完了しました')
    }

if __name__ == "__main__":
    main(0, 0)