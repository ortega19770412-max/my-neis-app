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
    <title>KICE Exam Generator</title>
    <style>
        :root { --kice-blue: #1a3a5f; }
        body { font-family: 'Batang', serif; background-color: #f1f3f5; padding: 20px; }
        .container { max-width: 1200px; margin: auto; background: white; padding: 30px; border-radius: 12px; }
        .config-card { background: #fff; border: 1px solid #ddd; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .type-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; padding: 15px; background: #f8f9fa; margin: 15px 0; }
        textarea { width: 100%; height: 120px; padding: 15px; box-sizing: border-box; font-family: sans-serif; }
        .btn-generate { width: 100%; padding: 18px; background: var(--kice-blue); color: white; border: none; cursor: pointer; font-weight: bold; font-size: 1.1rem; }
        
        /* [중요] 시험지 영역 스타일 */
        #exam-paper { 
            display: block; /* 기본적으로 보이게 유지 */
            min-height: 200px;
            margin-top: 30px; 
            border-top: 2px solid #000; 
            padding-top: 30px; 
            column-count: 2; 
            column-rule: 1px solid #000; 
            gap: 50px; 
        }
        .q-unit { break-inside: avoid; margin-bottom: 40px; }
        .q-passage { border: 1px solid #000; padding: 15px; margin-bottom: 15px; line-height: 1.8; text-align: justify; }
        .options { list-style: none; padding: 0; }
        .options li { margin-bottom: 5px; }
        .answer-key { column-span: all; background: #eee; padding: 20px; margin-top: 30px; border-radius: 5px; font-family: sans-serif; }
        
        .loading { display:none; text-align: center; font-weight: bold; color: blue; padding: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h2 style="text-align:center; border-bottom: 3px double #000;">수능 영어 문항 생성기</h2>
        <div class="config-card">
            <div><strong>난이도:</strong> <select id="difficulty"><option>Lv.1</option><option selected>Lv.3</option><option>Lv.5</option></select></div>
            <div class="type-grid" id="selectors">
                <label><input type="checkbox" value="어법 판단" checked> 어법 판단</label>
                <label><input type="checkbox" value="빈칸 추론" checked> 빈칸 추론</label>
                <label><input type="checkbox" value="내용 일치" checked> 내용 일치</label>
                <label><input type="checkbox" value="주제/제목" checked> 주제/제목</label>
            </div>
            <textarea id="sourceText" placeholder="지문을 입력해 주세요..."></textarea>
            <button class="btn-generate" onclick="generateExam()">수능형 정밀 문항 생성</button>
        </div>
        
        <div id="loading-msg" class="loading">문항을 생성 중입니다... 잠시만 기다려 주세요.</div>
        <div id="exam-paper"></div>
    </div>

    <script>
        async function generateExam() {
            const text = document.getElementById('sourceText').value;
            const selectors = Array.from(document.querySelectorAll('#selectors input:checked')).map(el => el.value);
            if(!text) return alert('지문을 입력하세요.');

            document.getElementById('loading-msg').style.display = 'block';
            document.getElementById('exam-paper').innerHTML = '';

            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text, tasks: selectors, difficulty: document.getElementById('difficulty').value })
                });
                const data = await response.json();
                
                document.getElementById('loading-msg').style.display = 'none';
                // AI 응답을 div에 주입
                document.getElementById('exam-paper').innerHTML = data.content;
            } catch (e) {
                alert('오류가 발생했습니다: ' + e);
                document.getElementById('loading-msg').style.display = 'none';
            }
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
        # AI가 HTML만 정확하게 내뱉도록 강력 지시
        system_prompt = f"""당신은 수능 영어 출제 위원입니다. 
제시된 지문을 바탕으로 수능 규격 문항을 **{len(d['tasks'])}문제 필수 출제**하십시오.

[출제 가이드라인]
1. 불필요한 서론(네, 알겠습니다 등)이나 <html>, <body> 같은 태그를 절대 쓰지 마십시오.
2. 오직 <div class="q-unit"> 으로 시작하는 문제 내용만 출력하십시오.
3. 어법 문항은 본문에 <u>①</u>~<u>⑤</u> 총 5개의 밑줄을 반드시 표시하고 보기 ①~⑤와 일치시키십시오.
4. 모든 문항은 5지선다형(`<ul class="options"><li>① ...</li></ul>`)입니다.
5. 마지막에 `<div class="answer-key">`를 만들어 모든 문제의 정답과 해설을 넣으십시오.
"""
        api_url = "https://api.openai.com/v1/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"지문: {d['text']}\\n유형: {d['tasks']}"}
            ],
            "temperature": 0.3
        }
        
        try:
            req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req) as res:
                res_data = json.loads(res.read().decode('utf-8'))
                return res_data['choices'][0]['message']['content']
        except Exception as e:
            return f"<div>AI 문항 생성 중 시스템 오류가 발생했습니다: {str(e)}</div>"

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), ExamServer) as httpd:
        httpd.serve_forever()
