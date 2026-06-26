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
    <title>KICE AI-English Exam System</title>
    <style>
        :root { --kice-blue: #1a3a5f; --accent: #2c5282; }
        body { font-family: 'Batang', serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1a202c; }
        .container { max-width: 1200px; margin: auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        
        /* UI Panel Styling from Image */
        .config-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 30px; }
        .row { display: flex; gap: 20px; align-items: center; margin-bottom: 15px; }
        .type-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; background: #f1f5f9; padding: 15px; border-radius: 8px; }
        .type-item { display: flex; align-items: center; font-size: 0.95rem; font-family: sans-serif; cursor: pointer; }
        .type-item input { margin-right: 8px; }
        
        textarea { width: 100%; height: 150px; border: 1px solid #cbd5e0; border-radius: 6px; padding: 15px; font-size: 1rem; line-height: 1.6; resize: vertical; box-sizing: border-box; }
        .btn-generate { width: 100%; padding: 18px; background: var(--kice-blue); color: white; border: none; border-radius: 6px; font-size: 1.1rem; font-weight: bold; cursor: pointer; transition: background 0.2s; margin-top: 15px; }
        .btn-generate:hover { background: #002a50; }

        /* Exam Paper Styling (2-Column) */
        #exam-paper { display: none; margin-top: 40px; border-top: 2px solid #000; padding-top: 20px; column-count: 2; column-rule: 1px solid #000; gap: 50px; }
        .q-unit { break-inside: avoid; margin-bottom: 40px; text-align: justify; }
        .q-header { font-weight: bold; margin-bottom: 10px; font-size: 1.1rem; }
        .q-passage { border: 1px solid #000; padding: 15px; margin-bottom: 15px; line-height: 1.8; font-size: 1rem; }
        .options { list-style: none; padding-left: 0; margin-top: 10px; }
        .options li { margin-bottom: 6px; }
        
        /* Answer Section */
        .answer-key { column-span: all; background: #edf2f7; border: 1px dashed #4a5568; padding: 20px; margin-top: 40px; border-radius: 8px; font-family: sans-serif; }
        @media print { .config-card { display: none; } body { padding: 0; } .container { box-shadow: none; max-width: 100%; } }
    </style>
</head>
<body>
    <div class="container">
        <h2 style="text-align:center; border-bottom: 3px double #000; padding-bottom:10px; margin-top:0;">2026학년도 대학수학능력시험 영농영역 (AI 모의평가)</h2>
        
        <div class="config-card">
            <div class="row">
                <label><strong>난이도:</strong></label>
                <select id="difficulty" style="padding:5px 10px;">
                    <option value="Lv.1 (기초)">Lv.1 (기초)</option>
                    <option value="Lv.3 (보통)" selected>Lv.3 (보통)</option>
                    <option value="Lv.5 (심화)">Lv.5 (심화)</option>
                </select>
                <input type="file" id="fileInput" style="margin-left:auto;">
            </div>

            <div class="type-grid" id="selectors">
                <label class="type-item"><input type="checkbox" value="어법 판단" checked> 어법 판단</label>
                <label class="type-item"><input type="checkbox" value="빈칸 추론" checked> 빈칸 추론</label>
                <label class="type-item"><input type="checkbox" value="내용 일치" checked> 내용 일치</label>
                <label class="type-item"><input type="checkbox" value="주제/제목" checked> 주제/제목</label>
                <label class="type-item"><input type="checkbox" value="글의 순서"> 글의 순서</label>
                <label class="type-item"><input type="checkbox" value="문장 삽입"> 문장 삽입</label>
                <label class="type-item"><input type="checkbox" value="분위기/심경"> 분위기/심경</label>
                <label class="type-item"><input type="checkbox" value="어휘 판단"> 어휘 판단</label>
            </div>

            <textarea id="sourceText" placeholder="이곳에 지문을 입력하세요..."></textarea>
            <button class="btn-generate" onclick="generateExam()">수능형 정밀 문항 생성</button>
        </div>

        <div id="exam-paper"></div>
    </div>

    <script>
        async function generateExam() {
            const text = document.getElementById('sourceText').value;
            if(!text) { alert('지문을 입력해주세요.'); return; }
            
            const types = Array.from(document.querySelectorAll('#selectors input:checked')).map(el => el.value);
            if(types.length < 1) { alert('최소 1개 이상의 유형을 선택해주세요.'); return; }

            const paper = document.getElementById('exam-paper');
            paper.innerHTML = '<p style="text-align:center;">AI가 문항을 제작 중입니다 (약 10~20초 소요)...</p>';
            paper.style.display = 'block';

            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: text,
                    tasks: types,
                    difficulty: document.getElementById('difficulty').value
                })
            });

            const data = await response.json();
            paper.innerHTML = data.content;
        }
    </script>
</body>
</html>
"""

class ExamServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header('Content-type', 'text/html; charset=utf-8'); self.end_headers()
        self.wfile.write(HTML_TEMPLATE.encode('utf-8'))

    def do_POST(self):
        if self.path == '/api/generate':
            length = int(self.headers['Content-Length']); data = json.loads(self.rfile.read(length))
            content = self.call_ai(data)
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({'content': content}).encode('utf-8'))

    def call_ai(self, d):
        system_prompt = f"""당신은 평가원 수석 영어 출제위원입니다. 
제시된 지문을 바탕으로 수능 영어 규격에 맞게 **{len(d['tasks'])}개 이상의 문항**을 생성하십시오.

[출제 지침 - 매우 중요]:
1. **문제 번호 일치**: '어법' 문항 출제 시 지문 본문 내 <u>①</u>~<u>⑤</u>의 위치와 하단 선택지의 1~5번 단어는 반드시 100% 일치해야 합니다.
2. **2단 구성 최적화**: 문항은 HTML `<div class="q-unit">`으로 감싸고, 지문은 `<div class="q-passage">`에 넣으십시오.
3. **5지선다**: 모든 문제는 오지선다형입니다.
4. **유형별 특징**: 
   - 내용 일치는 한글 선택지로 구성하십시오.
   - 빈칸 추론은 지문 내 적절한 위치에 (   )를 생성하십시오.
   - 어휘 판단은 본문에 (A), (B), (C) 선택형 또는 <u>①</u>~<u>⑤</u> 밑줄형으로 출제하십시오.
5. **난이도**: {d['difficulty']} 수준에 맞춰 매력적인 오답을 만드십시오.

[형식]: 결과물은 곧바로 div#exam-paper에 삽입될 HTML 조각이어야 합니다. 마지막에는 `<div class="answer-key">`를 만들어 정답과 해설을 포함하십시오."""

        api_url = "https://api.openai.com/v1/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"지문: {d['text']}\\n출제 희망 유형: {d['tasks']}"}
            ],
            "temperature": 0.4
        }
        
        try:
            req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req) as res:
                res_data = json.loads(res.read().decode('utf-8'))
                return res_data['choices'][0]['message']['content']
        except Exception as e:
            return f"<p>오류 발생: {str(e)}</p>"

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), ExamServer) as httpd:
        print(f"Server started at port {PORT}")
        httpd.serve_forever()
