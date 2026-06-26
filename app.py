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
        h1 { font-family: 'Pretendard', sans-serif; color: var(--kice-blue); text-align: center; border-bottom: 3px double #000; padding-bottom: 10px; margin-top: 0; }
        
        /* 설정 패널 */
        .config-panel { background: #fdfdfd; padding: 20px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 20px; font-family: sans-serif; }
        .type-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 15px 0; }
        .type-item { font-size: 13px; display: flex; align-items: center; gap: 5px; }
        
        /* 시험지 스타일 */
        #result-box { 
            display: none; 
            margin-top: 20px; 
            border: 1px solid #000; 
            padding: 40px; 
            background: #fff; 
            column-count: 2; 
            column-rule: 1px solid #000;
            gap: 40px;
        }
        
        .question-unit { margin-bottom: 35px; break-inside: avoid; }
        .q-header { font-weight: bold; margin-bottom: 8px; font-size: 1.05em; line-height: 1.4; }
        .q-passage { border: 1px solid #000; padding: 15px; margin-bottom: 15px; font-size: 1em; line-height: 1.7; text-align: justify; }
        .options { list-style: none; padding-left: 0; margin-top: 10px; }
        .options li { margin-bottom: 4px; font-size: 0.95em; }
        
        u { text-underline-offset: 4px; text-decoration: underline; }
        .blank { font-weight: bold; border-bottom: 1px solid #000; padding: 0 15px; }
        
        .ans-box { column-span: all; background: #f1f3f5; border: 1px dashed #333; margin-top: 30px; padding: 20px; font-family: sans-serif; font-size: 0.9em; }
        .loading { display: none; text-align: center; padding: 20px; font-weight: bold; color: var(--kice-blue); }
        button#generate { width: 100%; padding: 15px; background: var(--kice-blue); color: white; border: none; font-size: 17px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <h1>2026학년도 대학수학능력시험 영어영역 AI 출제 시스템</h1>
        
        <div class="config-panel">
            <div style="display: flex; gap: 20px; align-items: center;">
                <strong>난이도 설정:</strong>
                <select id="difficulty" style="padding: 5px 15px;">
                    <option value="1">Lv.1 (기초)</option>
                    <option value="2">Lv.2 (평이)</option>
                    <option value="3" selected>Lv.3 (수능 표준)</option>
                    <option value="4">Lv.4 (변별력 확보)</option>
                    <option value="5">Lv.5 (킬러 문항)</option>
                </select>
                <input type="file" id="fileInput" accept=".pdf,.docx">
            </div>

            <div class="type-grid" id="typeSelectors">
                <div class="type-item"><input type="checkbox" value="어법상 틀린 것" checked> 어법 판단</div>
                <div class="type-item"><input type="checkbox" value="내용 일치/불일치" checked> 내용 일치</div>
                <div class="type-item"><input type="checkbox" value="주제/제목 찾기" checked> 주제/제목</div>
                <div class="type-item"><input type="checkbox" value="글의 분위기/심경"> 분위기/심경</div>
                <div class="type-item"><input type="checkbox" value="빈칸 추론" checked> 빈칸 추론</div>
                <div class="type-item"><input type="checkbox" value="글의 순서"> 글의 순서</div>
                <div class="type-item"><input type="checkbox" value="문장 삽입"> 문장 삽입</div>
                <div class="type-item"><input type="checkbox" value="어휘의 적절성"> 어휘 판단</div>
            </div>

            <textarea id="sourceText" style="width:100%; height:120px; margin-top:10px;" placeholder="영어 지문을 입력하거나 파일을 업로드하세요. 입력된 지문을 분석하여 위에서 선택한 유형의 문제들을 생성합니다."></textarea>
            <button id="generate" onclick="startGeneration()" style="margin-top:10px;">수능형 정밀 문항 생성</button>
        </div>

        <div class="loading" id="loader">영어 교육과정 및 수능 출제 매뉴얼 분석 중...</div>
        <div id="result-box"></div>
    </div>

    <script>
        async function startGeneration() {
            const text = document.getElementById('sourceText').value;
            if(!text.trim()) return alert('지문을 입력하십시오.');
            
            // 선택된 유형 수집
            const selectedTypes = Array.from(document.querySelectorAll('#typeSelectors input:checked')).map(el => el.value);
            if(selectedTypes.length === 0) return alert('최소 하나 이상의 문제 유형을 선택하세요.');

            const loader = document.getElementById('loader');
            const resultBox = document.getElementById('result-box');
            loader.style.display = 'block';
            resultBox.style.display = 'none';

            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        subject: "영어",
                        types: selectedTypes,
                        difficulty: document.getElementById('difficulty').value,
                        text: text
                    })
                });
                const data = await response.json();
                resultBox.innerHTML = data.result;
                resultBox.style.display = 'block';
            } catch (e) {
                alert('연결 에러');
            } finally { loader.style.display = 'none'; }
        }

        // 파일 처리 로직 (생략 없이 유지)
        document.getElementById('fileInput').addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            if (file.name.endsWith('.pdf')) {
                reader.onload = async function() {
                    const typedarray = new Uint8Array(this.result);
                    const pdf = await pdfjsLib.getDocument(typedarray).promise;
                    let fullText = "";
                    for(let i=1; i<=pdf.numPages; i++){
                        const page = await pdf.getPage(i);
                        const textContent = await page.getTextContent();
                        fullText += textContent.items.map(item => item.str).join(" ") + "\\n";
                    }
                    document.getElementById('sourceText').value = fullText;
                };
                reader.readAsArrayBuffer(file);
            } else if (file.name.endsWith('.docx')) {
                reader.onload = async function(e) {
                    const result = await mammoth.extractRawText({arrayBuffer: e.target.result});
                    document.getElementById('sourceText').value = result.value;
                };
                reader.readAsArrayBuffer(file);
            }
        });
    </script>
