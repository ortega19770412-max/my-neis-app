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
    <title>KICE 정밀 문항 생성 시스템 V2</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/mammoth/1.4.21/mammoth.browser.min.js"></script>
    <style>
        :root { --kice-blue: #1a3a5f; --kice-orange: #e67e22; --border-color: #d1d8e0; }
        body { font-family: 'Pretendard', 'Malgun Gothic', sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b; }
        .container { max-width: 950px; margin: auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); }
        h1 { color: var(--kice-blue); text-align: center; border-bottom: 2px solid var(--kice-blue); padding-bottom: 15px; margin-bottom: 30px; }
        
        .setup-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 30px; }
        .input-group { display: flex; flex-direction: column; }
        label { font-weight: 700; margin-bottom: 8px; font-size: 14px; color: var(--kice-blue); }
        select, input, textarea { padding: 12px; border: 1px solid var(--border-color); border-radius: 8px; font-size: 15px; background: #fff; }
        
        .file-upload-area { grid-column: 1 / -1; border: 2px dashed var(--kice-blue); padding: 20px; text-align: center; border-radius: 10px; background: #f1f5f9; cursor: pointer; transition: 0.2s; }
        .file-upload-area:hover { background: #e2e8f0; }
        
        textarea { height: 200px; resize: vertical; grid-column: 1 / -1; }
        
        button#generate { width: 100%; padding: 18px; background: var(--kice-blue); color: white; border: none; border-radius: 8px; font-size: 18px; font-weight: bold; cursor: pointer; margin-top: 20px; }
        button#generate:hover { background: #122a45; }
        
        #result-box { margin-top: 40px; border: 1px solid var(--border-color); padding: 30px; border-radius: 10px; background: #fff; display: none; line-height: 1.8; }
        .loading { display: none; text-align: center; padding: 20px; font-weight: bold; color: var(--kice-orange); }
        .info-text { font-size: 12px; color: #64748b; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 KICE 정밀 문항 생성 시스템</h1>
        
        <div class="setup-grid">
            <div class="input-group">
                <label>1. 평가 지향점 (시험 유형)</label>
                <select id="testType">
                    <option value="사고력/추론 (CSAT 스타일)">사고력/추론 (논리적 연결/종합)</option>
                    <option value="지식/실무 (자격증 스타일)">지식/실무 (명확한 사실/규정)</option>
                    <option value="변별력/지엽 (공무원 스타일)">변별력/지엽 (정밀성/세부사항)</option>
                </select>
            </div>
            <div class="input-group">
                <label>2. 문항 난이도</label>
                <select id="difficulty">
                    <option value="기초 (핵심 개념 직시)">기초</option>
                    <option value="보통 (개념의 응용)">보통</option>
                    <option value="심화 (추론적 고도화)">심화</option>
                </select>
            </div>
            
            <div class="file-upload-area" onclick="document.getElementById('fileInput').click()">
                <strong>📄 파일 업로드 (PDF, DOCX) 또는 클릭하여 선택</strong>
                <p class="info-text">파일을 선택하면 텍스트가 자동으로 아래 박스에 추출됩니다.</p>
                <input type="file" id="fileInput" style="display:none" accept=".pdf,.docx">
            </div>

            <div class="input-group full-width" style="grid-column: 1 / -1;">
                <label>3. 출제 근거 데이터 (업로드 시 자동 입력)</label>
                <textarea id="sourceText" placeholder="여기에 직접 텍스트를 입력하거나 파일을 업로드하세요. 입력된 내용 안에서만 출제됩니다."></textarea>
                <p class="info-text">※ 시스템은 이 텍스트의 범위를 벗어난 내용을 임의로 생성하지 않습니다.</p>
            </div>
        </div>

        <button id="generate" onclick="startGeneration()">정렬된 데이터 기반 문항 출제</button>
        
        <div class="loading" id="loader">💡 출제 위원이 근거 자료를 분석하여 문항을 설계 중입니다...</div>
        <div id="result-box"></div>
    </div>

    <script>
        // 파일 처리 로직
        document.getElementById('fileInput').addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            if (file.name.endsWith('.pdf')) {
                reader.onload = async function() {
                    const typedarray = new Uint8Array(this.result);
                    const pdf = await pdfjsLib.getDocument(typedarray).promise;
                    let fullText = "";
                    for(let i=1; i<=pdf.numPages; i++) {
                        const page = await pdf.getPage(i);
                        const textContent = await page.getTextContent();
                        fullText += textContent.items.map(item => item.str).join(" ") + "\\n";
                    }
                    document.getElementById('sourceText').value = fullText;
                };
                reader.readAsArrayBuffer(file);
            } else if (file.name.endsWith('.docx')) {
                reader.onload = async function(e) {
                    const arrayBuffer = e.target.result;
                    const result = await mammoth.extractRawText({arrayBuffer: arrayBuffer});
                    document.getElementById('sourceText').value = result.value;
                };
                reader.readAsArrayBuffer(file);
            }
        });

        async function startGeneration() {
            const text = document.getElementById('sourceText').value;
            if(!text.trim()) { alert('근거 자료를 입력하거나 파일을 업로드하세요.'); return; }

            const loader = document.getElementById('loader');
            const resultBox = document.getElementById('result-box');
            
            loader.style.display = 'block';
            resultBox.style.display = 'none';

            const payload = {
                testType: document.getElementById('testType').value,
                difficulty: document.getElementById('difficulty').value,
                text: text
            };

            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                resultBox.innerHTML = '<pre style="white-space: pre-wrap; font-family: inherit;">' + data.result + '</pre>';
                resultBox.style.display = 'block';
            } catch (e) {
                alert('연결 오류가 발생했습니다.');
            } finally {
                loader.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""

class PreciseKICEServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(HTML_TEMPLATE.encode('utf-8'))

    def do_POST(self):
        if self.path == '/api/generate':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            result = self.call_kice_ai(data)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'result': result}).encode('utf-8'))

    def call_kice_ai(self, d):
        if not OPENAI_API_KEY: return "Error: API Key 미설정"

        # 엄격한 근거주의 프롬프트
        system_msg = f"""당신은 대한민국 최고 권위의 출제위원입니다. 
다음 원칙에 따라 문항을 출제하십시오:

1. [엄격한 근거주의]: 오직 제공된 '출제 근거 데이터' 내의 정보만을 사용하십시오. 외부 지식을 결합하거나 추측하여 문제를 만들지 마십시오.
2. [평가 유형]: {d['testType']}에 최적화된 발문을 구성하십시오.
3. [난이도]: {d['difficulty']} 수준에 맞춰 사고의 깊이를 조절하십시오.
4. [문항 구성]: 
   - 발문 (예: 다음 글을 바탕으로 할 때, ~으로 가장 적절한 것은?)
   - <보기> (필요 시 데이터 내 정보를 재구성)
   - 5지 선다형 선택지
   - 정답 및 정밀 해설 (데이터의 어느 부분에서 근거했는지 명시)

문체는 매우 격조 있고 정제된 공적 언어를 사용하십시오."""

        api_url = "https://api.openai.com/v1/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"[출제 근거 데이터]\\n{d['text']}"}
            ],
            "temperature": 0.3 # 무결성을 위해 무작위성을 최소화
        }

        try:
            req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req) as res:
                res_body = json.loads(res.read().decode('utf-8'))
                return res_body['choices'][0]['message']['content']
        except Exception as e:
            return f"출제 실패 (사유: {str(e)})"

with socketserver.TCPServer(("", PORT), PreciseKICEServer) as httpd:
    print(f"KICE 정밀 출제 시스템 가동 중... Port: {PORT}")
    httpd.serve_forever()
