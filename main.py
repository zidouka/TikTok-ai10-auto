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
        print("⚠️ 【通知】Google検索ツールを使わず通常モードで生成します。")
        payload.pop("tools")
        res = requests.post(url, json=payload)
    res.raise_for_status()
    return res.json()['candidates'][0]['content']['parts'][0]['text']

def main():
    print("--- 🚀 TikTok Auto Content System ---")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    full_model_name = get_best_model(gemini_key)
    gen_url = f"https://generativelanguage.googleapis.com/v1/{full_model_name}:generateContent?key={gemini_key}"
    
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(creds)
    sh = gc.open("TikTok管理シートAI10").sheet1

    # --- 💡 列の自動判定 ---
    headers = sh.row_values(1)
    print(f"📡 シートのヘッダーを確認しました: {headers}")

    def get_col_index(name):
        try:
            return headers.index(name) + 1
        except ValueError:
            return None

    col_topic = get_col_index("ネタ（Input）")
    col_status = get_col_index("ステータス")
    col_script = get_col_index("60秒台本")
    col_prompt = get_col_index("動画生成用プロンプト（英語）")
    col_caption = get_col_index("キャプション＆タグ")
    col_trend = get_col_index("トレンド設定")

    # トレンド設定読み取り
    user_input = sh.cell(2, col_trend).value if col_trend else None
    trend_instruction = f"Target Trend: {user_input}" if user_input else "Search for latest viral TikTok animal trends."

    # --- 1. ネタの検索と自動補充 ---
    row_num = None
    topic = None

    try:
        # 「未処理」の行を探す
        status_cells = sh.findall("未処理")
        # 「ステータス」列にあるものだけを対象にする
        unprocessed_row = None
        if col_status:
            for c in status_cells:
                if c.col == col_status:
                    unprocessed_row = c.row
                    break
        
        if unprocessed_row:
            row_num = unprocessed_row
            topic = sh.cell(row_num, col_topic).value
            print(f"📌 既存の未処理ネタを処理します: Row {row_num} [{topic}]")
        else:
            # ネタがないのでAIが自動で考える
            print("💡 '未処理'が見つかりません。AIが新しいネタを自動補充します...")
            all_topics = sh.col_values(col_topic) if col_topic else []
            history_str = ", ".join(all_topics[-5:])
            
            idea_prompt = (
                f"{trend_instruction}\n"
                "Task: Generate exactly ONE unique and cute TikTok theme (Animal doing human-like activity).\n"
                f"History: {history_str}\n"
                "Format: Theme name only (Japanese)."
            )
            topic = gemini_request(gen_url, idea_prompt).strip().replace('"', '')
            
            # 新しい行を追加
            new_row = [""] * len(headers)
            if col_topic: new_row[col_topic-1] = topic
            if col_status: new_row[col_status-1] = "未処理"
            
            sh.append_row(new_row)
            row_num = len(sh.get_all_values())
            print(f"✅ 新ネタをシートに追加完了: {topic} (Row {row_num})")

    except Exception as e:
        print(f"❌ ネタの取得/追加中にエラーが発生しました: {e}")
        return

    # --- 2. 構成の生成 ---
    print(f"✍️ '{topic}' の台本とプロンプトを生成中...")
    script_prompt = (
        f"Context: {trend_instruction}\n"
        f"Task: Create TikTok content for a 60s video about '{topic}'.\n"
        f"Output structure: (Japanese Script) ### (English Video Prompt) ### (Viral Caption & 5 Tags)"
    )

    try:
        full_text = gemini_request(gen_url, script_prompt)
        parts = [p.strip() for p in full_text.split("###")]
        
        script = parts[0] if len(parts) > 0 else "生成失敗"
        video_prompt = parts[1] if len(parts) > 1 else f"Cinematic {topic}"
        caption = parts[2] if len(parts) > 2 else f"{topic} #TikTok"

        # スプレッドシートへ書き込み
        sh.update_cell(row_num, col_status, "構成済み")
        sh.update_cell(row_num, col_script, script)
        sh.update_cell(row_num, col_prompt, video_prompt)
        sh.update_cell(row_num, col_caption, caption)
        print(f"✨ Row {row_num} すべての書き込みが完了しました！")

    except Exception as e:
        print(f"❌ 生成・書き込み中にエラーが発生しました: {e}")

if __name__ == "__main__":
    main()
