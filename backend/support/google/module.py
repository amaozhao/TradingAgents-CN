import json

import requests

API_KEY = "AIzaSyC3JdZVjblI0rfT_SNXXL5a4kvZ13_12CE"  # 请替换为您的真实API密钥
MODEL_NAME = "gemini-2.0-flash"
PROMPT = "请用一句话解释人工智能。"


def request_gemini_summary(prompt: str = PROMPT) -> requests.Response:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": API_KEY}
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    return requests.post(url, headers=headers, data=json.dumps(data), timeout=30)


def main() -> None:
    response = request_gemini_summary()
    if response.status_code == 200:
        result = response.json()
        print(result["candidates"][0]["content"]["parts"][0]["text"])
        return

    print(f"请求失败，状态码: {response.status_code}")
    print(response.text)


if __name__ == "__main__":
    main()
