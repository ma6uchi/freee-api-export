import os
import requests
import json
from dotenv import load_dotenv
import time # 有効期限を考慮するために追加

# .env ファイルから環境変数を読み込む
load_dotenv()

# freee APIのベースURLとトークンエンドポイント
BASE_API_URL = "https://api.freee.co.jp/api/1"
PM_API_BASE_URL = "https://api.freee.co.jp/pm"
TOKEN_URL = "https://accounts.secure.freee.co.jp/public_api/token"

# 環境変数から認証情報を取得
CLIENT_ID = os.getenv("FREEE_CLIENT_ID")
CLIENT_SECRET = os.getenv("FREEE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("FREEE_REDIRECT_URI")

COMPANY_ID = os.getenv("FREEE_COMPANY_ID")

# トークンを保存するファイル名 (セキュリティのため、本番環境ではより安全な方法を検討)
TOKEN_FILE = "tokens.json"

# グローバル変数としてトークンを管理
current_access_token = None
current_refresh_token = None
token_expires_at = 0 # アクセストークンの有効期限（Unixタイムスタンプ）

def load_tokens():
    """
    ファイルからトークン情報を読み込みます。
    """
    global current_access_token, current_refresh_token, token_expires_at
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            data = json.load(f)
            current_access_token = data.get('access_token')
            current_refresh_token = data.get('refresh_token')
            token_expires_at = data.get('expires_at', 0) # 有効期限が保存されていれば読み込む
            print(f"トークンをファイルから読み込みました。有効期限: {time.ctime(token_expires_at) if token_expires_at else '不明'}")
    else:
        print("トークンファイルが見つかりません。初回認証が必要です。")

def save_tokens(token_info: dict):
    """
    取得したトークン情報をファイルに保存します。
    """
    global current_access_token, current_refresh_token, token_expires_at
    current_access_token = token_info.get('access_token')
    current_refresh_token = token_info.get('refresh_token')
    # アクセストークンの有効期限を計算して保存（現在時刻 + expires_in - 余裕を持たせる時間）
    expires_in = token_info.get('expires_in', 3600) # デフォルト1時間
    # 少し余裕を持たせて、期限切れの5分前に更新を試みるようにする
    token_expires_at = time.time() + expires_in - 300 

    data = {
        'access_token': current_access_token,
        'refresh_token': current_refresh_token,
        'expires_at': token_expires_at
    }
    with open(TOKEN_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print("トークンをファイルに保存しました。")

def refresh_access_token(refresh_token: str) -> dict:
    """
    リフレッシュトークンを使用して新しいアクセストークンを取得し、保存します。
    """
    token_params = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token
    }
    print("アクセストークンをリフレッシュ中...")
    try:
        response = requests.post(TOKEN_URL, data=token_params)
        response.raise_for_status()
        new_token_info = response.json()
        print("アクセストークンをリフレッシュしました。")
        save_tokens(new_token_info) # 新しいトークンを保存
        return new_token_info
    except requests.exceptions.RequestException as e:
        print(f"アクセストークンのリフレッシュ中にエラーが発生しました: {e}")
        if response and hasattr(response, 'text'):
            print(f"レスポンスボディ: {response.text}")
        return None

def call_freee_api(endpoint: str, params: dict = None, method: str = 'GET', data: dict = None, is_pm_api: bool = False) -> dict:
    """
    freee APIを呼び出す汎用関数。アクセストークンのリフレッシュ処理も内包。
    is_pm_api=Trueの場合、工数管理APIのURLを使用します。
    """
    global current_access_token, current_refresh_token, token_expires_at

    # トークンが存在しない、または期限切れが近い場合はリフレッシュを試みる
    # 実際のリフレッシュはAPIコール時に401エラーが出た場合に行う
    if current_access_token is None or (token_expires_at > 0 and time.time() >= token_expires_at):
        print("アクセストークンが存在しないか、期限切れが近いため、リフレッシュを試みます。")
        if current_refresh_token:
            new_tokens_info = refresh_access_token(current_refresh_token)
            if not new_tokens_info:
                raise requests.exceptions.RequestException("アクセストークンのリフレッシュに失敗しました。再認証が必要です。")
        else:
            raise requests.exceptions.RequestException("リフレッシュトークンがありません。再認証が必要です。")


    headers = {
        "Authorization": f"Bearer {current_access_token}",
        "Content-Type": "application/json",
        "X-Freee-Version": "2020-06-15" # freee会計APIのバージョン
    }

    if is_pm_api:
        url = f"{PM_API_BASE_URL}/{endpoint}"
        # 工数管理APIは X-Freee-Version を要求しない場合があるため、ここでは削除または適切に調整
        headers.pop('X-Freee-Version', None) # 会計APIのバージョンヘッダーを削除
        # headers["X-PM-Version"] = "2024-05-01" # 例: 必要であれば工数管理APIのバージョンを指定
    else:
        url = f"{BASE_API_URL}/{endpoint}"

    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params)
        elif method == 'POST':
            response = requests.post(url, headers=headers, params=params, json=data)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as http_err:
        # アクセストークンの期限切れ (401 Unauthorized) の可能性
        if response.status_code == 401 and current_refresh_token:
            print("アクセストークンが期限切れの可能性があります。リフレッシュトークンで再試行します。")
            new_tokens_info = refresh_access_token(current_refresh_token)
            if new_tokens_info:
                # 新しいアクセストークンで再試行 (グローバル変数は refresh_access_token で更新済み)
                print("再試行中...")
                headers["Authorization"] = f"Bearer {current_access_token}" # 新しいトークンでヘッダーを更新
                if method == 'GET':
                    response = requests.get(url, headers=headers, params=params)
                elif method == 'POST':
                    response = requests.post(url, headers=headers, params=params, json=data)
                response.raise_for_status() # 再試行後のエラーも確認
                return response.json()
            else:
                print("アクセストークンのリフレッシュに失敗しました。再認証が必要です。")
                raise http_err # リフレッシュも失敗した場合はエラーを再スロー
        else:
            print(f"HTTPエラーが発生しました: {http_err}")
            print(f"レスポンスステータス: {response.status_code}")
            print(f"レスポンスボディ: {response.text}")
            raise http_err
    except requests.exceptions.RequestException as req_err:
        print(f"リクエスト中にエラーが発生しました: {req_err}")
        raise req_err

