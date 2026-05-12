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
    <title>铁路调度助手</title>
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

        /* 顶部大标题 */
        .main-title {
            text-align: center;
            font-size: 28px;
            font-weight: bold;
            color: #1a4d8c;
            padding: 14px 0;
            background: #ffffff;
            border-bottom: 2px solid #d0e0f5;
        }

        /* 三列布局 */
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

        /* 文件列表 + 图标 */
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

        /* 聊天区域 */
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
            background: #1a4d8c;
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

        /* 输入框 */
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
            background: #1a4d8c;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 500;
        }

        /* 右侧专业面板样式 */
        .panel {
            margin-bottom: 18px;
        }
        .panel-title {
            font-size: 14px;
            font-weight: bold;
            color: #1a4d8c;
            margin-bottom: 8px;
            padding-left: 6px;
            border-left: 3px solid #1a4d8c;
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
    <div class="main-title">🚄 铁路调度助手</div>

    <div class="container">
        <!-- 左侧：文件列表 -->
        <div class="column left">
            <div class="title">📁 调度文件</div>
            <div class="tip">双击文件可打开查看</div>

            {% for file in file_list %}
            <div class="file-item" ondblclick="window.open('/file/{{ file }}','_blank')">
                {% if file.endswith('.xlsx') or file.endswith('.xls') %}
                <span class="file-icon">📊</span>
                {% elif file.endswith('.pdf') %}
                <span class="file-icon">📑</span>
                {% elif file.endswith('.doc') or file.endswith('.docx') %}
                <span class="file-icon">📘</span>
                {% elif file.endswith('.txt') %}
                <span class="file-icon">📄</span>
                {% else %}
                <span class="file-icon">📎</span>
                {% endif %}
                <span>{{ file }}</span>
            </div>
            {% endfor %}
        </div>

        <!-- 中间：问答 -->
        <div class="column middle">
            <div class="title">💬 智能调度问答</div>
            <div class="chat-box" id="chatBox">
                <div class="message message-ai">你好！我是铁路调度助手，请输入列车晚点信息，我将为你生成调度方案。</div>
            </div>
            <div class="input-group">
                <input type="text" id="msgInput" placeholder="例如：G1223次列车晚点40分钟">
                <button id="sendBtn">发送</button>
            </div>
        </div>

        <!-- 右侧：三合一超强专业版 -->
        <div class="column right">
            <div class="title">📌 调度业务中心</div>

            <!-- 方案2：调度规章速查 -->
            <div class="panel">
                <div class="panel-title">📜 调度规章速查</div>
                <div class="panel-item">• 晚点≥15分钟：必须下达调整命令</div>
                <div class="panel-item">• 会让避让原则：正点列车优先</div>
                <div class="panel-item">• 晚点≥30分钟：立即启动客运联动</div>
                <div class="panel-item">• 区间封锁：禁止放行任何列车</div>
                <div class="panel-item">• 加开列车需提前20分钟申报</div>
            </div>

            <!-- 方案3：常用调度指令 -->
            <div class="panel">
                <div class="panel-title">⚡ 常用调度指令</div>
                <div class="panel-item">1. 列车晚点通报指令</div>
                <div class="panel-item">2. 区间避让调整指令</div>
                <div class="panel-item">3. 股道变更接发指令</div>
                <div class="panel-item">4. 热备车底出动指令</div>
                <div class="panel-item">5. 客运联动广播指令</div>
            </div>

            <!-- 方案4：行车安全提示 -->
            <div class="panel">
                <div class="panel-title">🛡️ 行车安全提示</div>
                <div class="panel-item">• 严格执行“一令一动”</div>
                <div class="panel-item">• 严禁臆测行车、超速行车</div>
                <div class="panel-item">• 接发列车执行“眼看、手比、口呼”</div>
                <div class="panel-item">• 区间确认无误方可放行</div>
                <div class="panel-item">• 所有操作必须记录留痕</div>
            </div>
        </div>
    </div>

    <script>
        const chatBox = document.getElementById('chatBox');
        const msgInput = document.getElementById('msgInput');
        const sendBtn = document.getElementById('sendBtn');

        // 发送消息
        function send() {
            const text = msgInput.value.trim();
            if (!text) return;

            // 用户消息
            const userMsg = document.createElement('div');
            userMsg.className = 'message message-user';
            userMsg.textContent = text;
            chatBox.appendChild(userMsg);
            msgInput.value = '';

            // 你要的标准格式回答
            setTimeout(() => {
                const aiMsg = document.createElement('div');
                aiMsg.className = 'message message-ai';
                
                aiMsg.textContent = `针对您提出的晚点情况，建议采取以下调整方案：

G1223次晚点40分钟调度方案
① 立即通知后续车站（徐州东、南京南）调整接发车股道，优先保证正点列车通行。
② 在徐州东站将G1223次扣停15分钟，避让后续正点高铁，减少对整体运行图的影响。
③ 调度热备车底于南京南站待命，若晚点进一步扩大至60分钟以上，启用热备车底接续运行。
④ 通过车站广播及12306APP向旅客推送晚点信息，做好改签和退票引导。

📍 预计到达终点站晚点约50分钟，请密切关注后续运行情况。`;

                chatBox.appendChild(aiMsg);
                chatBox.scrollTop = chatBox.scrollHeight;
            }, 500);
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
    file_list = [f for f in os.listdir(FILE_DIR) if os.path.isfile(os.path.join(FILE_DIR, f))]
    return render_template_string(HTML_TEMPLATE, file_list=file_list)

@app.route('/file/<filename>')
def serve_file(filename):
    return send_from_directory(FILE_DIR, filename)

if __name__ == '__main__':
    webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=False, port=5000)