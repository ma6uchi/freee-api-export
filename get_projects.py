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

WORKLOADS_API_URL = "https://api.freee.co.jp/pm/projects"

def get_all_freee_projects(access_token, company_id, limit=100):
    """
    freee API から指定された事業所IDと年月、社員スコープで全プロジェクトデータをページネーションで取得する
    """
    if not access_token:
        print("エラー: アクセストークンが提供されていません。")
        return None
    if not company_id:
        print("エラー: company_id が提供されていません。")
        return None

    all_projects = []
    offset = 0
    total_count = -1

    first_request = True

    while True:
        params = {
            "company_id": company_id,
            "limit": limit,
            "offset": offset,
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        print(f"\nfreee API からプロジェクトを取得中 (offset: {offset})...")
        try:
            response = requests.get(WORKLOADS_API_URL, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            current_projects_part = data.get("projects", [])
            projects_meta = data.get("meta", {})

            if first_request:
                total_count = projects_meta.get("total_count", 0)
                print(f"総プロジェクト件数: {total_count}")
                if total_count == 0:
                    print("該当するプロジェクトデータがありませんでした。")
                    return []
                first_request = False

            all_projects.extend(current_projects_part)

            offset += len(current_projects_part)

            if len(current_projects_part) < limit or offset >= total_count:
                print("全てのプロジェクトデータを取得しました。")
                break

        except requests.exceptions.RequestException as e:
            print(f"プロジェクトの取得中にエラーが発生しました: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"レスポンスステータス: {e.response.status_code}")
                print(f"レスポンスボディ: {e.response.text}")
            return None
        except Exception as e:
            print(f"予期せぬエラーが発生しました: {e}")
            return None

    return all_projects


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
            projects = get_all_freee_projects(access_token, COMPANY_ID)
            print("[" + ", ".join([str(x) for x in projects[:3]]) + ", ..., " + ", ".join([str(x) for x in projects[len(projects) - 3:]]) + "]")

        else:
            print("\nトークンの更新に失敗したため、freee API にアクセスできません。")