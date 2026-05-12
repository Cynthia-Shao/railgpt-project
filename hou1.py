from flask import Flask, request, jsonify
from flask_cors import CORS
import re

app = Flask(__name__)
CORS(app)

def generate_plan(question):
    # 提取车次 + 晚点时间
    train = re.search(r'[GDKZT]\d+', question)
    delay = re.search(r'\d+', question)

    t = train.group() if train else "G1223"
    d = delay.group() if delay else "40"
    final = str(int(d) + 10)

    return f"""针对您提出的晚点情况，建议采取以下调整方案：

{t}次晚点{d}分钟调度方案
① 立即通知后续车站（徐州东、南京南）调整接发车股道，优先保证正点列车通行。
② 在徐州东站将{t}次扣停15分钟，避让后续正点高铁，减少对整体运行图的影响。
③ 调度热备车底于南京南站待命，若晚点进一步扩大至60分钟以上，启用热备车底接续运行。
④ 通过车站广播及12306APP向旅客推送晚点信息，做好改签和退票引导。

📍 预计到达终点站晚点约{final}分钟，请密切关注后续运行情况。"""

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    q = data.get('question', '')
    return jsonify({"answer": generate_plan(q)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)