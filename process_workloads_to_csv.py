import csv
from collections import defaultdict

def create_project_lookup(projects_list):
    """
    プロジェクトリストをIDをキーとする辞書に変換し、検索を高速化する。
    """
    project_lookup = {}
    for project in projects_list:
        project_lookup[project['id']] = project
    return project_lookup

def process_workloads_to_csv_data(all_workloads, project_lookup_dict):
    """
    workloads と projects のデータからCSV出力用のデータを整形・集計する。

    Args:
        all_workloads (list): 全ての工数実績データ（workloads APIから取得）
        project_lookup_dict (dict): project_id をキーとするプロジェクト情報の辞書

    Returns:
        list: CSVに書き出すための行データのリスト
    """
    # CSV出力用のデータを格納するリスト
    csv_rows_raw = []

    for wl in all_workloads:
        person_name = wl.get('person_name', '')
        project_id = wl.get('project_id')
        memo = wl.get('memo', '')
        minutes = wl.get('minutes', 0)

        project_name = ''
        project_code = ''
        internal_external = '' # 社内/社外
        project_tag_name = '' # プロジェクトタグ

        # プロジェクト情報の取得
        project_info = project_lookup_dict.get(project_id)
        if project_info:
            project_name = project_info.get('name', '')
            project_code = project_info.get('code', '')

            # project_tagsから社内/社外を判定
            if project_info.get('project_tags'):
                for p_tag in project_info['project_tags']:
                    # project_tags に '社内' または '社外' が含まれるかを簡易的に判定
                    # 実際のデータと合わせてロジックを調整してください
                    if p_tag.get('tag_name') == '社内':
                        internal_external = '社内'
                        project_tag_name = p_tag.get('tag_name') # ここでは「社内」タグ名自体
                        break # 見つかったらループを抜ける
                    elif p_tag.get('tag_name') == '社外':
                        internal_external = '社外'
                        project_tag_name = p_tag.get('tag_name') # ここでは「社外」タグ名自体
                        break
                # もしproject_tagsに「社内/社外」の明示的なタグがない場合、デフォルトは空欄のまま

        # workload_tags は複数ある場合、それぞれ別の行にする
        if wl.get('workload_tags'):
            for wt in wl['workload_tags']:
                tag_group_name = wt.get('tag_group_name', '')
                tag_name = wt.get('tag_name', '')

                # CSV行データを作成
                csv_rows_raw.append({
                    'person_name': person_name,
                    'internal_external': internal_external,
                    'project_name': project_name,
                    'project_code': project_code, # プロジェクトコードも保持しておくと便利
                    'workload_tag_group_name': tag_group_name, # タググループ名
                    'workload_tag_name': tag_name, # 工数タグ名
                    'project_tag_name': project_tag_name, # プロジェクトタグ名
                    'memo': memo,
                    'minutes': minutes
                })
        else:
            # workload_tags がない場合も行を追加 (工数タグは空欄)
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

    # 集計処理
    # キーは (対象従業員, プロジェクト名, 工数タグ名)
    aggregated_data = defaultdict(lambda: {'minutes': 0, 'memos': []})

    for row in csv_rows_raw:
        key = (
            row['person_name'],
            row['project_name'],
            row['workload_tag_name'] # 工数タグ名で集計
        )
        aggregated_data[key]['minutes'] += row['minutes']
        if row['memo']: # memo が空でなければ追加
            aggregated_data[key]['memos'].append(row['memo'])

        # 集計キー以外の情報は、最初の出現データを使用
        if 'first_occurrence_row' not in aggregated_data[key]:
            aggregated_data[key]['first_occurrence_row'] = row

    # 最終的なCSV出力形式に整形
    final_csv_data = []
    for key, value in aggregated_data.items():
        original_row = value['first_occurrence_row']
        total_minutes = value['minutes']
        total_hours = round(total_minutes / 60, 2) # 時間に変換し、小数点以下2桁で丸める

        final_csv_data.append({
            '対象従業員': original_row['person_name'],
            '社内/社外': original_row['internal_external'],
            'プロジェクト': original_row['project_name'],
            '工数タグ': original_row['workload_tag_name'],
            'プロジェクトタグ': original_row['project_tag_name'], # ここでは project_tags からの情報をそのまま使用
            '業務内容': ", ".join(sorted(set(value['memos']))), # 重複するメモを除外し、ソートして連結
            '合計工数（分）': total_minutes,
            '合計工数（時間）': total_hours
        })

    return final_csv_data


