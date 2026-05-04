from flask import Flask, request, jsonify
from flask_cors import CORS
import time

app = Flask(__name__)
CORS(app)

def process_query(user_query: str) -> dict:
    time.sleep(1.5)
    return {
        "answer": "针对您提出的晚点情况，建议采取以下调整方案：",
        "plan": {
            "title": "G1223次晚点40分钟调度方案",
            "steps": [
                "立即通知后续车站（徐州东、南京南）调整接发车股道，优先保证正点列车通行。",
                "在徐州东站将G1223次扣停15分钟，避让后续正点高铁，减少对整体运行图的影响。",
                "调度热备车底于南京南站待命，若晚点进一步扩大至60分钟以上，启用热备车底接续运行。",
                "通过车站广播及12306APP向旅客推送晚点信息，做好改签和退票引导。"
            ],
            "note": "预计到达终点站晚点约50分钟，请密切关注后续运行情况。"
        }
    }

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({"error": "请求格式错误"}), 400
    return jsonify(process_query(data['query']))

@app.route('/health')
def health():
    return jsonify(status="ok")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)