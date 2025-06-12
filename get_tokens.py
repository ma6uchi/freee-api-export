import requests
import json
import os
import boto3

TOKEN_URL = "https://accounts.secure.freee.co.jp/public_api/token"
secrets_client = boto3.client('secretsmanager') # Lambda環境で初期化

def refresh_freee_tokens_with_secrets_manager(client_id, client_secret, secrets_name):
    """
    Secrets Managerからリフレッシュトークンを読み込み、
    freeeのアクセストークンとリフレッシュトークンを更新し、
    新しいトークンをSecrets Managerに保存する。
    """
    print(f"Secrets Managerからシークレット '{secrets_name}' を読み込み中...")
    try:
        # Secrets Managerから現在のトークン情報を取得
        get_secret_value_response = secrets_client.get_secret_value(SecretId=secrets_name)
        secret_json = json.loads(get_secret_value_response['SecretString'])
        current_refresh_token = secret_json.get("refresh_token")
        
    except Exception as e:
        print(f"Secrets Managerからのトークン読み込み中にエラーが発生しました: {e}")
        return None, None

    if not current_refresh_token:
        print("エラー: Secrets ManagerにFREEE_REFRESH_TOKENが見つかりません。初回認証が必要です。")
        return None, None

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
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
            
            # 新しいトークンをSecrets Managerに保存（既存のシークレットを更新）
            # client_id, client_secret も同じシークレットに保存されていることを前提
            secret_json["access_token"] = new_access_token
            secret_json["refresh_token"] = new_refresh_token
            
            secrets_client.put_secret_value(
                SecretId=secrets_name,
                SecretString=json.dumps(secret_json)
            )
            print(f"新しいトークンを Secrets Manager '{secrets_name}' に保存しました。")
            
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
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
        return None
