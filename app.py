import os
import http.server
import socketserver
import json
import urllib.request

# 1. 서버 설정 (배포용 포트 대응)
PORT = int(os.environ.get("PORT", 8000))

# 2. 웹 화면 (HTML) 설계
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NEIS 기록 생성기</title>
    <style>
        body { font-family: 'Pretendard', sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; background: #f5f7f9; }
        .card { background: white; padding: 25px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        h2 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        textarea { width: 100%; height: 120px; border: 1px solid #ddd; border-radius: 8px; padding: 10px; box-sizing: border-box; resize: none; }
        button { width: 100%; background: #3498db; color: white; border: none; padding: 12px; border-radius: 8px; cursor: pointer; margin-top: 10px; font-weight: bold; }
        #result { margin-top: 20px; white-space: pre-wrap; padding: 15px; background: #eef2f7; border-radius: 8px; min-height: 50px; font-size: 0.95em; line-height: 1.6; }
    </style>
</head>
<body>
    <div class="card">
        <h2>📑 NEIS 기록 자동 생성</h2>
        <p style="font-size:0.8em; color:gray;">키워드나 내용을 입력하면 NEIS 표준 문체로 변환합니다.</p>
        <textarea id="userInput" placeholder="예: 수학 시간에 미분 개념을 잘 이해하고 친구들에게 설명해줌"></textarea>
        <button onclick="generate()">기록 생성하기</button>
        <div id="result" id="placeholder">결과가 여기에 표시됩니다...</div>
    </div>

    <script>
        async function generate() {
            const input = document.getElementById('userInput').value;
            const resDiv = document.getElementById('result');
            if(!input) return alert('내용을 입력하세요!');
            
            resDiv.innerText = 'GPT가 작성 중입니다...';
            
            const response = await fetch('/api', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text: input})
            });
            const data = await response.json();
            resDiv.innerText = data.result || '오류가 발생했습니다.';
        }
    </script>
</body>
</html>
"""

# 3. 기능 처리 (백엔드 로직)
class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_CONTENT.encode("utf-8"))

    def do_POST(self):
        if self.path == '/api':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            user_input = json.loads(post_data).get('text', '')
            
            api_key = os.environ.get("OPENAI_API_KEY")
            prompt = f"다음 내용을 NEIS 학교생활기록부 문체(~함, ~임 명사형 종결)로 정제해줘. 분량은 200자 내외로: {user_input}"
            
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}]
            }
            
            req = urllib.request.Request("https://api.openai.com/v1/chat/completions")
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", f"Bearer {api_key}")
            
            try:
                with urllib.request.urlopen(req, data=json.dumps(payload).encode()) as f:
                    response = json.loads(f.read().decode())
                    result_text = response['choices'][0]['message']['content']
            except Exception as e:
                result_text = f"에러 발생: {str(e)}"

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"result": result_text}).encode())

# 4. 앱 실행
with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
    print(f"서버 작동 중: 포트 {PORT}")
    httpd.serve_forever()
