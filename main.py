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
    print("--- 🚀 Auto Content Generator (API Ready Format) ---")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    full_model_name = get_best_model(gemini_key)
    gen_url = f"https://generativelanguage.googleapis.com/v1/{full_model_name}:generateContent?key={gemini_key}"
    
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(creds)
    # スプレッドシート名を確認してください
    sh = gc.open("TikTok管理シートAI10").sheet1

    # 1. ネタの補充チェック
    try:
        cell = sh.find("未処理")
    except gspread.exceptions.CellNotFound:
        print("💡 ネタを補充中...")
        idea_prompt = (
            "Task: Generate 10 unique TikTok themes.\n"
            "Concept: 'Animals doing unexpected human-like activities' (e.g., dancing, cooking).\n"
            "Format: One theme per line. Japanese only. No extra text."
        )
        new_ideas_text = gemini_request(gen_url, idea_prompt)
        new_ideas = [line.strip() for line in new_ideas_text.split('\n') if line.strip()]
        for idea in new_ideas:
            sh.append_row([idea, "未処理"])
        cell = sh.find("未処理")

    row_num = cell.row
    topic = sh.cell(row_num, 1).value
    print(f"📌 Row {row_num}: {topic}")

    # 2. 生成指示（将来の自動投稿API連携を見据えたフォーマット固定版）
    script_prompt = (
        f"Task: Create TikTok content for a 10s video about '{topic}'.\n"
        f"Output Structure:\n"
        f"1. A concise Japanese script.\n"
        f"2. A detailed English video prompt (for Kling/Luma).\n"
        f"3. A viral Caption & Hashtags for TikTok API.\n"
        f"\n"
        f"Constraint for 'Caption & Hashtags':\n"
        f"- Focus on the latest TikTok algorithm (hooky opening, curiosity-driven).\n"
        f"- Include 5 trending hashtags.\n"
        f"- DO NOT include labels like 'Caption:' or 'Tags:'.\n"
        f"- Output ONLY the final text to be posted.\n"
        f"\n"
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
            # APIがそのまま使えるようにラベルを一切含ませない形式
            caption_for_api = parts[2].strip() if len(parts) > 2 else ""
            
            sh.update_cell(row_num, 2, "完了")
            sh.update_cell(row_num, 3, script)
            sh.update_cell(row_num, 4, video_prompt)
            sh.update_cell(row_num, 5, caption_for_api)
            
            print(f"✨ Row {row_num} 完了 (API用フォーマット)")
            break
        except Exception as e:
            print(f"⚠️ Retry {i+1}: {e}")
            time.sleep(15)

if __name__ == "__main__":
    main()
