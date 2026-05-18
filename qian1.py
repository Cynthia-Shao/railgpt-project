from flask import Flask, render_template_string, send_from_directory, abort
import os
import webbrowser

app = Flask(__name__)

# ---------- 文件目录配置 ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_DIR = os.path.join(BASE_DIR, "files")
os.makedirs(FILE_DIR, exist_ok=True)

# ---------- HTML 模板（两列布局：左侧上文件横条+下问答，右侧运行图） ----------
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>铁路调度指挥助手 - 专业运行图</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
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
        /* 两列布局 */
        .container {
            display: flex;
            height: calc(100vh - 70px);
            gap: 12px;
            padding: 12px;
        }
        /* 左侧列：上下结构 */
        .left-column {
            flex: 1;          /* 占剩余空间，与右侧比例可调 */
            display: flex;
            flex-direction: column;
            gap: 12px;
            min-width: 380px; /* 保证文件栏不换行太严重 */
        }
        /* 右侧列：运行图 */
        .right-column {
            flex: 2;          /* 右侧更宽，展示运行图 */
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.07);
            padding: 16px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
        }
        /* 共用卡片样式 */
        .card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.07);
            padding: 16px;
            overflow: auto;
        }
        .card-title {
            font-size: 18px;
            font-weight: bold;
            color: #222;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid #eee;
        }
        /* 文件栏横向滚动区域 */
        .files-horizontal {
            display: flex;
            gap: 12px;
            overflow-x: auto;
            padding-bottom: 8px;
            flex-wrap: nowrap;
        }
        .file-card {
            flex: 0 0 auto;
            width: 140px;
            background: #f7f9fc;
            border-radius: 8px;
            padding: 12px 8px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid #e2e8f0;
        }
        .file-card:hover {
            background: #e6effc;
            transform: translateY(-2px);
        }
        .file-icon {
            font-size: 32px;
            display: block;
            margin-bottom: 8px;
        }
        .file-name {
            font-size: 13px;
            word-break: break-all;
            color: #0d3b8f;
        }
        /* 问答区域 */
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
            min-height: 200px;
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
        /* 运行图容器 */
        #trainGraph {
            width: 100%;
            height: 70vh;
            background: #fefefe;
            border-radius: 8px;
            flex: 1;
        }
        .graph-note {
            font-size: 12px;
            color: #555;
            margin-top: 8px;
            text-align: center;
        }
        /* 提示文字 */
        .tip-text {
            font-size: 12px;
            color: #888;
            margin-top: 8px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="main-title">🚄 铁路调度指挥助手</div>
    <div class="container">
        <!-- 左侧列：上方横向文件栏 + 下方问答 -->
        <div class="left-column">
            <!-- 横向文件栏卡片 -->
            <div class="card">
                <div class="card-title">📁 调度文件（双击打开）</div>
                <div class="files-horizontal" id="fileList">
                    {% for file in file_list %}
                    <div class="file-card" ondblclick="window.open('/file/{{file}}','_blank')">
                        <div class="file-icon">
                            {% if '.xlsx' in file or '.xls' in file %}📊
                            {% elif '.pdf' in file %}📑
                            {% elif '.doc' in file or '.docx' in file %}📘
                            {% elif '.txt' in file %}📄
                            {% elif '.png' in file or '.jpg' in file or '.jpeg' in file or '.gif' in file %}🖼️
                            {% else %}📎
                            {% endif %}
                        </div>
                        <div class="file-name">{{ file }}</div>
                    </div>
                    {% endfor %}
                </div>
                {% if file_list|length == 0 %}
                <div style="color:#999; text-align:center; padding:20px;">暂无文件，请将文件放入 "files" 文件夹</div>
                {% endif %}
                <div class="tip-text">💡 提示：双击文件图标即可在新标签页打开/下载</div>
            </div>
            <!-- 问答卡片 -->
            <div class="card" style="flex:1; display: flex; flex-direction: column;">
                <div class="card-title">💬 智能调度指挥</div>
                <div class="chat-box" id="chatBox">
                    <div class="message message-ai">你好！我是智能调度助手，请输入列车晚点信息。</div>
                </div>
                <div class="input-group">
                    <input type="text" id="msgInput" placeholder="例如：G1223次列车晚点40分钟">
                    <button id="sendBtn">发送</button>
                </div>
            </div>
        </div>

        <!-- 右侧列：专业运行图 -->
        <div class="right-column">
            <div class="card-title">📌 列车运行图（时间-车站）</div>
            <div id="trainGraph"></div>
            <div class="graph-note">⚡ 横轴为时间（分钟） | 纵轴为车站顺序 | 每条线代表一列车 | 鼠标可缩放拖拽</div>
        </div>
    </div>

    <script>
        const chatBox = document.getElementById('chatBox');
        const msgInput = document.getElementById('msgInput');
        const sendBtn = document.getElementById('sendBtn');
        let myChart = null;

        function formatTime(minutes) {
            let h = Math.floor(minutes / 60);
            let m = minutes % 60;
            return `${h.toString().padStart(2,'0')}:${m.toString().padStart(2,'0')}`;
        }

        async function loadAndDrawGraph() {
            try {
                const response = await fetch('http://127.0.0.1:5001/api/timetable');
                if (!response.ok) throw new Error('后端无响应');
                const data = await response.json();
                if (data.error) {
                    document.getElementById('trainGraph').innerHTML = `<div style="color:red;padding:20px;">${data.error}</div>`;
                    return;
                }

                const stations = data.stations;
                const trains = data.trains;
                const timesMatrix = data.times;
                let series = [];
                let allValidPoints = [];

                for (let i = 0; i < trains.length; i++) {
                    let trainName = trains[i];
                    let points = [];
                    for (let j = 0; j < stations.length; j++) {
                        let timeStr = timesMatrix[i][j];
                        if (timeStr && timeStr !== '' && !isNaN(parseFloat(timeStr))) {
                            let timeVal = parseFloat(timeStr);
                            points.push([timeVal, j]);
                            allValidPoints.push(timeVal);
                        }
                    }
                    if (points.length < 2) continue;
                    points.sort((a,b) => a[0] - b[0]);
                    series.push({
                        name: trainName,
                        type: 'line',
                        data: points,
                        smooth: false,
                        lineStyle: { width: 1.5, opacity: 0.7 },
                        symbol: 'circle',
                        symbolSize: 4,
                        emphasis: { focus: 'series' }
                    });
                }

                let minTime = Math.min(...allValidPoints);
                let maxTime = Math.max(...allValidPoints);
                let timePadding = (maxTime - minTime) * 0.05;
                minTime = Math.max(0, minTime - timePadding);
                maxTime = maxTime + timePadding;

                if (myChart) myChart.dispose();
                myChart = echarts.init(document.getElementById('trainGraph'));
                myChart.setOption({
                    tooltip: {
                        trigger: 'axis',
                        axisPointer: { type: 'shadow' },
                        formatter: function(params) {
                            if (!params || params.length === 0) return '';
                            let timeVal = params[0].value[0];
                            let timeStr = formatTime(timeVal);
                            let stationIndex = params[0].value[1];
                            let stationName = stations[stationIndex];
                            let html = `<strong>时间: ${timeStr}</strong><br/>车站: ${stationName}<br/>`;
                            params.forEach(p => { html += `${p.marker} ${p.seriesName}<br/>`; });
                            return html;
                        }
                    },
                    legend: { type: 'scroll', orient: 'vertical', right: 10, top: 20, bottom: 20, itemWidth: 20, itemHeight: 12, textStyle: { fontSize: 10 } },
                    grid: { left: '8%', right: '15%', top: '10%', bottom: '8%', containLabel: false },
                    xAxis: { name: '时间 (分钟)', nameLocation: 'middle', nameGap: 35, type: 'value', min: minTime, max: maxTime, axisLabel: { formatter: formatTime } },
                    yAxis: { name: '车站', nameLocation: 'middle', nameGap: 50, type: 'category', data: stations, axisLabel: { fontWeight: 'bold', fontSize: 11 } },
                    series: series,
                    toolbox: { feature: { dataZoom: { yAxisIndex: 'none' }, restore: {}, saveAsImage: {} }, right: 40 },
                    dataZoom: [{ type: 'inside', xAxisIndex: 0 }, { type: 'slider', xAxisIndex: 0, bottom: 10 }]
                });
                window.addEventListener('resize', () => myChart.resize());
            } catch (error) {
                console.error(error);
                document.getElementById('trainGraph').innerHTML = `<div style="color:red;padding:20px;">加载运行图失败，请确保后端服务已启动。</div>`;
            }
        }

        async function send() {
            const text = msgInput.value.trim();
            if (!text) return;
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
                errMsg.textContent = '后端服务未启动，请启动 hou1.py';
                chatBox.appendChild(errMsg);
            } finally {
                sendBtn.disabled = false;
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        }

        sendBtn.onclick = send;
        msgInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); send(); } });
        loadAndDrawGraph();
    </script>
</body>
</html>
'''

# ---------- 路由定义 ----------
@app.route('/')
def index():
    files = [f for f in os.listdir(FILE_DIR) if os.path.isfile(os.path.join(FILE_DIR, f))]
    return render_template_string(HTML_TEMPLATE, file_list=files)

@app.route('/file/<path:filename>')
def get_file(filename):
    """安全提供文件，支持中文名"""
    try:
        safe_path = os.path.normpath(os.path.join(FILE_DIR, filename))
        if not safe_path.startswith(os.path.abspath(FILE_DIR)):
            abort(403)
        return send_from_directory(FILE_DIR, filename, as_attachment=False)
    except Exception as e:
        print(f"文件服务错误: {e}")
        abort(404)

if __name__ == '__main__':
    webbrowser.open('http://127.0.0.1:5000')
    app.run(port=5000, debug=False)