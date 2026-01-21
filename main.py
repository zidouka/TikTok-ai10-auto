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
    res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
    res.raise_for_status()
    return res.json()['candidates'][0]['content']['parts'][0]['text']

def main():
    print("--- 🚀 Auto Content Generator (Direct Row Logic) ---")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    full_model_name = get_best_model(gemini_key)
    gen_url = f"https://generativelanguage.googleapis.com/v1/{full_model_name}:generateContent?key={gemini_key}"
    
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(creds)
    sh = gc.open("TikTok管理シートAI10").sheet1

    # 1. 未処理の行を探す
    try:
        cell = sh.find("未処理")
        row_num = cell.row
        topic = sh.cell(row_num, 1).value
        print(f"📌 既存の未処理ネタを処理します: Row {row_num}")
    except gspread.exceptions.CellNotFound:
        print("💡 未処理ネタがないため、新規補充して即時実行します...")
        idea_prompt = (
            "Task: Generate 10 unique TikTok themes.\n"
            "Concept: 'Animals doing unexpected human-like activities'.\n"
            "Format: One theme per line. Japanese only."
        )
        new_ideas_text = gemini_request(gen_url, idea_prompt)
        new_ideas = [line.strip() for line in new_ideas_text.split('\n') if line.strip()]
        
        # 最初の1つ目を取得
        topic = new_ideas[0]
        # すべてのネタを書き込む（1つ目は「完了」予定だが、一旦「未処理」で並べる）
        for idea in new_ideas:
            sh.append_row([idea, "未処理"])
        
        # 💡 ここが修正ポイント: 
        # 検索せず、「現在の最終行」をターゲットにする
        row_num = len(sh.col_values(1)) - len(new_ideas) + 1
        print(f"📌 新規補充したネタを処理します: Row {row_num} ({topic})")

    # 2. 生成指示
    script_prompt = (
        f"Task: Create TikTok content for a 10s video about '{topic}'.\n"
        f"Strict Output Format:\n"
        f"[Script]\n"
        f"###\n"
        f"[English Video Prompt]\n"
        f"###\n"
        f"[Caption & Hashtags ONLY]"
    )

    max_retries = 3
    for i in range(max_retries):
        try:
            full_text = gemini_request(gen_url, script_prompt)
            parts = full_text.split("###")
            
            script = parts[0].strip() if len(parts) > 0 else ""
            video_prompt = parts[1].strip() if len(parts) > 1 else ""
            caption_for_api = parts[2].strip() if len(parts) > 2 else ""
            
            # 書き込み
            sh.update_cell(row_num, 2, "完了")
            sh.update_cell(row_num, 3, script)
            sh.update_cell(row_num, 4, video_prompt)
            sh.update_cell(row_num, 5, caption_for_api)
            
            print(f"✨ Row {row_num} 正常に完了しました！")
            break
        except Exception as e:
            print(f"⚠️ リトライ {i+1}: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
