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
    print("--- 🚀 Auto Content Generator (Step 2: Anti-Duplicate [Recent 6]) ---")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    full_model_name = get_best_model(gemini_key)
    gen_url = f"https://generativelanguage.googleapis.com/v1/{full_model_name}:generateContent?key={gemini_key}"
    
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(creds)
    sh = gc.open("TikTok管理シートAI10").sheet1

    # 1. 未処理の行を探す
    cell = sh.find("未処理")
    
    if cell:
        row_num = cell.row
        topic = sh.cell(row_num, 1).value
        print(f"📌 既存のネタを処理: Row {row_num}")
    else:
        print("💡 ネタがないため補充します。直近6件の重複チェック中...")
        
        # A列（ネタの全履歴）を取得
        all_topics = sh.col_values(1)
        # 💡 ここで末尾から最大6件を抽出
        history_topics = all_topics[-6:] if len(all_topics) >= 6 else all_topics
        history_str = ", ".join(history_topics)
        
        idea_prompt = (
            "Task: Generate exactly ONE unique TikTok theme.\n"
            f"Recent themes (DO NOT REPEAT): [{history_str}]\n"
            "Concept: 'Animals doing unexpected human-like activities'.\n"
            "Format: Just the theme name in Japanese. No extra text."
        )
        topic = gemini_request(gen_url, idea_prompt).strip()
        
        # 1つだけ補充
        sh.append_row([topic, "未処理"])
        all_rows = sh.get_all_values()
        row_num = len(all_rows)
        print(f"📌 新しいネタを補充しました（直近6件と被り回避）: {topic}")

    # 2. 生成指示
    script_prompt = (
        f"Task: Create TikTok content for a 10s video about '{topic}'.\n"
        f"Output MUST follow this structure exactly with '###' separators. \n"
        f"DO NOT include any labels like '[Script]'.\n"
        f"\n"
        f"Structure:\n"
        f"(Japanese Script)\n"
        f"###\n"
        f"(English Video Prompt for Kling/Luma)\n"
        f"###\n"
        f"(Viral Caption and Hashtags for TikTok)\n"
        f"\n"
        f"Constraint for Caption: Hooky opening, 5 trending tags, and NO labels."
    )

    max_retries = 3
    for i in range(max_retries):
        try:
            full_text = gemini_request(gen_url, script_prompt)
            parts = [p.strip() for p in full_text.split("###")]
            
            if len(parts) >= 3:
                script, video_prompt, caption = parts[0], parts[1], parts[2]
            else:
                script = full_text.split("###")[0].strip()
                video_prompt = f"Cinematic 10s video of {topic}"
                caption = f"{topic} #TikTok #AI"

            sh.update_cell(row_num, 2, "完了")
            sh.update_cell(row_num, 3, script)
            sh.update_cell(row_num, 4, video_prompt)
            sh.update_cell(row_num, 5, caption)
            
            print(f"✨ Row {row_num} 書き込み完了！")
            break
        except Exception as e:
            print(f"⚠️ リトライ {i+1}: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
