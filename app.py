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
        .container { max-width: 1100px; margin: auto; background: white; padding: 30px; box-shadow: 0 0 20px rgba(0,0,0,0.2); }
        h1 { font-family: 'Pretendard', sans-serif; color: var(--kice-blue); text-align: center; border-bottom: 2px solid #000; padding-bottom: 5px; }
        
        .config-panel { background: #eee; padding: 15px; margin-bottom: 20px; border-radius: 8px; font-family: sans-serif; }
        .setup-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
        select, textarea { width: 100%; padding: 10px; border: 1px solid #ccc; box-sizing: border-box; }
        
        #result-box { 
            display: none; 
            margin-top: 20px; 
            border: 2px solid #000; 
            padding: 40px; 
            background: #fff; 
            column-count: 2; 
            column-rule: 1px solid #000;
            gap: 40px;
        }
        
        .question-unit { margin-bottom: 30px; break-inside: avoid; }
        .q-header { font-weight: bold; margin-bottom: 10px; }
        .q-passage { border: 1px solid #000; padding: 15px; margin-bottom: 15px; font-size: 0.95em; line-height: 1.6; }
        .options { list-style: none; padding-left: 0; margin-top: 10px; }
        .options li { margin-bottom: 5px; }
        
        .ans-box { 
            column-span: all; 
            background: #f9f9f9; 
            border-top: 1px dashed #000; 
            margin-top: 20px; 
            padding: 20px; 
            font-family: sans-serif;
            font-size: 0.9em;
        }

        .loading { display: none; text-align: center; padding: 20px; font-weight: bold; color: var(--kice-blue); }
        button#generate { width: 100%; padding: 15px; background: var(--kice-blue); color: white; border: none; font-weight: bold; cursor: pointer; margin-top: 10px; }
        
        /* 밑줄 및 강조 스타일 */
        u { text-underline-offset: 3px; }
        .blank { display: inline-block; border-bottom: 1px solid #000; min-width: 50px; text-align: center; padding: 0 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>2026학년도 대학수학능력시험 모의평가</h1>
        
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

        <div class="loading" id="loader">시험지 검토 및 인쇄 중...</div>
        <div id="result-box"></div>
    </div>

    <script>
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
                resultBox.innerHTML = data.result;
                resultBox.style.display = 'block';
            } catch (e) {
                alert('연결 오류');
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

        system_msg = f"""당신은 평가원 수석 출제위원입니다. 반드시 다음의 '초정밀 출제 규칙'을 지켜 HTML로 출력하십시오.

[1. 지문 구성 (Passage Synchronization)]:
- 생성된 지문(<div class="q-passage">) 내부에는 문항에서 물어볼 장치들을 반드시 포함해야 합니다.
- 빈칸 추론 문항이 있다면 지문에 ( 가 ) 또는 [  ]와 같이 표시하십시오.
- 어휘/어법 문항이 있다면 지문의 해당 단어에 <u>ⓐ</u>, <u>ⓑ</u> 등으로 밑줄과 기호를 표시하십시오.

[2. 5지선다 강제 (Fixed 5-Options)]:
- 모든 문항은 반드시 5개(①, ②, ③, ④, ⑤)의 선택지를 명확히 제시하십시오.
- 4지선다나 단답형은 절대 허용하지 않습니다.

[3. 문항 세트 구성]:
- [1~3] 또는 [10~12] 처럼 문항 번호 범위를 상단에 적고 "다음 글을 읽고 물음에 답하시오."라는 발문을 작성하십시오.

[4. 과목별 발문 표준화]:
- {d['subject']} 과목의 수능 기출 발문을 그대로 사용하십시오. (예: "윗글의 내용과 일치하지 않는 것은?", "밑줄 친 ⓐ~ⓔ 중 문맥상 쓰임이 적절하지 않은 것은?")

[5. 출력 형식]:
- 결과값은 반드시 HTML 태그로만 구성하며, <div class="question-unit"> 구조를 정확히 지키십시오.
- 마지막에 <div class="ans-box">를 만들어 정답과 데이터에 기반한 상세 해설을 포함하십시오.
"""

        api_url = "https://api.openai.com/v1/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"과목: {d['subject']}, 데이터: {d['text']}, 난이도: {d['difficulty']}"}
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
