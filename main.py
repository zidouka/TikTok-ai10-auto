def gemini_request(url, prompt):
    # 最新の Google Search Retrieval 形式
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search_retrieval": {}}]
    }
    
    res = requests.post(url, json=payload)
    
    # 400エラー（ツール非対応など）が出た場合のバックアップ処理
    if res.status_code == 400:
        error_detail = res.json().get('error', {}).get('message', 'Unknown Error')
        print(f"\n⚠️ 【バックアップ処理始動】Google検索ツールを使用できませんでした。")
        print(f"   理由: {error_detail}")
        print(f"   対策: 通常モード（検索なし）で再送します...\n")
        
        # toolsを削除して通常のリクエストとして再送
        payload.pop("tools")
        res = requests.post(url, json=payload)
        
    res.raise_for_status()
    return res.json()['candidates'][0]['content']['parts'][0]['text']
