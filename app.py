"""AI 排版助手 v1.2 - 网页版"""
import tempfile
from pathlib import Path

import streamlit as st

from agent import FormatAgent
from llm_client import DEFAULT_BASE_URL

st.set_page_config(page_title="AI 排版助手", page_icon="📄", layout="wide")

st.markdown("""
<style>
    /* 全局 */
    .stApp { background-color: #ffffff; }
    /* 侧边栏 */
    section[data-testid="stSidebar"] { background-color: #f8fafc; border-right: 1px solid #e2e8f0; }
    section[data-testid="stSidebar"] .stMarkdown { color: #334155; }
    /* 标题 */
    h1 { color: #0f172a !important; font-size: 26px !important; font-weight: 700 !important; }
    h2, h3 { color: #1e293b !important; font-weight: 600 !important; }
    /* 按钮 */
    .stButton > button[kind="primary"] {
        background-color: #2563eb !important; border: none !important;
        color: white !important; border-radius: 8px !important;
        font-weight: 600 !important; transition: background 0.2s !important;
    }
    .stButton > button[kind="primary"]:hover { background-color: #1d4ed8 !important; }
    .stDownloadButton > button {
        background-color: #0ea5e9 !important; border: none !important;
        color: white !important; border-radius: 8px !important; font-weight: 600 !important;
    }
    /* 输入框 */
    .stTextInput > div > div > input {
        border-radius: 8px !important; border: 1px solid #cbd5e1 !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #2563eb !important; box-shadow: 0 0 0 2px rgba(37,99,235,0.15) !important;
    }
    /* 上传区 */
    section[data-testid="stFileUploader"] {
        border: 2px dashed #cbd5e1; border-radius: 12px; padding: 8px;
    }
    section[data-testid="stFileUploader"]:hover { border-color: #2563eb; }
    /* 聊天 */
    div[data-testid="stChatMessage"] {
        border-radius: 12px; padding: 8px 12px; margin: 4px 0;
    }
    /* 分割线 */
    hr { border: none; border-top: 1px solid #e2e8f0; margin: 12px 0; }
    /* expander */
    div[data-testid="stExpander"] {
        border: 1px solid #e2e8f0; border-radius: 8px;
    }
    /* 全局字体 */
    .stMarkdown, .stText, p, span { font-size: 15px; }
</style>
""", unsafe_allow_html=True)

# ── 侧边栏 ──
with st.sidebar:
    st.markdown("### 设置")
    api_key = st.text_input("API Key", type="password", placeholder="粘贴你的 Key")
    api_url = st.text_input("API 地址", value=DEFAULT_BASE_URL)
    model = st.text_input("模型", value="mimo-v2.5")
    st.markdown("---")
    st.markdown("""
> **使用流程**
> 1. 填入 API 密钥
> 2. 上传 .docx 文件
> 3. AI 自动分析并排版
> 4. 对话微调，自动重新执行
> 5. 下载结果
""")

# ── 主界面 ──
st.markdown("# AI 排版助手")
st.caption("上传文档 · 自动排版 · 对话微调")

# ── 初始化 session state ──
for key, default in [
    ("agent", None), ("current_file", None), ("chat_history", []),
    ("formats", []), ("output_path", None), ("changelog", []),
    ("input_path", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

uploaded = st.file_uploader("上传 Word 文档", type=["docx"], label_visibility="collapsed")

if uploaded:
    # 自动触发分析
    if "agent" not in st.session_state or st.session_state.get("current_file") != uploaded.name:
        if api_key:
            st.session_state.agent = FormatAgent(api_key, api_url, model)
            st.session_state.current_file = uploaded.name
            st.session_state.chat_history = []
            st.session_state.formats = []
            st.session_state.output_path = None
            st.session_state.changelog = []

            tmp_dir = tempfile.mkdtemp()
            in_path = Path(tmp_dir) / uploaded.name
            in_path.write_bytes(uploaded.read())
            st.session_state.input_path = str(in_path)

            with st.spinner("正在分析文档..."):
                try:
                    reply, formats = st.session_state.agent.analyze(str(in_path))
                    st.session_state.formats = formats
                    st.session_state.chat_history.append({"role": "assistant", "content": reply})
                except Exception as e:
                    st.session_state.chat_history.append({"role": "assistant", "content": f"分析失败: {e}"})

            with st.spinner("正在排版..."):
                try:
                    out_path = str(Path(tmp_dir) / (Path(uploaded.name).stem + "_排版.docx"))
                    st.session_state.agent.execute(out_path)
                    st.session_state.output_path = out_path
                    st.session_state.changelog = st.session_state.agent.get_changelog()
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"排版完成！共修改 {len(formats)} 处。可通过对话微调。"
                    })
                except Exception as e:
                    st.session_state.chat_history.append({"role": "assistant", "content": f"排版失败: {e}"})

    # ── 分栏 ──
    col_l, col_r = st.columns([2, 3])

    with col_l:
        st.markdown("### 分析结果")
        if st.session_state.get("changelog"):
            st.markdown(f"**{uploaded.name}** — 共修改 {len(st.session_state.changelog)} 处")
            with st.expander("变更详情", expanded=True):
                for ptype, desc in st.session_state.changelog:
                    st.markdown(f"• {desc}")
        else:
            st.info("等待上传文档...")

    with col_r:
        st.markdown("### 对话微调")
        for msg in st.session_state.get("chat_history", []):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if user_input := st.chat_input("输入修改指令，如「标题改大一点」"):
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.spinner("AI 思考中..."):
                try:
                    agent = st.session_state.agent
                    reply, formats = agent.chat(user_input)
                    st.session_state.formats = formats
                    out_path = str(
                        Path(st.session_state.input_path).parent
                        / (Path(st.session_state.current_file).stem + "_排版.docx")
                    )
                    agent.execute(out_path)
                    st.session_state.output_path = out_path
                    st.session_state.changelog = agent.get_changelog()
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"{reply}\n\n已重新排版，共修改 {len(formats)} 处。"
                    })
                except Exception as e:
                    st.session_state.chat_history.append({"role": "assistant", "content": f"错误: {e}"})
            st.rerun()

        if st.session_state.get("output_path"):
            st.markdown("---")
            out_data = Path(st.session_state.output_path).read_bytes()
            st.download_button(
                "下载排版后的文件",
                data=out_data,
                file_name=Path(st.session_state.output_path).name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
                use_container_width=True,
            )
else:
    st.markdown("---")
    st.markdown("""
    ### 智能体模式

    上传文档后，AI 会自动分析类型、排版、显示变更。
    你可以通过对话微调，AI 会自动重新执行。
    """)
