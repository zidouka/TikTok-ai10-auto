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
    print("--- 🚀 Auto Content Generator (One-Topic & Fix Column Edition) ---")
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
        print("💡 ネタがないため【1つだけ】補充します...")
        idea_prompt = (
            "Task: Generate exactly ONE unique TikTok theme.\n"
            "Concept: 'Animals doing unexpected human-like activities' (e.g., dancing, cooking, office work).\n"
            "Format: Just the theme name in Japanese. No extra text or symbols."
        )
        topic = gemini_request(gen_url, idea_prompt).strip()
        
        # 1つだけ補充
        sh.append_row([topic, "未処理"])
        
        # 追加した行を特定
        all_rows = sh.get_all_values()
        row_num = len(all_rows)
        print(f"📌 補充したネタを処理: Row {row_num} ({topic})")

    # 2. 生成指示（区切り文字のみを出力させるよう厳密に指示）
    script_prompt = (
        f"Task: Create TikTok content for a 10s video about '{topic}'.\n"
        f"Output MUST follow this structure exactly with '###' separators. \n"
        f"DO NOT include any labels like '[Script]' or '[English Video Prompt]'.\n"
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
            # ### で分割。空白や余計な記号を極限まで排除
            parts = [p.strip() for p in full_text.split("###")]
            
            if len(parts) >= 3:
                script = parts[0]
                video_prompt = parts[1]
                caption = parts[2]
            else:
                # 分割失敗時のフォールバック
                script = full_text.split("###")[0].strip()
                video_prompt = f"Cinematic 10s video of {topic}"
                caption = f"{topic} #TikTok #AI"

            # 書き込み
            sh.update_cell(row_num, 2, "完了")
            sh.update_cell(row_num, 3, script)
            sh.update_cell(row_num, 4, video_prompt) # D列：英語プロンプト本文のみ
            sh.update_cell(row_num, 5, caption)      # E列：バズるキャプション
            
            print(f"✨ Row {row_num} 正常に書き込み完了！")
            break
        except Exception as e:
            print(f"⚠️ リトライ {i+1}: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
