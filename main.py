import os
import gspread
import google.auth
import requests
import time
from datetime import datetime

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
    max_retries = 10
    for attempt in range(max_retries):
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "tools": [{"google_search_retrieval": {}}]
            }
            res = requests.post(url, json=payload)
            
            if res.status_code == 429:
                wait_time = 60 + (attempt * 30)
                print(f"⏳ [API Limit] Waiting {wait_time}s... ({attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            
            if res.status_code == 400 or (attempt > 2 and res.status_code != 200):
                print("⚠️ Switching to no-search mode...")
                payload.pop("tools", None)
                res = requests.post(url, json=payload)
            
            res.raise_for_status()
            return res.json()['candidates'][0]['content']['parts'][0]['text']
            
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"❌ Final attempt failed: {e}")
                raise e
            time.sleep(10)
    return None

def main():
    # 💡 現在の年月日と月名を詳細に取得
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")  # 例: 2026-01-23
    current_month = now.strftime("%B")       # 例: January
    current_year = now.year
    
    print("--- 🚀 Auto Content Generator (Fixed Strict Version) ---")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    full_model_name = get_best_model(gemini_key)
    gen_url = f"https://generativelanguage.googleapis.com/v1/{full_model_name}:generateContent?key={gemini_key}"
    
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(creds)
    sh = gc.open("TikTok管理シートAI10").sheet1

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
    col_audio    = get_col_index("音声生成用プロンプト（英語）") # 💡 追加

    user_input = sh.cell(2, col_trend).value if col_trend else None
    trend_instruction = f"Priority Trend: {user_input}" if user_input else "Search for latest viral TikTok animal trends."

    # 1. ネタの補充/取得
    cell = sh.find("未処理")
    if cell:
        row_num = cell.row
        topic = sh.cell(row_num, col_topic).value if col_topic else sh.cell(row_num, 1).value
        print(f"📌 Processing: Row {row_num} -> {topic}")
    else:
        print("💡 Generating new idea...")
        # 【修正】ネタ出しプロンプトを英語で厳格化
        idea_prompt = (
            f"Step 1: Search for the most viral TikTok animal trends specifically around {current_date} ({current_month}).\n"
            f"Step 2: Based on today's search results and seasonal context of {current_month}, generate 10 unique TikTok video themes.\n"
            f"Concept: Animals doing unexpected human-like activities. Priority Trend: {user_input if user_input else 'Latest viral trends'}\n"
            "Constraints: Provide 10 themes in Japanese. One theme per line. \n"
            "DO NOT include any English descriptions, numbering, or introductory text. \n"
            "Example format:\n"
            "雪かきをする柴犬\n"
            "こたつでみかんを食べる猫"
        )
        raw_idea = gemini_request(gen_url, idea_prompt)
        topic = raw_idea.split('\n')[-1].replace('**', '').replace('Concept:', '').strip()
        
        new_row = [""] * len(headers)
        if col_topic: new_row[col_topic-1] = topic
        if col_status: new_row[col_status-1] = "未処理"
        sh.append_row(new_row)
        row_num = len(sh.get_all_values())
        print(f"✅ Added new idea: {topic}")

    print("⏲️ Cooling down for 15s...")
    time.sleep(15)

    # 2. 生成指示 【修正】出力を「###」で厳格に固定
    script_prompt = (
        f"Step 1: Search for the latest trending keywords, sounds, or hashtags on TikTok as of {current_date}.\n"
        f"Step 2: Create TikTok content for a 10-second video about '{topic}'.\n"
        "Output Requirements:\n"
        "1. A concise Japanese script (approx. 10 seconds).\n"
        "2. A detailed English video prompt for Kling/Luma AI (10s continuous cinematic shot).\n"
        f"3. A viral Japanese caption: **MUST incorporate 2-3 of the latest trending slangs.**\n"
        "\n"
        "**Hashtag Strategy (Strictly follow this):**\n"
        "Include exactly 5 Japanese hashtags at the end of the caption:\n"
        " - 2 Big-word tags (Broad categories like #猫 #おもしろ)\n"
        " - 2 Middle-word tags (Genre specific like #癒やし動画 #動物のいる暮らし)\n"
        f" - 1 Small-word tag (Specific to this theme like #{topic})\n"
        "\n"
        "Strict Format: Separate the four elements using '###' ONLY. Do not include any other text.\n"
        "Format Example:\n"
        "台本の内容\n"
        "###\n"
        "Cinematic 4k video of...\n"
        "###\n"
        "バズる説明文とハッシュタグ"
        "###\n"
        "High-quality sound of a cat meowing with upbeat lo-fi music" # 💡 追加
    )

    print(f"✍️ Generating content for: {topic}")
    full_text = gemini_request(gen_url, script_prompt)
    
    if full_text:
        # 分割ロジック
        parts = [p.strip() for p in full_text.split("###")]
        
        # 【修正】分割後のデータを各列に正しく割り当て
        script = parts[0] if len(parts) > 0 else "Error"
        video_prompt = parts[1] if len(parts) > 1 else "Error"
        caption = parts[2] if len(parts) > 2 else "Error"
        audio_prompt = parts[3] if len(parts) > 3 else "Error" # 💡 追加

        # 【修正】正しい列番号に更新
        if col_status:  sh.update_cell(row_num, col_status, "構成済み")
        if col_script:  sh.update_cell(row_num, col_script, script)
        if col_prompt:  sh.update_cell(row_num, col_prompt, video_prompt)
        if col_caption: sh.update_cell(row_num, col_caption, caption)
        if col_audio:   sh.update_cell(row_num, col_audio, audio_prompt) # 💡 追加
        print(f"✨ Row {row_num} Processing Complete!")

if __name__ == "__main__":
    main()
