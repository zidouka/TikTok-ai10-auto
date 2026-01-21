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
    print("--- 🚀 Auto Content Generator (Step 4: Trend Hybrid Mode [F2]) ---")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    full_model_name = get_best_model(gemini_key)
    gen_url = f"https://generativelanguage.googleapis.com/v1/{full_model_name}:generateContent?key={gemini_key}"
    
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(creds)
    sh = gc.open("TikTok管理シートAI10").sheet1

    # 💡 F2セルからユーザー指定のトレンドワードを取得
    user_trend = sh.acell('F2').value
    if user_trend:
        trend_instruction = f"Priority Trend Keyword: {user_trend} (Incorporate this theme/style into the script and video!)"
        print(f"✅ ユーザー指定トレンド(F2)を使用中: {user_trend}")
    else:
        trend_instruction = "Search for the latest viral TikTok animal trends (Jan 2026) and incorporate them."
        print("🔍 自動トレンド検索モードで実行中...")

    # 1. 未処理の行を探す
    cell = sh.find("未処理")
    
    if cell:
        row_num = cell.row
        topic = sh.cell(row_num, 1).value
        print(f"📌 既存のネタを処理: Row {row_num}")
    else:
        # ネタ補充時もトレンドを考慮
        print("💡 最新トレンドに基づきネタ補充中...")
        all_topics = sh.col_values(1)
        history_topics = all_topics[-6:] if len(all_topics) >= 6 else all_topics
        history_str = ", ".join(history_topics)
        
        idea_prompt = (
            f"{trend_instruction}\n"
            "Based on this, generate exactly ONE unique and cute TikTok theme.\n"
            f"Avoid duplicates with: [{history_str}]\n"
            "Concept: 'Animals doing human-like activities'. Format: Theme name in Japanese only."
        )
        topic = gemini_request(gen_url, idea_prompt).strip()
        sh.append_row([topic, "未処理"])
        all_rows = sh.get_all_values()
        row_num = len(all_rows)
        print(f"📌 トレンド反映済みの新ネタ: {topic}")

    # 2. 生成指示
    script_prompt = (
        f"Context: {trend_instruction}\n"
        f"Task: Create TikTok content for a 10s video about '{topic}'.\n"
        f"Incorporate latest visual styles and popular audio cues.\n"
        f"Output MUST follow this structure with '###' separators:\n"
        f"(Japanese Script)\n###\n(English Video Prompt)\n###\n(Viral Caption & 5 Trending Tags)"
    )

    max_retries = 3
    for i in range(max_retries):
        try:
            full_text = gemini_request(gen_url, script_prompt)
            parts = [p.strip() for p in full_text.split("###")]
            
            if len(parts) >= 3:
                script, video_prompt, caption = parts[0], parts[1], parts[2]
            else:
                script, video_prompt, caption = full_text.split("###")[0], f"Cinematic {topic}", f"{topic} #TikTok"

            # 書き込み
            sh.update_cell(row_num, 2, "構成済み")
            sh.update_cell(row_num, 3, script)
            sh.update_cell(row_num, 4, video_prompt)
            sh.update_cell(row_num, 5, caption)
            
            print(f"✨ Row {row_num} 書き込み完了！")
            break
        except Exception as e:
            print(f"⚠️ リトライ {i+1}:
