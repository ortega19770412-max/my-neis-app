import os
import http.server
import socketserver
import urllib.request
import json

PORT = int(os.environ.get("PORT", 8000))
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KICE AI-Standard Question Generator</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/mammoth/1.4.21/mammoth.browser.min.js"></script>
    <style>
        :root { --kice-blue: #1a3a5f; --bg-gray: #f4f6f9; }
        body { font-family: 'Batang', 'Times New Roman', serif; background-color: var(--bg-gray); margin: 0; padding: 20px; }
        .container { max-width: 1100px; margin: auto; background: white; padding: 30px; border-radius: 0; box-shadow: 0 0 20px rgba(0,0,0,0.2); }
        h1 { font-family: 'Pretendard', sans-serif; color: var(--kice-blue); text-align: center; border-bottom: 2px solid #000; padding-bottom: 5px; }
        
        /* 설정 영역 */
        .config-panel { background: #eee; padding: 15px; margin-bottom: 20px; border-radius: 8px; font-family: sans-serif; }
        .setup-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
        select, textarea { width: 100%; padding: 10px; border: 1px solid #ccc; box-sizing: border-box; }
        
        /* 결과물 시험지 스타일 (핵심) */
        #result-box { 
            display: none; 
            margin-top: 20px; 
            border: 2px solid #000; 
            padding: 40px; 
            background: #fff; 
            column-count: 2; /* 2단 구성 */
            column-rule: 1px solid #000;
            gap: 40px;
        }
        
        /* 문항 스타일 */
        .question-unit { margin-bottom: 30px; break-inside: avoid; }
        .q-header { font-weight: bold; margin-bottom: 10px; }
        .q-passage { border: 1px solid #000; padding: 15px; margin-bottom: 15px; font-size: 0.95em; line-height: 1.6; }
        .options { list-style: none; padding-left: 0; }
        .options li { margin-bottom: 5px; }
        .options li:before { content: "① "; margin-right: 5px; } /* 자동 번호는 AI가 생성하도록 함 */
        
        .ans-box { 
            column-span: all; 
            background: #f9f9f9; 
            border-top: 1px dashed #000; 
            margin-top: 20px; 
            padding: 20px; 
            font-family: sans-serif;
        }

        .loading { display: none; text-align: center; padding: 20px; font-weight: bold; color: var(--kice-blue); }
        button#generate { width: 100%; padding: 15px; background: var(--kice-blue); color: white; border: none; font-weight: bold; cursor: pointer; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>2026학년도 대학수학능력시험 모의평가 문항생성기</h1>
        
        <div class="config-panel">
            <div class="setup-grid">
                <select id="subject">
                    <option value="국어">국어</option>
                    <option value="영어">영어</option>
                    <option value="수학">수학</option>
                    <option value="전문교과">전문교과</option>
                </select>
                <select id="difficulty">
                    <option value="L1">Level 1</option>
                    <option value="L3" selected>Level 3</option>
                    <option value="L5">Level 5</option>
                </select>
                <input type="file" id="fileInput" accept=".pdf,.docx">
            </div>
            <textarea id="sourceText" style="margin-top:10px; height:100px;" placeholder="지문 내용을 입력하십시오."></textarea>
            <button id="generate" onclick="startGeneration()">문항 생성 및 시험지 배치</button>
        </div>

        <div class="loading" id="loader">시험지 인쇄 중...</div>
        <div id="result-box"></div>
    </div>

    <script>
        // 기존 JS 로직 유지 (파일 업로드 및 API 호출)
        async function startGeneration() {
            const text = document.getElementById('sourceText').value;
            if(!text.trim()) return alert('내용을 입력하세요.');
            const loader = document.getElementById('loader');
            const resultBox = document.getElementById('result-box');
            
            loader.style.display = 'block';
            resultBox.style.display = 'none';

            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        subject: document.getElementById('subject').value,
                        text: text,
                        difficulty: document.getElementById('difficulty').value
                    })
                });
                const data = await response.json();
                resultBox.innerHTML = data.result; // HTML 형태로 직접 주입
                resultBox.style.display = 'block';
            } catch (e) {
                alert('오류 발생');
            } finally { loader.style.display = 'none'; }
        }
    </script>
</body>
</html>
"""

class KICEProfessionalServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(HTML_TEMPLATE.encode('utf-8'))

    def do_POST(self):
        if self.path == '/api/generate':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            result = self.call_kice_api(data)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'result': result}).encode('utf-8'))

    def call_kice_api(self, d):
        if not OPENAI_API_KEY: return "API Key Error"

        system_msg = f"""당신은 평가원 수석 출제위원입니다. 
출력 결과는 반드시 'HTML 태그'만을 사용해야 하며, 첨부된 시험지 이미지와 동일한 레이아웃을 가져야 합니다.

[작성 규칙]:
1. [2단 구성 연출]: 사용자가 제공한 텍스트를 분석하여 3문항 이상을 출제하되, 결과는 <div class="question-unit">으로 감싸서 출력하십시오.
2. [세트 문항]: 이미지와 같이 "[10~12] 다음 글을 읽고 물음에 답하시오." 형태의 안내문을 반드시 포함하십시오.
3. [발문 스타일]: 
   - 국어: "윗글의 내용과 일치하지 않는 것은?"
   - 영어: "윗글의 빈칸 [A]에 들어갈 말로 가장 적절한 것은?"
   - 전문교과: "다음 자료를 통해 알 수 있는 ~으로 가장 적절한 것은?"
4. [보기 지문]: 지문은 <div class="q-passage"> 태그로 감싸 박스 형태로 만드십시오.
5. [객관식]: 각 문항 아래 1~5번 선택지를 배치하십시오.

[출력 HTML 구조 예시]:
<div class="q-header text-center">[1-3] 다음 지문을 읽고 물음에 답하시오.</div>
<div class="q-passage"> (여기에 분석한 지문 내용 삽입) </div>
<div class="question-unit">
  <div class="q-header">1. (수능형 발문) [3점]</div>
  <ul class="options"><li>선택지1</li><li>선택지2</li>...</ul>
</div>
(반복...)
<div class="ans-box"><strong>[정답 및 해설]</strong><br>...</div>
"""

        api_url = "https://api.openai.com/v1/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"과목: {d['subject']}, 데이터: {d['text']}"}
            ],
            "temperature": 0.3
        }

        try:
            req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req) as res:
                res_body = json.loads(res.read().decode('utf-8'))
                return res_body['choices'][0]['message']['content']
        except Exception as e:
            return f"오류: {str(e)}"

with socketserver.TCPServer(("", PORT), KICEProfessionalServer) as httpd:
    httpd.serve_forever()
