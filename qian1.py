from flask import Flask, render_template_string, send_from_directory
import os
import webbrowser

app = Flask(__name__)
FILE_DIR = "files"
os.makedirs(FILE_DIR, exist_ok=True)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>铁路调度指挥助手</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: "Microsoft YaHei", sans-serif;
        }
        body {
            background: #f5f7fa;
            height: 100vh;
            overflow: hidden;
        }
        .main-title {
            text-align: center;
            font-size: 28px;
            font-weight: bold;
            color: #0d3b8f;
            padding: 14px 0;
            background: #ffffff;
            border-bottom: 2px solid #c8d8f2;
        }
        .container {
            display: flex;
            height: calc(100vh - 70px);
            gap: 12px;
            padding: 12px;
        }
        .column {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.07);
            padding: 16px;
            overflow-y: auto;
        }
        .left { width: 290px; }
        .middle { flex: 1; display: flex; flex-direction: column; }
        .right { width: 300px; }
        .title {
            font-size: 18px;
            font-weight: bold;
            color: #222;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid #eee;
        }
        .file-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 12px;
            background: #f7f9fc;
            margin-bottom: 8px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
        }
        .file-item:hover { background: #e6effc; }
        .file-icon { font-size: 16px; width: 20px; text-align: center; }
        .tip { font-size: 13px; color: #888; margin: 10px 0 16px; }

        .chat-box {
            flex: 1;
            background: #f9fbfd;
            border-radius: 8px;
            padding: 14px;
            overflow-y: auto;
            margin-bottom: 12px;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }
        .message {
            max-width: 82%;
            padding: 12px 16px;
            border-radius: 12px;
            line-height: 1.7;
            font-size: 14px;
        }
        .message-user {
            background: #0d3b8f;
            color: #fff;
            align-self: flex-end;
        }
        .message-ai {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            color: #222;
            align-self: flex-start;
            white-space: pre-line;
        }
        .input-group {
            display: flex;
            gap: 8px;
        }
        #msgInput {
            flex: 1;
            padding: 12px 14px;
            border: 1px solid #ddd;
            border-radius: 8px;
            outline: none;
            font-size: 14px;
        }
        #sendBtn {
            padding: 12px 20px;
            background: #0d3b8f;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 500;
        }
        #sendBtn:disabled {
            background: #94a3b8;
            cursor: not-allowed;
        }

        .panel { margin-bottom: 18px; }
        .panel-title {
            font-size: 14px;
            font-weight: bold;
            color: #0d3b8f;
            margin-bottom: 8px;
            padding-left: 6px;
            border-left: 3px solid #0d3b8f;
        }
        .panel-item {
            background: #eef5ff;
            padding: 9px 12px;
            border-radius: 6px;
            margin-bottom: 6px;
            font-size: 13px;
            line-height: 1.5;
        }
    </style>
</head>

<body>
    <div class="main-title">🚄 铁路调度指挥助手</div>
    <div class="container">

        <!-- 左侧文件 -->
        <div class="column left">
            <div class="title">📁 调度文件</div>
            <div class="tip">双击文件可打开查看</div>
            {% for file in file_list %}
            <div class="file-item" ondblclick="window.open('/file/{{file}}','_blank')">
                {% if '.xlsx' in file %}<span class="file-icon">📊</span>
                {% elif '.pdf' in file %}<span class="file-icon">📑</span>
                {% elif '.doc' in file %}<span class="file-icon">📘</span>
                {% elif '.txt' in file %}<span class="file-icon">📄</span>
                {% else %}<span class="file-icon">📎</span>{% endif %}
                <span>{{file}}</span>
            </div>
            {% endfor %}
        </div>

        <!-- 中间聊天 -->
        <div class="column middle">
            <div class="title">💬 智能调度指挥</div>
            <div class="chat-box" id="chatBox">
                <div class="message message-ai">你好！我是智能调度助手，请输入列车晚点信息。</div>
            </div>
            <div class="input-group">
                <input type="text" id="msgInput" placeholder="例如：G1223次列车晚点40分钟">
                <button id="sendBtn">发送</button>
            </div>
        </div>

        <!-- 右侧专业面板（三合一） -->
        <div class="column right">
            <div class="title">📌 调度业务中心</div>

            <div class="panel">
                <div class="panel-title">📜 调度规章速查</div>
                <div class="panel-item">• 晚点≥15分钟：必须下达调整命令</div>
                <div class="panel-item">• 会让避让原则：正点列车优先</div>
                <div class="panel-item">• 晚点≥30分钟：立即启动客运联动</div>
                <div class="panel-item">• 区间封锁：禁止放行任何列车</div>
                <div class="panel-item">• 加开列车需提前20分钟申报</div>
            </div>

            <div class="panel">
                <div class="panel-title">⚡ 常用调度指令</div>
                <div class="panel-item">1. 列车晚点通报指令</div>
                <div class="panel-item">2. 区间避让调整指令</div>
                <div class="panel-item">3. 股道变更接发指令</div>
                <div class="panel-item">4. 热备车底出动指令</div>
                <div class="panel-item">5. 客运联动广播指令</div>
            </div>

            <div class="panel">
                <div class="panel-title">🛡️ 行车安全提示</div>
                <div class="panel-item">• 严格执行“一令一动”</div>
                <div class="panel-item">• 严禁臆测行车、超速行车</div>
                <div class="panel-item">• 执行眼看、手比、口呼</div>
                <div class="panel-item">• 区间确认无误方可放行</div>
                <div class="panel-item">• 所有操作必须记录留痕</div>
            </div>
        </div>

    </div>

    <script>
        const chatBox = document.getElementById('chatBox');
        const msgInput = document.getElementById('msgInput');
        const sendBtn = document.getElementById('sendBtn');

        async function send() {
            const text = msgInput.value.trim();
            if (!text) return;

            // 用户消息
            const userMsg = document.createElement('div');
            userMsg.className = 'message message-user';
            userMsg.textContent = text;
            chatBox.appendChild(userMsg);
            msgInput.value = '';
            chatBox.scrollTop = chatBox.scrollHeight;

            sendBtn.disabled = true;
            const loading = document.createElement('div');
            loading.className = 'message message-ai';
            loading.textContent = '调度系统处理中...';
            chatBox.appendChild(loading);
            chatBox.scrollTop = chatBox.scrollHeight;

            try {
                const res = await fetch('http://127.0.0.1:5001/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question: text })
                });
                const data = await res.json();
                chatBox.removeChild(loading);

                const aiMsg = document.createElement('div');
                aiMsg.className = 'message message-ai';
                aiMsg.textContent = data.answer;
                chatBox.appendChild(aiMsg);
            } catch (e) {
                chatBox.removeChild(loading);
                const errMsg = document.createElement('div');
                errMsg.className = 'message message-ai';
                errMsg.textContent = '后端服务未启动，请启动 backend.py';
                chatBox.appendChild(errMsg);
            } finally {
                sendBtn.disabled = false;
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        }

        sendBtn.onclick = send;
        msgInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                send();
            }
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    files = [f for f in os.listdir(FILE_DIR) if os.path.isfile(os.path.join(FILE_DIR, f))]
    return render_template_string(HTML_TEMPLATE, file_list=files)

@app.route('/file/<filename>')
def get_file(filename):
    return send_from_directory(FILE_DIR, filename)

if __name__ == '__main__':
    webbrowser.open('http://127.0.0.1:5000')
    app.run(port=5000, debug=False)