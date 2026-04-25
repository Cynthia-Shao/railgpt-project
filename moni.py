"""
铁路晚点调度助手 - 最终完美版
（按钮蓝色 + 界面拉长 + 回车/按钮双发送 + 不重复 + 自动清空）
"""
import streamlit as st
import time
import re

# ------------------------------
# 页面配置
# ------------------------------
st.set_page_config(
    page_title="铁路晚点调度助手",
    page_icon="🚄",
    layout="centered"
)

# 初始化会话
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "type": "welcome",
            "text": "你好！我是铁路调度助手。\n请告诉我车次、晚点情况或需要调整的问题，我会为你生成调度方案。"
        }
    ]

# ------------------------------
# 模拟回复
# ------------------------------
def mock_response(user_query: str) -> dict:
    train_match = re.search(r"G\d+", user_query)
    delay_match = re.search(r"(\d+)分钟", user_query)
    
    train_num = train_match.group() if train_match else "GXXXX"
    delay_min = delay_match.group(1) if delay_match else "XX"
    
    return {
        "role": "assistant",
        "type": "plan",
        "intro": "针对您提出的晚点情况，建议采取以下调整方案：",
        "plan_title": f"{train_num}次晚点{delay_min}分钟调度方案",
        "steps": [
            "立即通知后续车站（徐州东、南京南）调整接发车股道，优先保证正点列车通行。",
            f"在徐州东站将{train_num}次扣停15分钟，避让后续正点高铁，减少对整体运行图的影响。",
            "调度热备车底于南京南站待命，若晚点进一步扩大至60分钟以上，启用热备车底接续运行。",
            "通过车站广播及12306APP向旅客推送晚点信息，做好改签和退票引导。"
        ],
        "note": "预计到达终点站晚点约50分钟，请密切关注后续运行情况。"
    }

# ------------------------------
# CSS 样式（按钮恢复原来的蓝色）
# ------------------------------
st.markdown("""
<style>
/* 全局拉长界面高度 */
.stApp {
    background-color: #12121a;
    min-height: 100vh !important;
}
.main .block-container {
    max-width: 800px;
    padding-top: 2rem;
    padding-bottom: 5rem;
}

/* 消息行 */
.message-row { 
    display: flex; 
    gap: 10px; 
    margin: 12px 0; 
    align-items: flex-start; 
}
.message-row.user { 
    flex-direction: row-reverse; 
}

/* 头像 */
.avatar { 
    width: 36px; 
    height: 36px; 
    border-radius: 50%; 
    display: flex; 
    align-items: center; 
    justify-content: center; 
    font-size: 18px; 
    flex-shrink: 0; 
}
.avatar.assistant { 
    background-color: #e0e7ff; 
    color: #3b4b8b; 
}
.avatar.user { 
    background-color: #3b4b8b; 
    color: white; 
}

/* 气泡 */
.bubble { 
    padding: 12px 16px; 
    border-radius: 18px; 
    max-width: 75%; 
    line-height: 1.6; 
    color: #111 !important; 
}
.bubble.assistant { 
    background-color: #ffffff; 
    border: 1px solid #e5e7eb; 
}
.bubble.user { 
    background-color: #3b4b8b; 
    color: white !important; 
    text-align: right; 
}

/* 方案卡片 */
.plan-card { 
    background-color: #f9fafb; 
    border-left: 4px solid #3b4b8b; 
    border-radius: 8px; 
    padding: 16px; 
    margin: 12px 0; 
}
.plan-title { 
    font-size: 20px; 
    font-weight: bold;
    color: #3b4b8b; 
    margin-bottom: 16px; 
}
.step-item { 
    display: flex; 
    gap: 12px; 
    margin: 12px 0; 
    align-items: flex-start; 
}
.step-number { 
    width: 32px; 
    height: 32px; 
    border-radius: 50%; 
    background-color: #3b4b8b; 
    color: white; 
    display: flex; 
    align-items: center; 
    justify-content: center; 
    font-weight: bold; 
    flex-shrink: 0; 
}
.note-text { 
    color: #6b7280; 
    margin-top: 16px; 
}

/* 顶部标题 */
.header-bar { 
    background-color: #3b4b8b; 
    color: white; 
    padding: 18px 24px; 
    border-radius: 12px 12px 0 0; 
    margin-bottom: 16px; 
}

/* ====================== */
/* 发送按钮 → 原版深蓝色 */
/* ====================== */
.stFormSubmitButton>button {
    background-color: #3b4b8b !important;
    color: white !important;
    border-radius: 20px !important;
    padding: 8px 24px !important;
    border: none !important;
}
.stFormSubmitButton>button:hover {
    background-color: #2c3a70 !important;
}

/* 输入框 */
.stTextInput>div>div>input {
    background-color: #2a2a38;
    color: white;
    border-radius: 20px;
    padding: 8px 16px;
}
</style>
""", unsafe_allow_html=True)

# ------------------------------
# 标题栏
# ------------------------------
st.markdown("""
<div class="header-bar">
    <h3 style="margin:0; display: flex; align-items: center; gap: 8px;">
        🚄 铁路晚点调度助手
        <span style="font-size: 14px; font-weight: normal;">智能调整方案</span>
    </h3>
</div>
""", unsafe_allow_html=True)

# ------------------------------
# 渲染聊天记录
# ------------------------------
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f'''
        <div class="message-row user">
            <div class="avatar user">👤</div>
            <div class="bubble user">{msg["text"]}</div>
        </div>
        ''', unsafe_allow_html=True)
    else:
        if msg["type"] == "welcome":
            st.markdown(f'''
            <div class="message-row assistant">
                <div class="avatar assistant">🤖</div>
                <div class="bubble assistant">{msg["text"]}</div>
            </div>
            ''', unsafe_allow_html=True)
        elif msg["type"] == "plan":
            steps_html = ""
            for i, step in enumerate(msg["steps"], 1):
                steps_html += f'<div class="step-item"><div class="step-number">{i}</div><div>{step}</div></div>'
            plan_html = f'''
                <div class="plan-card">
                    <div class="plan-title">{msg["plan_title"]}</div>
                    {steps_html}
                    <div class="note-text">📍 {msg["note"]}</div>
                </div>
            '''
            full = f"{msg['intro']}{plan_html}"
            st.markdown(f'''
            <div class="message-row assistant">
                <div class="avatar assistant">🤖</div>
                <div class="bubble assistant">{full}</div>
            </div>
            ''', unsafe_allow_html=True)

# ------------------------------
# 输入框 + 发送按钮（稳定版）
# ------------------------------
with st.form("chat_form", clear_on_submit=True):
    col1, col2 = st.columns([5, 1])
    with col1:
        user_input = st.text_input(
            "",
            placeholder="例如：G123次列车晚点40分钟，请给出调整建议",
            label_visibility="collapsed"
        )
    with col2:
        submitted = st.form_submit_button("发送")

# ------------------------------
# 发送逻辑
# ------------------------------
if submitted and user_input.strip():
    st.session_state.messages.append({"role": "user", "text": user_input})
    with st.spinner(""):
        time.sleep(1)
    reply = mock_response(user_input)
    st.session_state.messages.append(reply)
    st.rerun()