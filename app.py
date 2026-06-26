import os
import http.server
import socketserver
import urllib.request
import json

# Render 환경에서 포트 설정
PORT = int(os.environ.get("PORT", 8000))
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KICE 수석출제위원 문항 생성 시스템</title>
    <style>
        body { font-family: 'Malgun Gothic', sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; color: #333; }
        .container { max-width: 800px; margin: auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        h1 { color: #1a3a5f; text-align: center; border-bottom: 2px solid #1a3a5f; padding-bottom: 10px; }
        .mode-selector { display: flex; gap: 10px; margin-bottom: 20px; }
        .mode-btn { flex: 1; padding: 12px; border: 1px solid #1a3a5f; background: white; cursor: pointer; border-radius: 5px; font-weight: bold; }
        .mode-btn.active { background: #1a3a5f; color: white; }
        textarea { width: 100%; height: 200px; padding: 15px; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; resize: vertical; font-size: 15px; }
        button#generate { width: 100%; padding: 15px; background-color: #e67e22; color: white; border: none; border-radius: 8px; font-size: 18px; font-weight: bold; cursor: pointer; margin-top: 20px; }
        #result { margin-top: 30px; padding: 20px; background-color: #fafafa; border-left: 5px solid #1a3a5f; white-space: pre-wrap; line-height: 1.6; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📑 KICE 문항 생성 시스템</h1>
        <div class="mode-selector">
            <button class="mode-btn active" onclick="setMode('Type A')">Type A: 문항 변형</button>
            <button class="mode-btn" onclick="setMode('Type B')">Type B: 자료 기반 출제</button>
        </div>
        <p id="mode-desc"><b>[Type A]</b> 기존 문항의 논리 구조를 유지하며 소재와 보기를 재구성합니다.</p>
        <textarea id="inputData" placeholder="이곳에 원본 문항 혹은 분석할 학술 자료를 입력하세요..."></textarea>
        <button id="generate" onclick="generateProblem()">국가고시급 문항 생성 시작</button>
        <div id="result" style="display:none;"></div>
    </div>

    <script>
        let currentMode = 'Type A';
        function setMode(mode) {
            currentMode = mode;
            document.querySelectorAll('.mode-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('mode-desc').innerHTML = mode === 'Type A' ? 
                '<b>[Type A]</b> 기존 문항의 논리 구조를 유지하며 소재와 보기를 재구성합니다.' : 
                '<b>[Type B]</b> 학술 자료에서 핵심 개념을 추출하여 변별력 있는 신규 문항을 제작합니다.';
        }

        async function generateProblem() {
            const inputData = document.getElementById('inputData').value;
            const resultDiv = document.getElementById('result');
            if(!inputData) { alert('내용을 입력해주세요.'); return; }

            resultDiv.style.display = 'block';
            resultDiv.innerText = '출제 위원들이 문항을 검토 중입니다... 잠시만 기다려 주십시오.';

            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: currentMode, text: inputData })
            });
            const data = await response.json();
            resultDiv.innerText = data.result;
        }
    </script>
</body>
</html>
"""

class AIServerHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(HTML_TEMPLATE.encode('utf-8'))

    def do_POST(self):
        if self.path == '/api/generate':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request_data = json.loads(post_data)
            
            mode = request_data.get('mode')
            text = request_data.get('text')
            
            result = self.call_openai_api(mode, text)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'result': result}).encode('utf-8'))

    def call_openai_api(self, mode, text):
        if not OPENAI_API_KEY:
            return "Error: API Key가 설정되지 않았습니다. Render 환경 변수를 확인하세요."

        system_prompt = f"당신은 한국교육과정평가원 수석 출제위원입니다. {mode} 방식으로 문항을 생성하십시오."
        if mode == 'Type A':
            system_prompt += " 소재와 수치를 변경하되 논리적 뼈대와 난이도는 유지하십시오."
        else:
            system_prompt += " 텍스트의 핵심 개념을 추출하여 수능형 발문으로 신규 제작하십시오."
        
        system_prompt += " 타당성, 논리성, 학술적 언어, 무결성 원칙을 엄수하며 정답과 해설도 포함하십시오."

        api_url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "temperature": 0.7
        }

        try:
            req = urllib.request.Request(api_url, data=json.dumps(data).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                return res_data['choices'][0]['message']['content']
        except Exception as e:
            return f"알 수 없는 오류가 발생했습니다: {str(e)}"

with socketserver.TCPServer(("", PORT), AIServerHandler) as httpd:
    print(f"출제 시스템 서버 가동 중: 포트 {PORT}")
    httpd.serve_forever()
