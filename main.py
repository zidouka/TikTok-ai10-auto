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
    print("--- 🚀 Auto Content Generator (Stability Version) ---")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    full_model_name = get_best_model(gemini_key)
    gen_url = f"https://generativelanguage.googleapis.com/v1/{full_model_name}:generateContent?key={gemini_key}"
    
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(creds)
    sh = gc.open("TikTok管理シートAI10").sheet1

    # 1. 未処理の行を探す (findの戻り値を直接チェックする安全な方法)
    cell = sh.find("未処理")
    
    if cell:
        row_num = cell.row
        topic = sh.cell(row_num, 1).value
        print(f"📌 既存のネタを処理: Row {row_num}")
    else:
        print("💡 ネタがないため補充します...")
        idea_prompt = (
            "Task: Generate 10 unique TikTok themes.\n"
            "Concept: 'Animals doing unexpected human-like activities'.\n"
            "Format: One theme per line. Japanese only."
        )
        new_ideas_text = gemini_request(gen_url, idea_prompt)
        new_ideas = [line.strip() for line in new_ideas_text.split('\n') if line.strip()]
        
        # 最初のネタを今回のターゲットにする
        topic = new_ideas[0]
        
        # ネタを補充
        for idea in new_ideas:
            sh.append_row([idea, "未処理"])
        
        # 補充した直後の行をターゲットにする
        # 全体の行数から、今追加した数（10個）を逆算して最初の行を特定
        all_rows = sh.get_all_values()
        row_num = len(all_rows) - len(new_ideas) + 1
        print(f"📌 補充したてのネタを処理: Row {row_num}")

    # 2. 生成指示 (API用フォーマット)
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
            caption = parts[2].strip() if len(parts) > 2 else ""
            
            # 書き込み
            sh.update_cell(row_num, 2, "完了")
            sh.update_cell(row_num, 3, script)
            sh.update_cell(row_num, 4, video_prompt)
            sh.update_cell(row_num, 5, caption)
            
            print(f"✨ Row {row_num} 完了！")
            break
        except Exception as e:
            print(f"⚠️ リトライ {i+1}: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
