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
    <title>KICE 국가수준 평가문항 생성 시스템</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/mammoth/1.4.21/mammoth.browser.min.js"></script>
    <style>
        :root { --kice-blue: #1a3a5f; --kice-gold: #c2a15f; --bg-gray: #f4f6f9; }
        body { font-family: 'Pretendard', 'Malgun Gothic', sans-serif; background-color: var(--bg-gray); margin: 0; padding: 20px; }
        .container { max-width: 1000px; margin: auto; background: white; padding: 40px; border-radius: 15px; box-shadow: 0 15px 35px rgba(0,0,0,0.1); }
        h1 { color: var(--kice-blue); text-align: center; border-bottom: 3px solid var(--kice-blue); padding-bottom: 10px; font-size: 24px; }
        
        .setup-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 25px; }
        .input-group { display: flex; flex-direction: column; }
        label { font-weight: bold; margin-bottom: 5px; font-size: 13px; color: #555; }
        select, input, textarea { padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; }
        
        .mode-section { grid-column: 1 / -1; display: flex; gap: 10px; margin: 10px 0; }
        .mode-btn { flex: 1; padding: 15px; border: 2px solid #ddd; background: #fff; cursor: pointer; border-radius: 8px; font-weight: bold; transition: 0.3s; text-align: center; }
        .mode-btn.active { border-color: var(--kice-blue); background: var(--kice-blue); color: white; }
        
        .file-drop { grid-column: 1 / -1; border: 2px dashed var(--kice-blue); padding: 20px; text-align: center; border-radius: 10px; background: #f9fbff; cursor: pointer; margin-bottom: 10px; }
        textarea { height: 250px; grid-column: 1 / -1; font-family: 'Courier New', monospace; line-height: 1.6; }
        
        button#generate { width: 100%; padding: 20px; background: var(--kice-blue); color: white; border: none; border-radius: 8px; font-size: 18px; font-weight: bold; cursor: pointer; margin-top: 20px; }
        
        #result-box { margin-top: 40px; border: 1px solid #eee; padding: 30px; border-radius: 12px; background: #fff; display: none; line-height: 1.8; }
        .loading { display: none; text-align: center; font-weight: bold; color: var(--kice-blue); padding: 20px; }
        .q-title { font-weight: bold; font-size: 1.1em; color: #000; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎓 KICE AI-Standard Question Generator</h1>
        
        <div class="setup-grid">
            <div class="input-group">
                <label>1. 과목 범주</label>
                <select id="subject">
                    <option value="국어">국어 (화작/독서/문학)</option>
                    <option value="영어">영어 (독해/어법/논리)</option>
                    <option value="수학">수학 (공통/선택)</option>
                    <option value="전문교과">전문교과 (상업/공업/가사/수산)</option>
                    <option value="한국사/사회">한국사/사회탐구</option>
                </select>
            </div>
            <div class="input-group">
                <label>2. 문항 성격</label>
                <select id="testType">
                    <option value="추론/종합">대학수학능력시험형 (추론)</option>
                    <option value="기초/이해">전국연합학력평가형 (기해)</option>
                    <option value="실무/적용">직업기초능력평가형</option>
                </select>
            </div>
            <div class="input-group">
                <label>3. 난이도</label>
                <select id="difficulty">
                    <option value="L1">Level 1 (기초)</option>
                    <option value="L3" selected>Level 3 (평이)</option>
                    <option value="L5">Level 5 (변별력 확보)</option>
                </select>
            </div>
        </div>

        <div class="mode-section">
            <button id="btnA" class="mode-btn active" onclick="setMode('Type A')">Type A: 문항 변형<br><small>기존 문제의 틀 유지</small></button>
            <button id="btnB" class="mode-btn" onclick="setMode('Type B')">Type B: 지문 기반 신규 출제<br><small>자료 분석 후 수능형 생성</small></button>
        </div>

        <div class="file-drop" onclick="document.getElementById('fileInput').click()">
            <strong>[지문/문제 업로드] PDF, DOCX 분석 지원</strong>
            <input type="file" id="fileInput" style="display:none" accept=".pdf,.docx">
        </div>

        <textarea id="sourceText" placeholder="지문 내용을 입력하거나 문항 변형을 위한 기존 문제를 입력하십시오."></textarea>
        
        <button id="generate" onclick="startGeneration()">수능/평가원 양식 문항 생성</button>
        
        <div class="loading" id="loader">🔎 수능 출제 매뉴얼에 따라 문항을 검토 중입니다...</div>
        <div id="result-box"></div>
    </div>

    <script>
        let currentMode = 'Type A';
        function setMode(mode) {
            currentMode = mode;
            document.getElementById('btnA').classList.toggle('active', mode === 'Type A');
            document.getElementById('btnB').classList.toggle('active', mode === 'Type B');
        }

        // 파일 처리 로직 (PDF.js, Mammoth.js 활용)
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

        async function startGeneration() {
            const text = document.getElementById('sourceText').value;
            if(!text.trim()) return alert('자료를 입력하십시오.');
            
            const loader = document.getElementById('loader');
            const resultBox = document.getElementById('result-box');
            loader.style.display = 'block';
            resultBox.style.display = 'none';

            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        mode: currentMode,
                        subject: document.getElementById('subject').value,
                        testType: document.getElementById('testType').value,
                        difficulty: document.getElementById('difficulty').value,
                        text: text
                    })
                });
                const data = await response.json();
                resultBox.innerHTML = '<div style="white-space:pre-wrap">' + data.result + '</div>';
                resultBox.style.display = 'block';
            } catch (e) {
                alert('연결 오류가 발생했습니다.');
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
        if not OPENAI_API_KEY: return "Error: API Key is missing."

        # 과목별 수능형 발문 가이드
        stem_guides = {
            "국어": "윗글의 내용과 일치하지 않는 것은? / 윗글을 통해 알 수 있는 내용으로 적절하지 않은 것은? / <보기>에 대한 설명으로 가장 적절한 것은?",
            "영어": "다음 글의 주제로 가장 적적한 것은? / 밑줄 친 부분이 의미하는 바로 가장 적절한 것은? / 글의 흐름으로 보아 주어진 문장이 들어가기에 가장 적절한 곳은?",
            "전문교과": "다음 대화를 바탕으로 (가)에 들어갈 내용으로 옳은 것은? / 그림의 출납전표를 분석한 결과로 가장 적절한 것은? / 다음 설명에 해당하는 개념으로 옳은 것은?",
            "기타": "다음 자료에 대한 설명으로 옳은 것만을 <보기>에서 있는 대로 고른 것은?"
        }

        system_msg = f"""당신은 한국교육과정평가원(KICE) 수석 출제위원입니다.
[주요 임무]: 주어진 텍스트를 분석하여 대학수학능력시험 및 정기고사 표준 양식에 맞는 고품질 문항을 생성하십시오.

[출제 가이드라인]:
1. [발문 형식]: 반드시 한국 교육과정 평가원 표준 발문을 사용하십시오. ({stem_guides.get(d['subject'], stem_guides['기타'])})
2. [문항 구성]: 최소 3문항 이상을 한 세트로 출제하십시오.
3. [전문교과 특화]: 과목이 '전문교과'인 경우 실무 사례, 도표 분석, 법령 적용 문제를 위주로 출제하십시오. 
4. [엄격한 근거]: 정답과 오답의 근거는 반드시 제출된 텍스트 내에 존재해야 합니다.
5. [난이도]: {d['difficulty']} 수준에 맞춰 선택지의 매력도를 조정하십시오.

[출력 양식]:
- [문제 1] (수능형 발문)
- 객관식 1번~5번 (수능식 번호 표기)
- [정답]
- [출제 근거 및 해설]: (텍스트의 어느 부분에서 근거했는지 명시)
"""

        api_url = "https://api.openai.com/v1/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"다음 자료를 바탕으로 {d['subject']} 문항 세트를 생성하십시오:\\n{d['text']}"}
            ],
            "temperature": 0.35
        }

        try:
            req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req) as res:
                res_body = json.loads(res.read().decode('utf-8'))
                return res_body['choices'][0]['message']['content']
        except Exception as e:
            return f"오류 발생: {str(e)}"

with socketserver.TCPServer(("", PORT), KICEProfessionalServer) as httpd:
    print(f"Server running on port {PORT}")
    httpd.serve_forever()
