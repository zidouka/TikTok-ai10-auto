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
    """Gemini APIへのリクエスト共通処理"""
    res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
    res.raise_for_status()
    return res.json()['candidates'][0]['content']['parts'][0]['text']

def main():
    print("--- 🚀 Auto Content Generator Started ---")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    full_model_name = get_best_model(gemini_key)
    gen_url = f"https://generativelanguage.googleapis.com/v1/{full_model_name}:generateContent?key={gemini_key}"
    
    # 1. 認証とシート接続
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(creds)
    sh = gc.open("TikTok管理シートAI").sheet1

    # 2. ネタの補充チェック
    # A列が空、または「未処理」が一つもない場合にネタを自動生成
    try:
        cell = sh.find("未処理")
    except gspread.exceptions.CellNotFound:
        print("💡 「未処理」のネタがありません。新しいネタを生成中...")
        idea_prompt = (
            "Task: Generate 1 unique video themes for TikTok.\n"
            "Concept: 'Cute animals doing unexpected human-like activities' (e.g., dancing, cooking, office work, playing instruments).\n"
            "Format: One theme per line. Japanese only. No numbering, no extra text."
        )
        new_ideas_text = gemini_request(gen_url, idea_prompt)
        new_ideas = [line.strip() for line in new_ideas_text.split('\n') if line.strip()]
        
        for idea in new_ideas:
            sh.append_row([idea, "未処理"])
        print(f"✅ {len(new_ideas)}個の新しいネタを補充しました。")
        cell = sh.find("未処理") # 補充したので再度検索

    row_num = cell.row
    topic = sh.cell(row_num, 1).value
    print(f"📌 Row {row_num} 処理開始: {topic}")

    # 3. 台本と英語プロンプトの生成
    script_prompt = (
        f"Task: Create a concise TikTok script for exactly a 10-second video about the theme: '{topic}'.\n"
        f"Language: The script must be in Japanese.\n"
        f"Additional Task: Provide a powerful English prompt for an AI video generator (Kling or Luma).\n"
        f"Constraint: Optimize for a single 10-second continuous shot of animal doing unexpected action.\n"
        f"\n"
        f"Strict Output Format:\n"
        f"[Japanese Script Content]\n"
        f"###\n"
        f"[Concise English Video Prompt]"
    )

    # リトライ処理
    max_retries = 3
    for i in range(max_retries):
        try:
            full_text = gemini_request(gen_url, script_prompt)
            if "###" in full_text:
                parts = full_text.split("###")
                script, video_prompt = parts[0].strip(), parts[1].strip()
            else:
                script, video_prompt = full_text.strip(), f"A high-quality 10s video of {topic}."
            
            sh.update_cell(row_num, 2, "完了")
            sh.update_cell(row_num, 3, script)
            sh.update_cell(row_num, 4, video_prompt)
            print("✨ 正常に完了しました！")
            break
        except Exception as e:
            print(f"⚠️ エラー (試行 {i+1}): {e}")
            time.sleep(15)

if __name__ == "__main__":
    main()
