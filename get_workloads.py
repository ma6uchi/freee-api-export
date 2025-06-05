import requests
import json
import os
from dotenv import load_dotenv
from get_tokens import refresh_freee_tokens

load_dotenv()

TOKEN_URL = "https://api.freee.co.jp/oauth/token"

# .env ファイルまたは環境変数から取得
CLIENT_ID = os.getenv("FREEE_CLIENT_ID")
CLIENT_SECRET = os.getenv("FREEE_CLIENT_SECRET")
COMPANY_ID = os.getenv("FREEE_COMPANY_ID")

WORKLOADS_API_URL = "https://api.freee.co.jp/pm/workloads"

def get_all_freee_workloads(access_token, company_id, year_month, limit=100):
    """
    freee API から指定された事業所IDと年月、社員スコープで全工数実績データをページネーションで取得する
    """
    if not access_token:
        print("エラー: アクセストークンが提供されていません。")
        return None
    if not company_id:
        print("エラー: company_id が提供されていません。")
        return None
    if not year_month:
        print("エラー: year_month が提供されていません (例: '2025-05')。")
        return None

    all_workloads = []
    offset = 0
    total_count = -1

    first_request = True

    while True:
        params = {
            "company_id": company_id,
            "employees_scope": "all",
            "year_month": year_month,
            "limit": limit,
            "offset": offset,
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        print(f"\nfreee API から工数実績を取得中 (offset: {offset})...")
        try:
            response = requests.get(WORKLOADS_API_URL, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            current_workloads_part = data.get("workloads", [])
            workloads_meta = data.get("meta", {})

            if first_request:
                total_count = workloads_meta.get("total_count", 0)
                print(f"総工数実績件数: {total_count}")
                if total_count == 0:
                    print("該当する工数実績データがありませんでした。")
                    return []
                first_request = False

            all_workloads.extend(current_workloads_part)

            offset += len(current_workloads_part)

            if len(current_workloads_part) < limit or offset >= total_count:
                print("全ての工数実績データを取得しました。")
                break

        except requests.exceptions.RequestException as e:
            print(f"工数実績の取得中にエラーが発生しました: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"レスポンスステータス: {e.response.status_code}")
                print(f"レスポンスボディ: {e.response.text}")
            return None
        except Exception as e:
            print(f"予期せぬエラーが発生しました: {e}")
            return None

    return all_workloads


# --- 実行例 ---
if __name__ == "__main__":
    if not CLIENT_ID or not CLIENT_SECRET:
        print("エラー: CLIENT_ID または CLIENT_SECRET が .env ファイルに設定されていません。")
    else:
        print("\n--- freee API 連携処理の開始 ---")

        access_token, _ = refresh_freee_tokens()
        year_month = "2025-05"
        offset = 0

        if access_token:
            workloads = get_all_freee_workloads(access_token, COMPANY_ID, year_month)
            print("[" + ", ".join([str(x) for x in workloads[:3]]) + ", ..., " + ", ".join([str(x) for x in workloads[len(workloads) - 3:]]) + "]")

        else:
            print("\nトークンの更新に失敗したため、freee API にアクセスできません。")