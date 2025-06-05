import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN_URL = "https://accounts.secure.freee.co.jp/public_api/token"
CLIENT_ID = os.getenv("FREEE_CLIENT_ID")
CLIENT_SECRET = os.getenv("FREEE_CLIENT_SECRET")

def refresh_freee_tokens():
    """
    リフレッシュトークンを使ってfreeeのアクセストークンとリフレッシュトークンを更新する
    """
    current_refresh_token = os.getenv("FREEE_REFRESH_TOKEN")
    if not current_refresh_token:
        print("エラー: FREEE_REFRESH_TOKEN が .env ファイルまたは環境変数に設定されていません。")
        return None, None

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": current_refresh_token
    }

    print("新しいトークンを取得するためにリフレッシュトークンを使用しています...")
    try:
        response = requests.post(TOKEN_URL, headers=headers, data=payload)
        response.raise_for_status()
        tokens = response.json()

        new_access_token = tokens.get("access_token")
        new_refresh_token = tokens.get("refresh_token")

        if new_access_token and new_refresh_token:
            print("トークンの更新に成功しました。")
            print(f"新しいアクセストークン (次回使用): {new_access_token}")
            print(f"新しいリフレッシュトークン (次回使用): {new_refresh_token}")
            print("--- 重要 ---")
            print("この新しいリフレッシュトークンを次の実行のために手動で .env ファイルの FREEE_REFRESH_TOKEN に更新してください。")
            return new_access_token, new_refresh_token
        else:
            print(f"エラー: レスポンスに新しいトークンが含まれていませんでした。{tokens}")
            return None, None

    except requests.exceptions.RequestException as e:
        print(f"トークンの更新中にエラーが発生しました: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"レスポンスステータス: {e.response.status_code}")
            print(f"レスポンスボディ: {e.response.text}")
        return None, None