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
    <title>KICE 과목특화 정밀 출제 시스템</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/mammoth/1.4.21/mammoth.browser.min.js"></script>
    <style>
        :root { --kice-blue: #1a3a5f; --kice-gold: #c2a15f; --bg-gray: #f4f6f9; }
        body { font-family: 'Pretendard', sans-serif; background-color: var(--bg-gray); margin: 0; padding: 20px; }
        .container { max-width: 1000px; margin: auto; background: white; padding: 40px; border-radius: 15px; box-shadow: 0 15px 35px rgba(0,0,0,0.1); }
        h1 { color: var(--kice-blue); text-align: center; border-bottom: 3px solid var(--kice-blue); padding-bottom: 10px; }
        
        .setup-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 25px; }
        .input-group { display: flex; flex-direction: column; }
        label { font-weight: bold; margin-bottom: 5px; font-size: 13px; color: #555; }
        select, input, textarea { padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; }
        
        .mode-section { grid-column: 1 / -1; display: flex; gap: 10px; margin: 10px 0; }
        .mode-btn { flex: 1; padding: 15px; border: 2px solid #ddd; background: #fff; cursor: pointer; border-radius: 8px; font-weight: bold; transition: 0.3s; }
        .mode-btn.active { border-color: var(--kice-blue); background: var(--kice-blue); color: white; }
        
        .file-drop { grid-column: 1 / -1; border: 2px dashed var(--kice-blue); padding: 20px; text-align: center; border-radius: 10px; background: #f9fbff; cursor: pointer; }
        textarea { height: 250px; grid-column: 1 / -1; font-family: 'Courier New', monospace; line-height: 1.6; }
        
        button#generate { width: 100%; padding: 20px; background: var(--kice-blue); color: white; border: none; border-radius: 8px; font-size: 18px; font-weight: bold; cursor: pointer; margin-top: 20px; box-shadow: 0 5px 15px rgba(26,58,95,0.3); }
        
        #result-box { margin-top: 40px; border: 1px solid #eee; padding: 30px; border-radius: 12px; background: #fff; display: none; }
        .loading { display: none; text-align: center; font-weight: bold; color: var(--kice-blue); padding: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎓 KICE 과목특화 정밀 문항 생성기</h1>
        
        <div class="setup-grid">
            <div class="input-group">
                <label>1. 과목 선택</label>
                <select id="subject">
                    <option value="영어">영어 (주제/어법/순서/빈칸)</option>
                    <option value="국어">국어 (비문학/독해/추론)</option>
                    <option value="수학">수학/통계 (원리/응용/계산)</option>
                    <option value="한국사/사회">한국사/사회 (인과/사료분석)</option>
                    <option value="직업자격증">자격증/실무 (법규/원리/암기)</option>
                </select>
            </div>
            <div class="input-group">
                <label>2. 평가 지향점</label>
                <select id="testType">
                    <option value="사고력/추론">사고력/추론 (CSAT 스타일)</option>
                    <option value="지식/실무">지식/실무 (자격증 스타일)</option>
                    <option value="변별력/지엽">변별력/지엽 (공무원 스타일)</option>
                </select>
            </div>
            <div class="input-group">
                <label>3. 난이도</label>
                <select id="difficulty">
                    <option value="기초">기초</option>
                    <option value="보통" selected>보통</option>
                    <option value="심화">심화 (킬러문항)</option>
                </select>
            </div>
        </div>

        <div class="mode-section">
            <button id="btnA" class="mode-btn active" onclick="setMode('Type A')">Type A: 문제지 변형<br><small>(기존 문제 논리 유지)</small></button>
            <button id="btnB" class="mode-btn" onclick="setMode('Type B')">Type B: 자료 기반 신규출제<br><small>(데이터 분석 후 창조)</small></button>
        </div>

        <div class="file-drop" onclick="document.getElementById('fileInput').click()">
            <strong>[파일 선택] PDF 또는 DOCX 업로드 (텍스트 자동 추출)</strong>
            <input type="file" id="fileInput" style="display:none" accept=".pdf,.docx">
        </div>

        <textarea id="sourceText" placeholder="여기에 지문이나 기존 문제를 입력하십시오. 오직 이 입력 내용 안에서만 문제가 생성됩니다."></textarea>
        
        <button id="generate" onclick="startGeneration()">3문항 이상 세트 생성 시작</button>
        
        <div class="loading" id="loader">⚙️ 과목별 출제 가이드라인에 따라 정밀 검토 중입니다...</div>
        <div id="result-box"></div>
    </div>

    <script>
        let currentMode = 'Type A';
        function setMode(mode) {
            currentMode = mode;
            document.getElementById('btnA').classList.toggle('active', mode === 'Type A');
            document.getElementById('btnB').classList.toggle('active', mode === 'Type B');
        }

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
            if(!text.trim()) return alert('자료를 입력하세요.');
            
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
                alert('통신 오류');
            } finally { loader.style.display = 'none'; }
        }
    </script>
</body>
</html>
"""

class SpecializedKICEServer(http.server.BaseHTTPRequestHandler):
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
        if not OPENAI_API_KEY: return "API Key Missing"

        # 과목별 출제 로직 정의
        subject_guide = {
            "영어": "주제 파악, 문맥상 어휘, 어법 판단, 빈칸 추론, 글의 순서 중 3가지 선택",
            "국어": "핵심 논지 파악, 구체적 사례 적용, 추론적 이해, 어휘의 의미",
            "수학": "원리 이해, 데이터 해석, 응용 계산, 고난도 추론",
            "한국사/사회": "시대 상황 파악, 사료 분석, 인과 관계 추론, 개념 비교",
            "직업자격증": "법규 적용, 핵심 원리 암기 확인, 실무 사례 판단"
        }

        system_msg = f"""당신은 한국교육과정평가원 수석 출제위원입니다.
[필수 원칙]:
1. [자료 강제성]: 오직 입력된 데이터(텍스트) 내의 정보만 사용하여 출제하십시오. 외부 사실을 절대 추가하지 마십시오.
2. [과목 특성화]: {d['subject']} 과목의 특징에 따라 {subject_guide.get(d['subject'], '')} 형태의 문제를 출제하십시오.
3. [최소 수량]: 반드시 서로 다른 유형의 문항을 3개 이상 한 세트로 생성하십시오.
4. [출제 모드]: {d['mode']} (Type A는 구조 유지 변형, Type B는 데이터 분석 후 신규 생성)
5. [평가 유형 및 난이도]: {d['testType']}, 난이도 {d['difficulty']}에 맞출 것.

[출력 형식]:
- 각 문제별 [발문], [보기(필요시)], [5지선다 선택지], [정답], [정밀 해설(데이터 근거 명시)]를 포함하십시오.
"""

        api_url = "https://api.openai.com/v1/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"이 데이터를 분석하여 3문항 세트를 만드십시오:\\n{d['text']}"}
            ],
            "temperature": 0.4
        }

        try:
            req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req) as res:
                res_body = json.loads(res.read().decode('utf-8'))
                return res_body['choices'][0]['message']['content']
        except Exception as e:
            return f"에러: {str(e)}"

with socketserver.TCPServer(("", PORT), SpecializedKICEServer) as httpd:
    print(f"KICE 과목특화 엔진 가동 중: 포트 {PORT}")
    httpd.serve_forever()
