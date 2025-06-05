import requests
import time

PROJECTS_API_URL = "https://api.freee.co.jp/pm/projects"

def get_all_freee_projects(access_token, company_id, limit=100):
    """
    freee API から全プロジェクトデータをページネーションで取得する
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
            response = requests.get(PROJECTS_API_URL, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            current_projects_part = data.get("projects", [])
            projects_meta = data.get("meta", {})

            if first_request:
                total_count = projects_meta.get("total_count", 0)
                print(f"総プロジェクト件数: {total_count}")
                if total_count == 0:
                    print("プロジェクトデータがありませんでした。")
                    return []
                first_request = False

            all_projects.extend(current_projects_part)

            offset += len(current_projects_part)

            if len(current_projects_part) < limit or offset >= total_count:
                print("全てのプロジェクトデータを取得しました。")
                break

            time.sleep(1) # レートリミット対策

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

def create_project_lookup(projects_list):
    """
    プロジェクトリストをIDをキーとする辞書に変換し、検索を高速化する。
    """
    project_lookup = {}
    for project in projects_list:
        project_lookup[project['id']] = project
    return project_lookup