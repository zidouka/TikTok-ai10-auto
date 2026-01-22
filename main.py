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
    max_retries = 5
    for attempt in range(max_retries):
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "tools": [{"google_search_retrieval": {}}]
            }
            res = requests.post(url, json=payload)
            
            # API制限(429)の場合
            if res.status_code == 429:
                wait_time = (attempt + 1) * 20 # 20秒, 40秒, 60秒...と待機
                print(f"⏳ API制限(429)を検知。{wait_time}秒待機してリトライします({attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            
            # 検索ツールエラー(400)の場合
            if res.status_code == 400:
                payload.pop("tools")
                res = requests.post(url, json=payload)
            
            res.raise_for_status()
            return res.json()['candidates'][0]['content']['parts'][0]['text']
            
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(10)
    return None

def main():
    print("--- 🚀 Auto Content Generator (Maximum Reliability Version) ---")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    full_model_name = get_best_model(gemini_key)
    gen_url = f"https://generativelanguage.googleapis.com/v1/{full_model_name}:generateContent?key={gemini_key}"
    
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(creds)
    sh = gc.open("TikTok管理シートAI10").sheet1

    # --- 1. 列の自動判定 ---
    headers = sh.row_values(1)
    def get_col_index(name):
        try: return headers.index(name) + 1
        except ValueError: return None

    col_topic    = get_col_index("ネタ（Input）")
    col_status   = get_col_index("ステータス")
    col_script   = get_col_index("60秒台本")
    col_prompt   = get_col_index("動画生成用プロンプト（英語）")
    col_caption  = get_col_index("キャプション＆タグ")
    col_trend    = get_col_index("トレンド設定")

    user_input = sh.cell(2, col_trend).value if col_trend else None
    trend_instruction = f"Priority Trend: {user_input}" if user_input else "Search for latest viral TikTok animal trends."

    # --- 2. ネタの検索と補充 ---
    cell = sh.find("未処理")
    if cell:
        row_num = cell.row
        topic = sh.cell(row_num, col_topic).value if col_topic else sh.cell(row_num, 1).value
        print(f"📌 既存のネタを処理: Row {row_num} -> {topic}")
    else:
        print("💡 ネタを自動補充中...")
        all_topics = sh.col_values(col_topic) if col_topic else []
        history_str = ", ".join(all_topics[-6:])
        
        idea_prompt = (
            f"{trend_instruction}\n"
            "Task: Generate exactly ONE unique and cute TikTok theme.\n"
            f"Avoid duplicates with: [{history_str}]\n"
            "Concept: 'Animals doing human-like activities'.\n"
            "IMPORTANT: Output ONLY the theme name in Japanese."
        )
        
        raw_idea = gemini_request(gen_url, idea_prompt)
        topic = raw_idea.split('\n')[-1].replace('**', '').replace('「', '').replace('」', '').strip()
        
        new_row = [""] * len(headers)
        if col_topic: new_row[col_topic-1] = topic
        if col_status: new_row[col_status-1] = "未処理"
        sh.append_row(new_row)
        row_num = len(sh.get_all_values())
        print(f"✅ 新ネタを追加: {topic} (Row {row_num})")

    # リクエスト間の冷却時間
    time.sleep(10)

    # --- 3. 生成指示 ---
    script_prompt = (
        f"Step 1: Search for the latest TikTok visual trends and popular hashtags for animal videos.\n"
        f"Step 2: Create TikTok content for a 10s video about '{topic}'.\n"
        f"Incorporate trending camera movements, editing styles, or background music concepts discovered in Step 1.\n"
        f"Output MUST follow this structure exactly with '###' separators. No labels.\n"
        f"\n"
        f"Structure:\n"
        f"(Japanese Script including trending audio cues)\n"
        f"###\n"
        f"(English Video Prompt for Kling/Luma with trending visual styles)\n"
        f"###\n"
        f"(Viral Caption and 5 Trending Hashtags)\n"
    )

    print(f"✍️ '{topic}' の詳細構成を生成中...")
    full_text = gemini_request(gen_url, script_prompt)
    
    if full_text:
        parts = [p.strip() for p in full_text.split("###")]
        script = parts[0] if len(parts) > 0 else "Error"
        video_prompt = parts[1] if len(parts) > 1 else "Error"
        caption = parts[2] if len(parts) > 2 else "Error"

        # 書き込み
        try:
            if col_status:  sh.update_cell(row_num, col_status, "構成済み")
            if col_script:  sh.update_cell(row_num, col_script, script)
            if col_prompt:  sh.update_cell(row_num, col_prompt, video_prompt)
            if col_caption: sh.update_cell(row_num, col_caption, caption)
            print(f"✨ Row {row_num} 全データ書き込み完了！")
        except Exception as e:
            print(f"❌ スプレッドシートへの書き込みに失敗: {e}")

if __name__ == "__main__":
    main()
