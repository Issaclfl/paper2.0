"""AI 排版助手 v1.2 - 网页版（智能体模式）"""
import tempfile
from pathlib import Path

import streamlit as st

from agent import FormatAgent
from llm_client import DEFAULT_BASE_URL

st.set_page_config(page_title="AI 排版助手 v1.2", page_icon="📄", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #f0f2f5; }
    .stButton > button[kind="primary"] {
        background-color: #0071e3 !important; border: none !important; color: white !important;
        font-size: 16px !important;
    }
    .stButton > button[kind="primary"]:hover { background-color: #0077ed !important; }
    section[data-testid="stSidebar"] { background-color: #ffffff; }
    .stDownloadButton > button {
        background-color: #34c759 !important; border: none !important; color: white !important;
        font-size: 16px !important;
    }
    h1 { color: #1d1d1f !important; font-size: 28px !important; }
    h2, h3 { color: #1d1d1f !important; }
    div[data-testid="stExpander"] { background-color: white; border-radius: 8px; font-size: 15px; }
    .stMarkdown { font-size: 15px; }
</style>
""", unsafe_allow_html=True)

# ── 侧边栏 ──
with st.sidebar:
    st.header("设置")
    api_key = st.text_input("API Key", type="password", placeholder="粘贴你的 Key")
    api_url = st.text_input("API 地址", value=DEFAULT_BASE_URL)
    model = st.text_input("模型", value="mimo-v2.5")
    st.divider()
    st.markdown("""
**使用流程**
1. 填入 API 密钥
2. 上传 .docx 文件
3. AI 自动分析并排版
4. 对话微调 → 自动重新执行
5. 下载结果
""")

# ── 主界面 ──
st.title("AI 排版助手 v1.2")
st.caption("上传文档 → 自动排版 → 对话微调")

uploaded = st.file_uploader("上传 Word 文档", type=["docx"])

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

            # 保存文件到临时目录
            tmp_dir = tempfile.mkdtemp()
            in_path = Path(tmp_dir) / uploaded.name
            in_path.write_bytes(uploaded.read())
            st.session_state.input_path = str(in_path)

            # 自动分析
            with st.spinner("正在提取文档结构..."):
                try:
                    reply, formats = st.session_state.agent.analyze(str(in_path))
                    st.session_state.formats = formats
                    st.session_state.chat_history.append({"role": "assistant", "content": reply})
                except Exception as e:
                    st.session_state.chat_history.append({"role": "assistant", "content": f"分析失败: {e}"})

            # 自动执行
            with st.spinner("正在应用排版格式..."):
                try:
                    out_path = str(Path(tmp_dir) / (Path(uploaded.name).stem + "_排版.docx"))
                    st.session_state.agent.execute(out_path)
                    st.session_state.output_path = out_path
                    st.session_state.changelog = st.session_state.agent.get_changelog()
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"排版完成！共修改 {len(formats)} 处。可对话微调或下载结果。"
                    })
                except Exception as e:
                    st.session_state.chat_history.append({"role": "assistant", "content": f"排版失败: {e}"})

    # ── 分栏布局 ──
    col_left, col_right = st.columns([2, 3])

    with col_left:
        st.subheader("文档分析")

        if st.session_state.get("changelog"):
            st.success(f"文档: {uploaded.name}")
            st.info(f"共修改 {len(st.session_state.changelog)} 处")

            with st.expander("查看变更详情", expanded=True):
                icons = {"paragraph": "📄", "table": "📊", "header_footer": "📑"}
                for ptype, desc in st.session_state.changelog:
                    icon = icons.get(ptype, "•")
                    st.markdown(f"{icon} {desc}")
        else:
            st.info("请选择文档")

    with col_right:
        st.subheader("对话排版")

        # 显示对话历史
        for msg in st.session_state.get("chat_history", []):
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.write(msg["content"])
            else:
                with st.chat_message("assistant"):
                    st.write(msg["content"])

        # 对话输入
        if user_input := st.chat_input("输入修改指令，如「标题改大一点」"):
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.spinner("AI 思考中..."):
                try:
                    agent = st.session_state.agent
                    reply, formats = agent.chat(user_input)
                    st.session_state.formats = formats

                    # 自动重新执行
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
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"错误: {e}"
                    })
            st.rerun()

        # 下载按钮
        if st.session_state.get("output_path"):
            st.divider()
            out_data = Path(st.session_state.output_path).read_bytes()
            st.download_button(
                label="下载排版后的文件",
                data=out_data,
                file_name=Path(st.session_state.output_path).name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
                use_container_width=True,
            )

else:
    st.markdown("""
    ---

    ### 智能体模式

    上传文档后，AI 会自动：
    1. 分析文档类型和结构
    2. 按照最佳实践排版
    3. 显示变更记录

    你可以通过对话微调排版方案，AI 会自动重新执行。
    """)
