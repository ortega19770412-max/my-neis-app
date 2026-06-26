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
    <title>KICE English AI Question Generator</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/mammoth/1.4.21/mammoth.browser.min.js"></script>
    <style>
        :root { --kice-blue: #1a3a5f; --bg-gray: #f4f6f9; }
        body { font-family: 'Batang', 'Times New Roman', serif; background-color: var(--bg-gray); margin: 0; padding: 20px; }
        .container { max-width: 1100px; margin: auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.1); }
        h1 { font-family: 'Pretendard', sans-serif; color: var(--kice-blue); text-align: center; border-bottom: 3px double #000; padding-bottom: 10px; }
        .config-panel { background: #fdfdfd; padding: 20px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 20px; font-family: sans-serif; }
        .type-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 15px 0; }
        #result-box { display: none; margin-top: 20px; border: 1px solid #000; padding: 40px; background: #fff; column-count: 2; column-rule: 1px solid #000; gap: 40px; }
        .question-unit { margin-bottom: 35px; break-inside: avoid; }
        .q-passage { border: 1px solid #000; padding: 15px; margin-bottom: 15px; font-size: 1em; line-height: 1.8; text-align: justify; }
        .options { list-style: none; padding-left: 0; margin-top: 10px; }
        .options li { margin-bottom: 4px; }
        u { text-underline-offset: 5px; text-decoration: underline; }
        .ans-box { column-span: all; background: #f1f3f5; border: 1px dashed #333; margin-top: 30px; padding: 20px; font-family: sans-serif; }
    </style>
</head>
<body>
    <div class="container">
        <h1>2026학년도 대학수학능력시험 영어영역 AI 출제기</h1>
        <div class="config-panel">
            <strong>난이도:</strong>
            <select id="difficulty"><option value="1">Lv.1</option><option value="3" selected>Lv.3</option><option value="5">Lv.5</option></select>
            <div class="type-grid" id="typeSelectors">
                <div><input type="checkbox" value="어법" checked> 어법</div>
                <div><input type="checkbox" value="내용일치" checked> 내용일치</div>
                <div><input type="checkbox" value="주제"> 주제</div>
                <div><input type="checkbox" value="빈칸" checked> 빈칸</div>
            </div>
            <textarea id="sourceText" style="width:100%; height:100px;" placeholder="지문을 입력하세요."></textarea>
            <button id="generate" onclick="startGeneration()" style="width:100%; padding:15px; background:#1a3a5f; color:white; border:none; cursor:pointer; font-weight:bold; margin-top:10px;">문항 생성</button>
        </div>
        <div id="result-box"></div>
    </div>

    <script>
        async function startGeneration() {
            const text = document.getElementById('sourceText').value;
            const selectedTypes = Array.from(document.querySelectorAll('#typeSelectors input:checked')).map(el => el.value);
            const resultBox = document.getElementById('result-box');
            resultBox.style.display = 'none';

            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ types: selectedTypes, difficulty: document.getElementById('difficulty').value, text: text })
            });
            const data = await response.json();
            resultBox.innerHTML = data.result;
            resultBox.style.display = 'block';
        }
    </script>
</body>
</html>
"""

class KICEEnglishServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header('Content-type', 'text/html; charset=utf-8'); self.end_headers()
        self.wfile.write(HTML_TEMPLATE.encode('utf-8'))

    def do_POST(self):
        if self.path == '/api/generate':
            length = int(self.headers['Content-Length']); data = json.loads(self.rfile.read(length))
            result = self.call_english_api(data)
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({'result': result}).encode('utf-8'))

    def call_english_api(self, d):
        system_msg = f"""당신은 평가원 수석 영어 출제위원입니다. 
본문과 문항 번호의 **1:1 완벽한 일치**가 가장 중요합니다.

[어법 문항 출제 시 절대 규칙]:
1. 지문 본문(<div class="q-passage">)에 반드시 <u>①</u>, <u>②</u>, <u>③</u>, <u>④</u>, <u>⑤</u> 총 5개의 밑줄 기호를 삽입하십시오.
2. 하단 선택지 ①~⑤는 지문에 표시된 <u>①</u>~<u>⑤</u>의 단어들을 순서대로 정확히 가져와 구성하십시오.
3. 지문의 밑줄 개수가 3개나 4개에 그치지 않도록 **반드시 5개를 꽉 채워** 표시하십시오.

[빈칸 문항 출제 시 절대 규칙]:
1. 지문 내의 논리적 핵심 문장에 (   ) 빈칸을 만드십시오.
2. 선택지 ①~⑤는 해당 빈칸에 들어갈 적절한 말을 5지선다로 구성하십시오.

[공통 규칙]:
- 모든 문항은 5지선다 형식을 갖춥니다.
- 지문 내의 표시(밑줄/빈칸)와 문항의 물음이 서로 완벽하게 호응해야 합니다.
- HTML 형식으로 출력하며, 마지막에 정답과 근거를 해설에 포함하십시오.
"""
        api_url = "https://api.openai.com/v1/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "system", "content": system_msg}, {"role": "user", "content": f"지문: {d['text']}\\n유형: {d['types']}"}],
            "temperature": 0.3
        }
        req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers)
        with urllib.request.urlopen(req) as res:
            res_body = json.loads(res.read().decode('utf-8'))
            return res_body['choices'][0]['message']['content']

with socketserver.TCPServer(("", PORT), KICEEnglishServer) as httpd:
    httpd.serve_forever()
