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
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search_retrieval": {}}]
    }
    res = requests.post(url, json=payload)
    if res.status_code == 400:
        payload.pop("tools")
        res = requests.post(url, json=payload)
    res.raise_for_status()
    return res.json()['candidates'][0]['content']['parts'][0]['text']

def main():
    print("--- 🚀 Auto Content Generator (Restore Original Style) ---")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    full_model_name = get_best_model(gemini_key)
    gen_url = f"https://generativelanguage.googleapis.com/v1/{full_model_name}:generateContent?key={gemini_key}"
    
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(creds)
    sh = gc.open("TikTok管理シートAI10").sheet1

    # --- 列のタイトルから列番号を自動取得 ---
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
    
    # トレンド指示
    if not user_input:
        trend_instruction = "Search for the latest viral TikTok animal trends (Jan 2026) and incorporate them."
    elif user_input in ["オフ", "off", "OFF", "なし"]:
        trend_instruction = "Focus only on the given topic. Do not include specific external trends."
    else:
        trend_instruction = f"Priority Trend Keyword: {user_input}"

    # 1. 未処理の行を探す
    cell = sh.find("未処理")
    
    if cell:
        row_num = cell.row
        topic = sh.cell(row_num, col_topic).value if col_topic else sh.cell(row_num, 1).value
        print(f"📌 既存のネタを処理: Row {row_num}")
    else:
        print("💡 ネタ補充中...")
        all_topics = sh.col_values(col_topic) if col_topic else sh.col_values(1)
        history_str = ", ".join(all_topics[-6:])
        idea_prompt = f"{trend_instruction}\nBased on this, generate exactly ONE unique and cute TikTok theme. Avoid duplicates with: [{history_str}]. Concept: 'Animals doing human-like activities'. Format: Theme name in Japanese only."
        topic = gemini_request(gen_url, idea_prompt).strip()
        new_row = [""] * len(headers)
        if col_topic: new_row[col_topic-1] = topic
        if col_status: new_row[col_status-1] = "未処理"
        sh.append_row(new_row)
        row_num = len(sh.get_all_values())
        print(f"📌 新ネタ: {topic}")

    # 2. 生成指示（2～7行目の形式を再現するためのプロンプト）
    script_prompt = (
        f"Context: {trend_instruction}\n"
        f"Task: Create TikTok content for a 10s video about '{topic}'.\n"
        f"Follow the style of previous successful outputs: \n"
        f"- Script: Engaging Japanese dialogue or narration.\n"
        f"- Video Prompt: High-quality, detailed English cinematic prompt including Scene 1, Scene 2, Scene 3, camera angles, lighting, and specific movements.\n"
        f"- Caption: Viral Japanese text with 5 hashtags.\n\n"
        f"Output MUST use '###' separators:\n"
        f"(Japanese Script)\n###\n(Detailed English Video Prompt with Scenes)\n###\n(Viral Caption & 5 Tags)"
    )

    try:
        full_text = gemini_request(gen_url, script_prompt)
        parts = [p.strip() for p in full_text.split("###")]
        
        script, video_prompt, caption = (parts[0], parts[1], parts[2]) if len(parts) >= 3 else (full_text, "Error", "Error")

        # 書き込み
        if col_status:  sh.update_cell(row_num, col_status, "構成済み")
        if col_script:  sh.update_cell(row_num, col_script, script)
        if col_prompt:  sh.update_cell(row_num, col_prompt, video_prompt)
        if col_caption: sh.update_cell(row_num, col_caption, caption)
        print(f"✨ Row {row_num} 書き込み完了！過去の形式を再現しました。")
    except Exception as e:
        print(f"❌ エラー: {e}")

if __name__ == "__main__":
    main()
