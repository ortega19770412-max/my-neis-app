import os
import http.server
import socketserver
import urllib.request
import json

# 환경 설정
PORT = int(os.environ.get("PORT", 8000))
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KICE 초대형 언어모델 기반 문항 생성 시스템</title>
    <style>
        :root { --kice-blue: #1a3a5f; --kice-orange: #e67e22; }
        body { font-family: 'Malgun Gothic', sans-serif; background-color: #f0f2f5; margin: 0; padding: 20px; line-height: 1.6; }
        .container { max-width: 900px; margin: auto; background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
        h1 { color: var(--kice-blue); text-align: center; font-size: 28px; border-bottom: 3px solid var(--kice-blue); padding-bottom: 15px; }
        
        .setup-section { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 25px; background: #f8f9fa; padding: 20px; border-radius: 10px; }
        .input-group { display: flex; flex-direction: column; }
        label { font-weight: bold; margin-bottom: 8px; color: var(--kice-blue); }
        select, textarea { padding: 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 15px; }
        
        .full-width { grid-column: 1 / -1; }
        textarea { height: 180px; resize: vertical; }
        
        button#generate { width: 100%; padding: 18px; background-color: var(--kice-orange); color: white; border: none; border-radius: 8px; font-size: 20px; font-weight: bold; cursor: pointer; transition: 0.3s; }
        button#generate:hover { background-color: #d35400; }
        
        #result-container { margin-top: 35px; border-top: 2px dashed #ccc; padding-top: 25px; }
        #result { white-space: pre-wrap; background: #fff; padding: 25px; border: 1px solid #eee; border-radius: 8px; box-shadow: inset 0 2px 5px rgba(0,0,0,0.05); font-size: 16px; }
        .loading { text-align: center; color: var(--kice-blue); font-weight: bold; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📑 국가고시·수능 문항 자동 생성 시스템</h1>
        
        <div class="setup-section">
            <div class="input-group">
                <label>1. 시험 유형</label>
                <select id="testType">
                    <option value="CSAT">대학수학능력시험 (사고력/추론)</option>
                    <option value="CERT">국가기술자격시험 (지식/실무)</option>
                    <option value="OFFICIAL">공무원 임용시험 (변별력/지엽)</option>
                </select>
            </div>
            <div class="input-group">
                <label>2. 대상 과목</label>
                <input type="text" id="subject" placeholder="예: 국어(비문학), 전기기사, 한국사" style="padding:12px; border-radius:6px; border:1px solid #ccc;">
            </div>
            <div class="input-group">
                <label>3. 문항 난이도</label>
                <select id="difficulty">
                    <option value="Level 1">기초 (개념 이해)</option>
                    <option value="Level 3" selected>보통 (응용 및 적용)</option>
                    <option value="Level 5">심화 (킬러 문항/고난도)</option>
                </select>
            </div>
            <div class="input-group">
                <label>4. 출제 방식</label>
                <select id="genType">
                    <option value="Type A">Type A (기존 문항 변형)</option>
                    <option value="Type B">Type B (자료 기반 신규 출제)</option>
                </select>
            </div>
            <div class="input-group full-width">
                <label>5. 원본 자료 및 지문 입력</label>
                <textarea id="sourceText" placeholder="변형할 문항이나 출제 근거가 될 학술/정책 자료를 입력하십시오."></textarea>
            </div>
        </div>

        <button id="generate" onclick="requestQuestion()">문항 출제 서명 및 생성</button>
        
        <div id="result-container">
            <div class="loading" id="loader">출제 위원들이 보안 구역에서 문항을 제작 중입니다...</div>
            <div id="result"></div>
        </div>
    </div>

    <script>
        async function requestQuestion() {
            const resultDiv = document.getElementById('result');
            const loader = document.getElementById('loader');
            
            const payload = {
                testType: document.getElementById('testType').value,
                subject: document.getElementById('subject').value,
                difficulty: document.getElementById('difficulty').value,
                genType: document.getElementById('genType').value,
                text: document.getElementById('sourceText').value
            };

            if(!payload.subject || !payload.text) {
                alert('과목과 자료를 모두 입력해주세요.');
                return;
            }

            loader.style.display = 'block';
            resultDiv.innerText = '';

            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                resultDiv.innerText = data.result;
            } catch (e) {
                resultDiv.innerText = "오류 발생: " + e.message;
            } finally {
                loader.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""

class KICEServerHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(HTML_TEMPLATE.encode('utf-8'))

    def do_POST(self):
        if self.path == '/api/generate':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            
            result = self.call_ai(data)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'result': result}).encode('utf-8'))

    def call_ai(self, d):
        if not OPENAI_API_KEY: return "API 키가 설정되지 않았습니다."

        # 과목 및 유형별 페르소나 설정
        system_msg = f"""당신은 대한민국 '한국교육과정평가원' 및 '한국산업인력공단'의 합동 수석 출제위원입니다.
지시사항:
1. 대상 과목: {d['subject']}
2. 시험 유형: {d['testType']} (수능은 사고력 위주, 자격증은 실무와 정확한 지식 위주)
3. 난이도: {d['difficulty']} (Level 5는 변별력을 위한 킬러 문항)
4. 출제 방식: {d['genType']}

문항 구성:
- 발문: 격조 있고 명확한 학술적 언어 사용
- 보기: [보기] 박스 혹은 선택지(1~5번) 구성
- 해설: 정답의 근거를 지문 내에서 논리적으로 제시
- 오답: 매력적인 오답(오개념 유도)을 포함할 것
"""

        api_url = "https://api.openai.com/v1/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": d['text']}
            ],
            "temperature": 0.5 # 안정적인 출제를 위해 온도를 낮춤
        }

        try:
            req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req) as res:
                res_body = json.loads(res.read().decode('utf-8'))
                return res_body['choices'][0]['message']['content']
        except Exception as e:
            return f"문항 생성 중 오류: {str(e)}"

with socketserver.TCPServer(("", PORT), KICEServerHandler) as httpd:
    print(f"KICE 출제 엔진 가동: 포트 {PORT}")
    httpd.serve_forever()
