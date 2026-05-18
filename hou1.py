from flask import Flask, request, jsonify
from flask_cors import CORS
import re
import pandas as pd
import os

app = Flask(__name__)
CORS(app)

# 加载运行图
TIMETABLE_DF = None
STATIONS = []
try:
    # 请确保文件名与您的实际文件完全一致
    file_path = 'planned_timetable(1).xlsx'
    if os.path.exists(file_path):
        TIMETABLE_DF = pd.read_excel(file_path, index_col=0)
        TIMETABLE_DF = TIMETABLE_DF.fillna('')
        STATIONS = list(TIMETABLE_DF.columns)
        print(f"成功加载运行图，共 {len(TIMETABLE_DF)} 趟列车，{len(STATIONS)} 个车站。")
    else:
        print(f"未找到运行图文件: {file_path}")
except Exception as e:
    print(f"加载运行图失败: {e}")

def generate_plan(question):
    # 提取车次和晚点时间
    train_match = re.search(r'([A-Za-z]+\d+)', question)
    delay_match = re.search(r'(\d+)\s*分钟', question)

    train_id = train_match.group(1) if train_match else None
    delay = int(delay_match.group(1)) if delay_match else 30

    response = f"针对您提出的晚点情况，建议采取以下调整方案：\n\n"

    if TIMETABLE_DF is not None and train_id and train_id in TIMETABLE_DF.index:
        train_data = TIMETABLE_DF.loc[train_id]
        
        start_station = None
        start_time = None
        for station in STATIONS:
            val = train_data[station]
            if val != '' and val != 0:
                start_time = val
                start_station = station
                break

        response += f"🚄 {train_id}次晚点{delay}分钟调度方案\n"
        response += f"① {train_id}次列车从{start_station}({start_time}分)出发后晚点。\n"
        
        conflicting_trains = []
        for other_train in TIMETABLE_DF.index:
            if other_train == train_id:
                continue
            other_data = TIMETABLE_DF.loc[other_train]
            for i, station in enumerate(STATIONS):
                t_time = train_data[station]
                o_time = other_data[station]
                if isinstance(t_time, (int, float)) and isinstance(o_time, (int, float)):
                    if t_time < o_time < t_time + delay:
                        conflicting_trains.append(other_train)
                        break
        
        if conflicting_trains:
            response += f"② 与 {', '.join(conflicting_trains[:3])} 等列车存在运行冲突，建议在前方站扣停避让。\n"
        else:
            response += f"② 目前暂无直接冲突列车，可维持原计划运行，注意追踪间隔。\n"
            
        response += f"③ 立即通知后续车站（徐州东、南京南）调整接发车股道，优先保证正点列车通行。\n"
        response += f"④ 调度热备车底于南京南站待命，若晚点进一步扩大至60分钟以上，启用热备车底接续运行。\n"
        response += f"⑤ 通过车站广播及12306APP向旅客推送晚点信息，做好改签和退票引导。\n\n"
        response += f"📍 预计到达终点站晚点约{delay + 10}分钟，请密切关注后续运行情况。"
    else:
        response += f"{train_id if train_id else '列车'}次晚点{delay}分钟调度方案\n"
        response += f"① 立即通知后续车站（徐州东、南京南）调整接发车股道，优先保证正点列车通行。\n"
        response += f"② 在徐州东站将{train_id if train_id else '列车'}次扣停15分钟，避让后续正点高铁。\n"
        response += f"③ 调度热备车底于南京南站待命，若晚点扩大至60分钟以上启用。\n"
        response += f"④ 做好旅客广播、改签及退票引导。\n\n"
        response += f"📍 预计到达终点站晚点约{delay + 10}分钟。"
    
    return response

@app.route('/api/timetable', methods=['GET'])
def get_timetable():
    """提供运行图数据给前端"""
    if TIMETABLE_DF is None:
        return jsonify({"error": "运行图未加载"}), 500
    
    stations = STATIONS
    trains = TIMETABLE_DF.index.tolist()
    times = TIMETABLE_DF.values.tolist()
    times = [[str(cell) if cell != '' else '' for cell in row] for row in times]
    
    return jsonify({
        "stations": stations,
        "trains": trains,
        "times": times
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    q = data.get('question', '')
    return jsonify({"answer": generate_plan(q)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)