import csv
from collections import defaultdict
import io
import json

# Google Drive API 関連のライブラリのインポート
from google.oauth2 import service_account # <-- ここを追加
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

def process_workloads_to_csv_data(all_workloads, project_lookup_dict):
    """
    workloads と projects のデータからCSV出力用のデータを整形・集計する。

    Args:
        all_workloads (list): 全ての工数実績データ
        project_lookup_dict (dict): project_id をキーとするプロジェクト情報の辞書

    Returns:
        list: CSVに書き出すための行データのリスト
    """
    csv_rows_raw = []

    for wl in all_workloads:
        person_name = wl.get('person_name', '')
        project_id = wl.get('project_id')
        memo = wl.get('memo', '')
        minutes = wl.get('minutes', 0)

        project_name = ''
        project_code = ''
        internal_external = ''
        project_tag_name = ''

        project_info = project_lookup_dict.get(project_id)
        if project_info:
            project_name = project_info.get('name', '')
            project_code = project_info.get('code', '')

            if project_info.get('project_tags'):
                current_project_tags = [] 
                for p_tag in project_info['project_tags']:
                    # 社内/社外の判定
                    if p_tag.get('tag_group_name') == '社内':
                        internal_external = '社内'
                    elif p_tag.get('tag_group_name') == '社外':
                        internal_external = '社外'

                # tag_name を project_tag_name に含めるのは、そのままのロジックでOKです。
                if p_tag.get('tag_name'):
                    current_project_tags.append(p_tag['tag_name'])

                
                # 複数のプロジェクトタグがある場合を考慮し、カンマ区切りで結合
                project_tag_name = ", ".join(sorted(set(current_project_tags)))

        if wl.get('workload_tags'):
            for wt in wl['workload_tags']:
                tag_group_name = wt.get('tag_group_name', '')
                tag_name = wt.get('tag_name', '')

                csv_rows_raw.append({
                    'person_name': person_name,
                    'internal_external': internal_external,
                    'project_name': project_name,
                    'project_code': project_code,
                    'workload_tag_group_name': tag_group_name,
                    'workload_tag_name': tag_name,
                    'project_tag_name': project_tag_name,
                    'memo': memo,
                    'minutes': minutes
                })
        else:
            csv_rows_raw.append({
                'person_name': person_name,
                'internal_external': internal_external,
                'project_name': project_name,
                'project_code': project_code,
                'workload_tag_group_name': '',
                'workload_tag_name': '',
                'project_tag_name': project_tag_name,
                'memo': memo,
                'minutes': minutes
            })

    aggregated_data = defaultdict(lambda: {'minutes': 0, 'memos': []})

    for row in csv_rows_raw:
        key = (
            row['person_name'],
            row['project_name'],
            row['workload_tag_name']
        )
        aggregated_data[key]['minutes'] += row['minutes']
        if row['memo']:
            aggregated_data[key]['memos'].append(row['memo'])

        if 'first_occurrence_row' not in aggregated_data[key]:
            aggregated_data[key]['first_occurrence_row'] = row

    final_csv_data = []
    for key, value in aggregated_data.items():
        original_row = value['first_occurrence_row']
        total_minutes = value['minutes']
        total_hours = round(total_minutes / 60, 2)

        final_csv_data.append({
            '対象従業員': original_row['person_name'],
            '社内/社外': original_row['internal_external'],
            'プロジェクト': original_row['project_name'],
            '工数タグ': original_row['workload_tag_name'],
            'プロジェクトタグ': original_row['project_tag_name'],
            '業務内容': ", ".join(sorted(set(value['memos']))),
            '合計工数（分）': total_minutes,
            '合計工数（時間）': total_hours
        })

    return final_csv_data

def write_to_csv_to_google_drive(data_rows, service_account_info_json, folder_id, file_name):
    """
    整形されたデータをCSVファイルとしてGoogleドライブに書き出す。
    """
    if not data_rows:
        print("書き出すデータがありません。Googleドライブへの書き込みをスキップします。")
        return

    # CSVヘッダー
    fieldnames = [
        '対象従業員', '社内/社外', 'プロジェクト', '工数タグ',
        'プロジェクトタグ', '業務内容', '合計工数（分）', '合計工数（時間）'
    ]

    # メモリ上でCSVデータを構築
    csv_string_buffer = io.StringIO()
    writer = csv.DictWriter(csv_string_buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data_rows)

    csv_bytes = csv_string_buffer.getvalue().encode('utf-8') # UTF-8でバイト列にエンコード
    csv_bytes_buffer = io.BytesIO(csv_bytes)

    # Google Drive API 認証
    try:
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(service_account_info_json),
            scopes=['https://www.googleapis.com/auth/drive']
        )
        service = build('drive', 'v3', credentials=credentials)
    except Exception as e:
        print(f"Google Drive APIの認証に失敗しました: {e}")
        raise

    # ファイルメタデータ
    file_metadata = {
        'name': file_name,
        'parents': [folder_id],
        'mimeType': 'text/csv'
    }

    # ファイルのアップロード
    media = MediaIoBaseUpload(csv_bytes_buffer, mimetype='text/csv', resumable=True)
    
    try:
        file = service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id', 
            supportsAllDrives=True
        ).execute()
        print(f"CSVファイル '{file_name}' をGoogleドライブにアップロードしました。ファイルID: {file.get('id')}")
    except Exception as e:
        print(f"GoogleドライブへのCSVファイルアップロード中にエラーが発生しました: {e}")
        raise