</body>
</html>
"""

class KICEEnglishServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(HTML_TEMPLATE.encode('utf-8'))

    def do_POST(self):
        if self.path == '/api/generate':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            result = self.call_english_api(data)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'result': result}).encode('utf-8'))

    def call_english_api(self, d):
        if not OPENAI_API_KEY: return "API Key Error"

        system_msg = f"""당신은 한국교육과정평가원(KICE) 수석 영어 출제위원입니다.
입력된 지문을 바탕으로 수능 영어영역의 엄격한 형식에 맞춰 문항을 생성하십시오.

[출제 필수 지침]:
1. [지문 동기화]: 
   - '어법' 문제를 출제한다면 지문(<div class="q-passage">) 내의 해당 부분에 <u>①</u> ~ <u>⑤</u> 밑줄과 기호를 반드시 표시하십시오.
   - '빈칸' 문제를 출제한다면 지문 내에 (   ) 또는 [   ] 빈칸을 만드십시오.
2. [5지선다]: 모든 문제는 예외 없이 ① ~ ⑤의 오지선다 형식을 갖추어야 합니다.
3. [수능 발문]: 수능 공식 발문만 사용하십시오.
   - "다음 글의 밑줄 친 부분 중, 어법상 틀린 것은?"
   - "다음 글의 빈칸에 들어갈 말로 가장 적절한 것을 고르시오."
   - "다음 글에 드러난 필자의 심경으로 가장 적절한 것은?" 등
4. [난이도]: 난이도 Lv {d['difficulty']}에 맞춰 매력적인 오답을 구성하십시오.
5. [유형 위젯]: 사용자가 선택한 유형({', '.join(d['types'])})을 한 세트로 묶어 출력하십시오.

[출력 레이아웃]: HTML 태그(<div class="question-unit"> 등)를 사용하여 2단 시험지 형태로 배치하십시오.
마지막에 정답과 지문 근거가 포함된 해설(<div class="ans-box">)을 제공하십시오.
"""

        api_url = "https://api.openai.com/v1/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"지문: {d['text']}\\n출제유형: {d['types']}"}
            ],
            "temperature": 0.35
        }

        try:
            req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req) as res:
                res_body = json.loads(res.read().decode('utf-8'))
                return res_body['choices'][0]['message']['content']
        except Exception as e:
            return f"에러: {str(e)}"

with socketserver.TCPServer(("", PORT), KICEEnglishServer) as httpd:
    httpd.serve_forever()
