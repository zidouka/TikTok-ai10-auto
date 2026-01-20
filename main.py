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

def main():
    print("--- 🚀 Program Started (Latest Model & English Prompt) ---")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    
    # 1. Google Cloud Authentication
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(creds)

    # 2. Spreadsheet Operations
    try:
        sh = gc.open("TikTok管理シートAI60").sheet1
        cell = sh.find("未処理")
        row_num = cell.row
        topic = sh.cell(row_num, 1).value
        print(f"📌 Row {row_num} Processing: {topic}")
    except:
        print("✅ No 'unprocessed' rows found.")
        return

    # 3. Get Model Name
    full_model_name = get_best_model(gemini_key)
    print(f"🤖 Model: {full_model_name}")

    # 4. Gemini API Execution with English Prompt
    gen_url = f"https://generativelanguage.googleapis.com/v1/{full_model_name}:generateContent?key={gemini_key}"
    
    # 指示を英語に変更。ただし「台本は日本語で」と指定しています。
    prompt = (
        f"Task: Create a 30-second TikTok script about the theme: '{topic}'.\n"
        f"Language: The script must be in Japanese.\n"
        f"Additional Task: Provide a detailed English prompt for an AI video generator (like Luma or Kling) to visualize this content.\n"
        f"\n"
        f"Strict Output Format:\n"
        f"[Japanese Script Content]\n"
        f"###\n"
        f"[English Video Prompt]"
    )

    max_retries = 3
    retry_delay = 15

    for i in range(max_retries):
        try:
            print(f"🧠 Requesting AI... (Attempt {i+1}/{max_retries})")
            res = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]})
            
            if res.status_code in [503, 429]:
                print(f"⚠️ Server overloaded (Error {res.status_code}). Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                continue
            
            res.raise_for_status()
            full_text = res.json()['candidates'][0]['content']['parts'][0]['text']
            
            # 5. Split and Update Spreadsheet
            if "###" in full_text:
                parts = full_text.split("###")
                script = parts[0].strip()
                video_prompt = parts[1].strip()
            else:
                script = full_text.strip()
                video_prompt = f"A high-quality cinematic video of {topic}"
            
            print("💾 Updating spreadsheet...")
            sh.update_cell(row_num, 2, "完了")
            sh.update_cell(row_num, 3, script)
            sh.update_cell(row_num, 4, video_prompt)
            print("✨ Successfully completed!")
            return

        except Exception as e:
            print(f"❌ Attempt {i+1} failed: {e}")
            if i < max_retries - 1:
                time.sleep(retry_delay)
            else:
                sh.update_cell(row_num, 2, "Error")

if __name__ == "__main__":
    main()
