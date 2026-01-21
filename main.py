import os
import gspread
import google.auth
import requests
import time

def get_best_model(api_key):
    try:
        url = f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
        res = requests.get(url).json()
        models = [m['name'] for m in res.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        for version in ['2.5-flash', '2.0-flash', '1.5-flash']:
            found = next((m for m in models if version in m), None)
            if found: return found
        return models[0] if models else "models/gemini-1.5-flash"
    except:
        return "models/gemini-2.5-flash"

def gemini_request(url, prompt):
    # Google検索（最新情報取得）機能を有効化
    res = requests.post(url, json={
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search_retrieval": {}}]
    })
    res.raise_for_status()
    return res.json()['candidates'][0]['content']['parts'][0]['text']

def main():
    print("--- 🚀 Auto Content Generator (Step 4 Final: Optimized) ---")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    full_model_name = get_best_model(gemini_key)
    gen_url = f"https://generativelanguage.googleapis.com/v1/{full_model_name}:generateContent?key={gemini_key}"
    
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(creds)
    sh = gc.open("TikTok管理シートAI10").sheet1

    # --- 💡 列のタイトルから列番号を自動取得するロジック ---
    headers = sh.row_values(1)
    def get_col_index(name):
        try:
            return headers.index(name) + 1
        except ValueError:
            print(f"⚠️ 警告: 列名 '{name}' が見つかりません。")
            return None

    col_topic    = get_col_index("ネタ（Input）")
    col_status   = get_col_index("ステータス")
    col_script   = get_col_index("60秒台本")
    col_prompt   = get_col_index("動画生成用プロンプト（英語）")
    col_caption  = get_col_index("キャプション＆タグ")
    col_trend    = get_col_index("トレンド設定") # F1セルの名前に合わせました

    # トレンド設定列の「2行目」の値を取得
    user_input = sh.cell(2, col_trend).value if col_trend else None
    
    # --- モード判定 ---
    if not user_input:
        # 空欄：自動検索
        trend_instruction = "Search for the latest viral TikTok animal trends (Jan 2026) and incorporate them."
        print("🔍 モード：【自動トレンド検索】")
    elif user_input in ["オフ", "off", "OFF", "なし"]:
        # オフ：お題重視
        trend_instruction = "Focus strictly on the topic. Do not add external viral trends."
        print("⏸ モード：【トレンド機能オフ】")
    else:
        # 入力あり：手動反映
        trend_instruction = f"Priority Trend Keyword: {user_input} (Incorporate this style!)"
        print(f"✅ モード：【ユーザー指定反映: {user_input}】")

    # 1. 未処理の行を探す
    cell = sh.find("未処理")
    
    if cell:
        row_num = cell.row
        topic = sh.cell(row_num, col_topic).value
        print(f"📌 既存のネタを処理: Row {row_num}")
    else:
        print("💡 ネタ補充中...")
        all_topics = sh.col_values(col_topic)
        history_topics = all_topics[-6:] if len(all_topics) >= 6 else all_topics
        history_str = ", ".join(history_topics)
        
        idea_prompt = (
            f"{trend_instruction}\n"
            "Task: Generate ONE unique and cute TikTok theme.\n"
            f"Recent history (Avoid): [{history_str}]\n"
            "Concept: Animals doing human-like activities. Format: Japanese only."
        )
        topic = gemini_request(gen_url, idea_prompt).strip()
        
        # 動的な列配置に対応した新規行追加
        new_row = [""] * len(headers)
        new_row[col_topic-1] = topic
        new_row[col_status-1] = "未処理"
        sh.append_row(new_row)
        
        row_num = len(sh.get_all_values())
        print(f"📌 トレンド反映済みの新ネタ: {topic}")

    # 2. 生成指示
    script_prompt = (
        f"Context: {trend_instruction}\n"
        f"Task: Create TikTok content for a 60s video about '{topic}'.\n"
        f"Output MUST follow this structure with '###' separators:\n"
        f"(Japanese Script)\n###\n(English Video Prompt for Kling)\n###\n(Viral Caption & 5 Tags)"
    )

    max_retries = 3
    for i in range(max_retries):
        try:
            full_text = gemini_request(gen_url, script_prompt)
            parts = [p.strip() for p in full_text.split("###")]
            
            if len(parts) >= 3:
                script, video_prompt, caption = parts[0], parts[1], parts[2]
            else:
                script, video_prompt, caption = full_text, f"Cinematic {topic}", f"{topic} #TikTok"

            # 判定された列番号に書き込み
            sh.update_cell(row_num, col_status, "構成済み")
            sh.update_cell(row_num, col_script, script)
            sh.update_cell(row_num, col_prompt, video_prompt)
            sh.update_cell(row_num, col_caption, caption)
            
            print(f"✨ Row {row_num} 書き込み完了！")
            break
        except Exception as e:
            print(f"⚠️ リトライ {i+1}: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