# --- freee API呼び出し例 (会計API) ---

def get_deals(company_id: int):
    """取引一覧を取得します。"""
    print(f"\n--- 取引一覧を取得中 (company_id: {company_id}) ---")
    endpoint = "deals"
    params = {
        "company_id": company_id,
        "limit": 10,
    }
    deals = call_freee_api(endpoint, params=params, is_pm_api=False)
    print("取得した取引データ:")
    print(json.dumps(deals, indent=2, ensure_ascii=False))
    return deals

def get_account_items(company_id: int):
    """科目一覧を取得します。"""
    print(f"\n--- 科目一覧を取得中 (company_id: {company_id}) ---")
    endpoint = "account_items"
    params = {
        "company_id": company_id
    }
    account_items = call_freee_api(endpoint, params=params, is_pm_api=False)
    print("取得した科目データ:")
    print(json.dumps(account_items, indent=2, ensure_ascii=False))
    return account_items

# --- freee工数管理API呼び出し例 ---

def get_pm_projects():
    """freee工数管理のプロジェクト一覧を取得します。"""
    print("\n--- freee工数管理プロジェクト一覧を取得中 ---")
    endpoint = "projects"
    params = {} # 工数管理APIのprojectsエンドポイントは、通常company_id不要
    projects = call_freee_api(endpoint, params=params, is_pm_api=True)
    print("取得したプロジェクトデータ:")
    print(json.dumps(projects, indent=2, ensure_ascii=False))
    return projects

def get_pm_project_details(project_id: str):
    """freee工数管理の特定のプロジェクト詳細を取得します。"""
    print(f"\n--- freee工数管理プロジェクト詳細を取得中 (Project ID: {project_id}) ---")
    endpoint = f"projects/{project_id}"
    details = call_freee_api(endpoint, is_pm_api=True)
    print("取得したプロジェクト詳細データ:")
    print(json.dumps(details, indent=2, ensure_ascii=False))
    return details

if __name__ == "__main__":
    # 最初にトークンをファイルから読み込む
    load_tokens()

    # 環境変数に設定しているClient ID/Secretが空でないことを確認
    if not all([CLIENT_ID, CLIENT_SECRET]):
        raise ValueError(
            "環境変数 FREEE_CLIENT_ID, FREEE_CLIENT_SECRET が設定されていません。"
            "これらは .env ファイルで設定してください。"
        )

    # 最初にトークンが存在しない場合は、手動で取得を促す
    if current_access_token is None or current_refresh_token is None:
        print("\n初回認証が必要です。トークンファイルが見つからないか、トークンが不足しています。")
        print("token_manager.py スクリプトを実行し、アクセストークンとリフレッシュトークンを取得して、")
        print(f"その情報を '{TOKEN_FILE}' ファイルに手動で保存してください。")
        exit() # ここで終了し、ユーザーに手動でのトークン取得を促す

    try:
        # freee工数管理APIの呼び出し
        pm_projects_data = get_pm_projects()

        # もしプロジェクトが取得できたら、最初のプロジェクトの詳細も取得してみる
        if pm_projects_data and pm_projects_data.get('projects'):
            first_project_id = pm_projects_data['projects'][0]['id']
            get_pm_project_details(first_project_id)

        # 会計APIの呼び出し（company_idが必要）
        if COMPANY_ID: # COMPANY_IDが設定されている場合のみ会計APIを呼ぶ
            deals_data = get_deals(int(COMPANY_ID))
            account_items_data = get_account_items(int(COMPANY_ID))
        else:
            print("\nCOMPANY_IDが設定されていないため、会計APIの呼び出しをスキップします。")


        print("\n=== 全てのAPI呼び出しが完了しました ===")

    except ValueError as e:
        print(f"設定エラー: {e}")
    except requests.exceptions.RequestException as e:
        print(f"API呼び出し中にエラーが発生しました: {e}")