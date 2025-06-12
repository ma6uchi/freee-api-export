import json
import os
from datetime import datetime, timedelta, date
import boto3

# 各ファイルから必要な関数をインポート
from get_tokens import refresh_freee_tokens_with_secrets_manager
from get_workloads import get_all_freee_workloads
from get_projects import get_all_freee_projects, create_project_lookup
from process_workloads_to_csv import process_workloads_to_csv_data, write_to_csv_to_google_drive 

secrets_client = boto3.client('secretsmanager')

SECRETS_NAME = os.environ.get("FREEE_SECRETS_NAME")
# Google DriveのフォルダIDをLambda環境変数で設定
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
# サービスアカウントの認証情報JSONをSecrets Managerから取得するため、そのシークレット名
GOOGLE_SERVICE_ACCOUNT_SECRETS_NAME = os.environ.get("GOOGLE_SERVICE_ACCOUNT_SECRETS_NAME")

def get_freee_credentials():
    """
    AWS Secrets Manager から freee の認証情報を取得する
    """
    if not SECRETS_NAME:
        raise ValueError("環境変数 FREEE_SECRETS_NAME が設定されていません。")

    try:
        get_secret_value_response = secrets_client.get_secret_value(SecretId=SECRETS_NAME)
    except Exception as e:
        print(f"Secrets Manager からシークレット '{SECRETS_NAME}' の取得に失敗しました: {e}")
        raise # エラーを再スローしてLambdaの実行を中断

    if 'SecretString' in get_secret_value_response:
        secret = json.loads(get_secret_value_response['SecretString'])
        return secret
    else:
        # バイナリシークレットの場合の処理（今回はJSONなので通常は使わない）
        raise ValueError("Secrets Manager のシークレットが期待される JSON 形式ではありません。")

def get_google_service_account_json():
    """
    AWS Secrets Manager から Google サービスアカウントの認証情報JSONを取得する
    """
    if not GOOGLE_SERVICE_ACCOUNT_SECRETS_NAME:
        raise ValueError("環境変数 GOOGLE_SERVICE_ACCOUNT_SECRETS_NAME が設定されていません。")

    try:
        get_secret_value_response = secrets_client.get_secret_value(SecretId=GOOGLE_SERVICE_ACCOUNT_SECRETS_NAME)
        # SecretStringにはサービスアカウントのJSONがそのまま文字列として入っている想定
        return get_secret_value_response['SecretString']
    except Exception as e:
        print(f"Secrets Manager からシークレット '{GOOGLE_SERVICE_ACCOUNT_SECRETS_NAME}' の取得に失敗しました: {e}")
        raise # エラーを再スロー

def lambda_handler(event, context):
    print("--- Lambda関数実行開始 ---")
    export_type = event.get('export_type', 'unknown') 
    print(f"実行タイプ: {export_type}")


    try:
        # Secrets Manager から freee 認証情報を取得
        freee_credentials = get_freee_credentials()
        client_id = freee_credentials.get("client_id")
        client_secret = freee_credentials.get("client_secret")
        company_id = freee_credentials.get("company_id")

        if not client_id or not client_secret or not company_id:
            raise ValueError("Secrets Manager から freee 認証情報が不足しています。")

        try:
            company_id = int(company_id)
        except ValueError:
            raise ValueError(f"COMPANY_ID '{company_id}' が有効な数値ではありません。")

        # Secrets Manager から Google サービスアカウント認証情報を取得
        service_account_info_json = get_google_service_account_json()
        if not service_account_info_json:
            raise ValueError("Google サービスアカウント認証情報が取得できませんでした。")

        if not GOOGLE_DRIVE_FOLDER_ID:
            raise ValueError("Lambda環境変数 GOOGLE_DRIVE_FOLDER_ID が設定されていません。")

        # 1. アクセストークンを更新
        access_token, new_refresh_token = refresh_freee_tokens_with_secrets_manager(
            client_id, client_secret, SECRETS_NAME
        )
        if not access_token:
            print("アクセストークンの取得に失敗しました。処理を終了します。")
            return {
                'statusCode': 500,
                'body': json.dumps('アクセストークン取得失敗')
            }

        # 2. エクスポート対象期間の決定ロジックを分岐
        target_csv_filename_prefix = "freee_workloads_summary"
        
        # APIに渡す year_month を計算
        target_api_year_month = None 
        # ファイル名に含める期間情報
        file_period_info = ""
        
        today_date = date.today()

        if export_type == 'monthly':
            # 月次実行の場合: 前月全体を対象
            first_day_of_current_month = today_date.replace(day=1)
            last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
            
            target_api_year_month = last_day_of_previous_month.strftime("%Y-%m")
            file_period_info = f"{target_api_year_month}_monthly" # ファイル名を明確に
            print(f"\n月次エクスポート対象年月 (前月全体): {target_api_year_month}")
            
        elif export_type == 'weekly':
            # 週次実行の場合: 現在の月全体を対象
            target_api_year_month = today_date.strftime("%Y-%m")
            file_period_info = f"{target_api_year_month}_weekly" # ファイル名を明確に
            print(f"\n週次エクスポート対象年月 (現在の月全体): {target_api_year_month}")
            
        else:
            raise ValueError("EventBridgeからの呼び出しタイプが不明です。'monthly' または 'weekly' を指定してください。")

        # 3. 全プロジェクト情報を取得
        all_projects = get_all_freee_projects(access_token, company_id)
        if all_projects is None:
            print("プロジェクト情報の取得に失敗しました。処理を終了します。")
            return {
                'statusCode': 500,
                'body': json.dumps('プロジェクト情報取得失敗')
            }
        project_lookup = create_project_lookup(all_projects)

        # 4. 全工数実績データを取得
        all_workloads = get_all_freee_workloads(access_token, company_id, target_api_year_month)
        if all_workloads is None:
            print("工数実績データの取得に失敗しました。処理を終了します。")
            return {
                'statusCode': 500,
                'body': json.dumps('工数実績データ取得失敗')
            }

        # 5. 工数実績データを整形・集計してCSV用のデータを作成
        print("\n工数実績データを整形・集計しています...")
        final_csv_data = process_workloads_to_csv_data(all_workloads, project_lookup)

        if not final_csv_data:
            print(f"対象年月 ({target_api_year_month}) のCSVデータが生成されませんでした。")
            return {
                'statusCode': 200,
                'body': json.dumps(f'対象年月 ({target_api_year_month}) のCSVデータは生成されませんでした。')
            }

        # 6. CSVファイルをGoogleドライブに書き出し
        csv_filename = f"{target_csv_filename_prefix}_{file_period_info}.csv" 
        write_to_csv_to_google_drive(final_csv_data, service_account_info_json, GOOGLE_DRIVE_FOLDER_ID, csv_filename)

        print("\n--- freee 工数データエクスポート処理が完了しました ---")
        return {
            'statusCode': 200,
            'body': json.dumps('処理が正常に完了しました')
        }

    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps(f'処理中にエラーが発生しました: {str(e)}')
        }