def write_to_csv(data_rows, filename="workloads_summary.csv"):
    """
    整形されたデータをCSVファイルに書き出す。
    """
    if not data_rows:
        print("書き出すデータがありません。")
        return

    # CSVヘッダー
    fieldnames = [
        '対象従業員', '社内/社外', 'プロジェクト', '工数タグ', 
        'プロジェクトタグ', '業務内容', '合計工数（分）', '合計工数（時間）'
    ]

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader() # ヘッダーを書き込む
            writer.writerows(data_rows) # データ行を書き込む
        print(f"CSVファイル '{filename}' を作成しました。")
    except IOError as e:
        print(f"CSVファイルの書き込み中にエラーが発生しました: {e}")

# --- 実行例 ---
if __name__ == "__main__":
    # CLIENT_ID, CLIENT_SECRET, FREEE_REFRESH_TOKEN, FREEE_COMPANY_ID, FREEE_TARGET_YEAR_MONTH
    # を .env ファイルに設定していることを確認してください。
    # refresh_freee_tokens 関数は別途定義されているものとします。

    # ここに、実際に freee API から取得した all_workloads と all_projects_data を格納
    # テスト用のダミーデータ（実際にはAPIから取得したデータを使用）
    # get_all_freee_workloads 関数で取得したデータを使用
    # get_all_freee_projects 関数 (別途実装が必要) で取得したデータを使用

    # 実際のAPI呼び出しの代わりにダミーデータを使用
    # Dummy Data for workloads (from your previous example, but extended for more entries)
    # (実際のデータは非常に長いため、一部を抜粋し、複数のタグやメモが混在する例を表現)
    dummy_all_workloads = [
        {'id': 21021095, 'person_id': 41210, 'person_name': '日野史菜', 'date': '2025-05-01', 'project_id': 248508, 'project_name': 'リブセンス', 'project_code': 'P-009', 'memo': 'Int準備', 'minutes': 45, 'workload_tags': [{'tag_group_id': 30547, 'tag_group_name': 'PM', 'tag_id': 200664, 'tag_name': '資料作成、議事録作成'}]},
        {'id': 21021205, 'person_id': 41210, 'person_name': '日野史菜', 'date': '2025-05-01', 'project_id': 248502, 'project_name': '組織共通', 'project_code': 'P-003', 'memo': 'GV案件人探し、スキル要件確認', 'minutes': 60, 'workload_tags': [{'tag_group_id': 30543, 'tag_group_name': '共通', 'tag_id': 200623, 'tag_name': 'その他作業'}]},
        {'id': 21035996, 'person_id': 41210, 'person_name': '日野史菜', 'date': '2025-05-01', 'project_id': 248503, 'project_name': 'マネジメント', 'project_code': 'P-004', 'memo': 'レビューFMTアナウンス', 'minutes': 20, 'workload_tags': [{'tag_group_id': 30553, 'tag_group_name': 'マネージャー・リーダー', 'tag_id': 201465, 'tag_name': '業務改善・効率化'}]},
        {'id': 21053057, 'person_id': 41210, 'person_name': '日野史菜', 'date': '2025-05-01', 'project_id': 248506, 'project_name': 'ワールドプラス_DX', 'project_code': 'P-007', 'memo': 'task:WP_DX調査・分析', 'minutes': 135, 'workload_tags': [{'tag_group_id': 30547, 'tag_group_name': 'PM', 'tag_id': 200663, 'tag_name': '調査・分析'}]},
        # 同じプロジェクト、同じ人、同じタグでmemoとminutesが異なる例
        {'id': 21053058, 'person_id': 41210, 'person_name': '日野史菜', 'date': '2025-05-01', 'project_id': 248508, 'project_name': 'リブセンス', 'project_code': 'P-009', 'memo': 'int リブセンス様 PJ確認', 'minutes': 30, 'workload_tags': [{'tag_group_id': 30547, 'tag_group_name': 'PM', 'tag_id': 200665, 'tag_name': 'MTG（社外）'}]},
        {'id': 21053059, 'person_id': 41210, 'person_name': '日野史菜', 'date': '2025-05-01', 'project_id': 248508, 'project_name': 'リブセンス', 'project_code': 'P-009', 'memo': '標準化シート作成', 'minutes': 15, 'workload_tags': [{'tag_group_id': 30547, 'tag_group_name': 'PM', 'tag_id': 200664, 'tag_name': '資料作成、議事録作成'}]},
        # 複数タグの例
        {'id': 21053060, 'person_id': 41210, 'person_name': '日野史菜', 'date': '2025-05-01', 'project_id': 248502, 'project_name': '組織共通', 'project_code': 'P-003', 'memo': '個人スキル強化', 'minutes': 15, 'workload_tags': [{'tag_group_id': 30543, 'tag_group_name': '共通', 'tag_id': 200631, 'tag_name': '個人スキル強化・キャリア形成'}, {'tag_group_id': 99999, 'tag_group_name': '開発', 'tag_id': 999999, 'tag_name': '技術学習'}]},
        {'id': 21053154, 'person_id': 41210, 'person_name': '日野史菜', 'date': '2025-05-01', 'project_id': 248508, 'project_name': 'リブセンス', 'project_code': 'P-009', 'memo': 'トレーニング調整、TODO確認', 'minutes': 30, 'workload_tags': [{'tag_group_id': 30547, 'tag_group_name': 'PM', 'tag_id': 200660, 'tag_name': 'タスク整理・工数管理'}]},
        {'id': 21056869, 'person_id': 41210, 'person_name': '日野史菜', 'date': '2025-05-01', 'project_id': 248500, 'project_name': 'エスオーシー', 'project_code': 'P-001', 'memo': 'SOC様データ確認', 'minutes': 15, 'workload_tags': [{'tag_group_id': 30547, 'tag_group_name': 'PM', 'tag_id': 200665, 'tag_name': 'MTG（社外）'}]},
        {'id': 21057053, 'person_id': 41210, 'person_name': '日野史菜', 'date': '2025-05-01', 'project_id': 248506, 'project_name': 'ワールドプラス_DX', 'project_code': 'P-007', 'memo': 'task:WP_DX調査・分析', 'minutes': 120, 'workload_tags': [{'tag_group_id': 30547, 'tag_group_name': 'PM', 'tag_id': 200663, 'tag_name': '調査・分析'}]}
    ] * 2 # ダミーデータを増やすために複製

    # Dummy Data for projects (from your previous example)
    dummy_all_projects = [
        {'id': 248500, 'name': 'エスオーシー', 'code': 'P-001', 'description': '', 'manager': {'person_id': 41210, 'person_name': '日野史菜'}, 'color': '#fa6414', 'from_date': '2025-03-03', 'thru_date': '2025-08-31', 'publish_to_employee': True, 'assignment_url_enabled': False, 'operational_status': 'in_progress', 'sales_order_status': '指定なし', 'workload_tag_groups': [{'tag_group_id': 30547, 'tag_group_name': 'PM', 'required': False, 'tags': [{'id': 201414, 'name': 'プロジェクト計画'}, {'id': 200662, 'name': 'スケジュール管理'}, {'id': 200660, 'name': 'タスク整理・工数管理'}, {'id': 200664, 'name': '資料作成、議事録作成'}, {'id': 200663, 'name': '調査・分析'}, {'id': 200661, 'name': '要件定義・設計'}, {'id': 200677, 'name': '連絡'}, {'id': 200665, 'name': 'MTG（社外）'}, {'id': 200658, 'name': 'MTG（社内）'}, {'id': 200654, 'name': '環境構築・設定'}, {'id': 200653, 'name': 'テスト'}, {'id': 200657, 'name': 'トレーニング'}, {'id': 200656, 'name': '運用保守・クライアントサポート'}, {'id': 200655, 'name': '確認・レビュー'}, {'id': 200651, 'name': '契約手続き・書類作成'}, {'id': 200649, 'name': 'ヘルプ・サポート'}, {'id': 200648, 'name': 'サポート依頼・準備'}, {'id': 200650, 'name': '移動'}, {'id': 201482, 'name': 'イベント・会食'}]}], 'members': [{'person_id': 41210, 'person_name': '日野史菜'}], 'orderers': [], 'contractors': [], 'project_tags': [{'tag_group_name': '社外', 'tag_name': '業務委託'}]},
        {'id': 248508, 'name': 'リブセンス', 'code': 'P-009', 'description': '', 'manager': {'person_id': 41210, 'person_name': '日野史菜'}, 'color': '#fa6414', 'from_date': '2025-03-03', 'thru_date': '2025-08-31', 'publish_to_employee': True, 'assignment_url_enabled': False, 'operational_status': 'in_progress', 'sales_order_status': '指定なし', 'workload_tag_groups': [], 'members': [], 'orderers': [], 'contractors': [], 'project_tags': [{'tag_group_name': '社外', 'tag_name': 'コンサルティング'}]},
        {'id': 248502, 'name': '組織共通', 'code': 'P-003', 'description': '', 'manager': {'person_id': 41210, 'person_name': '日野史菜'}, 'color': '#0099cc', 'from_date': None, 'thru_date': None, 'publish_to_employee': True, 'assignment_url_enabled': False, 'operational_status': 'in_progress', 'sales_order_status': '指定なし', 'workload_tag_groups': [], 'members': [], 'orderers': [], 'contractors': [], 'project_tags': [{'tag_group_name': '社内', 'tag_name': '共通業務'}]},
        {'id': 248503, 'name': 'マネジメント', 'code': 'P-004', 'description': '', 'manager': {'person_id': 41210, 'person_name': '日野史菜'}, 'color': '#0099cc', 'from_date': None, 'thru_date': None, 'publish_to_employee': True, 'assignment_url_enabled': False, 'operational_status': 'in_progress', 'sales_order_status': '指定なし', 'workload_tag_groups': [], 'members': [], 'orderers': [], 'contractors': [], 'project_tags': [{'tag_group_name': '社内', 'tag_name': '管理業務'}]},
        {'id': 248506, 'name': 'ワールドプラス_DX', 'code': 'P-007', 'description': '', 'manager': {'person_id': 41210, 'person_name': '日野史菜'}, 'color': '#33cc33', 'from_date': '2025-04-01', 'thru_date': '2025-09-30', 'publish_to_employee': True, 'assignment_url_enabled': False, 'operational_status': 'in_progress', 'sales_order_status': '指定なし', 'workload_tag_groups': [], 'members': [], 'orderers': [], 'contractors': [], 'project_tags': [{'tag_group_name': '社外', 'tag_name': '開発PJ'}]},
    ]

    # プロジェクトルックアップ辞書を作成
    project_lookup = create_project_lookup(dummy_all_projects)

    # CSV出力データを整形・集計
    final_csv_data = process_workloads_to_csv_data(dummy_all_workloads, project_lookup)

    # CSVファイルに書き出し
    write_to_csv(final_csv_data, "freee_workloads_summary.csv")