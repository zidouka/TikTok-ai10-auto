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
    print("--- 🚀 Program Started (10s Focused Version) ---")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    
    # 1. Google Cloud Authentication
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(creds)

    # 2. Spreadsheet Operations
    try:
        sh = gc.open("TikTok管理シートAI10").sheet1
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

    # 4. Gemini API Execution (Optimized for exactly 10s clip)
    gen_url = f"https://generativelanguage.googleapis.com/v1/{full_model_name}:generateContent?key={gemini_key}"
    
    # プロンプトを「10秒前後」に厳密に固定し、コスト効率を最大化します
    prompt = (
        f"Task: Create a concise TikTok script for exactly a 10-second video about the theme: '{topic}'.\n"
        f"Language: The script must be in Japanese.\n"
        f"Additional Task: Provide a powerful English prompt for an AI video generator (Kling or Luma).\n"
        f"Video Length Constraint: Optimize for a single 10-second continuous shot.\n"
        f"Focus: Highly dynamic movement of the animal (dancing, cooking, etc.) that fits perfectly in a 10s timeframe.\n"
        f"\n"
        f"Strict Output Format:\n"
        f"[Japanese Script Content]\n"
        f"###\n"
        f"[Concise English Video Prompt]"
    )

    max_retries = 3
    retry_delay = 15

    for i in range(max_retries):
        try:
            print(f"🧠 Requesting AI... (Attempt {i+1}/{max_retries})")
            res = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]})
            
            if res.status_code in [503, 429]:
                print(f"⚠️ Server overloaded. Retrying in {retry_delay}s...")
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
                video_prompt = f"A high-quality 10s video of {topic} with dynamic motion."
            
            print("💾 Updating spreadsheet...")
            sh.update_cell(row_num, 2, "完了")
            sh.update_cell(row_num, 3, script)
            sh.update_cell(row_num, 4, video_prompt)
            print("✨ Successfully completed (10s mode)!")
            return

        except Exception as e:
            print(f"❌ Attempt {i+1} failed: {e}")
            if i < max_retries - 1:
                time.sleep(retry_delay)
            else:
                sh.update_cell(row_num, 2, "Error")

if __name__ == "__main__":
    main()
