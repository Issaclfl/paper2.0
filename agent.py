"""排版智能体：自动分析文档 + 多轮对话微调"""
import json
from pathlib import Path

from doc_formatter import DocFormatter
from llm_client import call_llm_chat
from prompts import AGENT_SYSTEM_PROMPT


class FormatAgent:
    def __init__(self, api_key, base_url="https://token-plan-cn.xiaomimimo.com/v1",
                 model="mimo-v2.5"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.messages = []  # 对话历史
        self.formats = []   # 当前排版方案
        self.formatter = None
        self.docx_path = None

    def analyze(self, docx_path):
        """第一轮：自动分析文档，给出排版建议"""
        self.docx_path = docx_path
        self.formatter = DocFormatter(docx_path)
        self.messages = []

        # 提取文档结构
        paragraphs = self.formatter.extract_paragraphs()
        tables = self.formatter.extract_tables()
        hf = self.formatter.extract_headers_footers()

        # 构造分析请求
        doc_info = (
            "## 文档内容\n"
            f"段落:\n{json.dumps(paragraphs, ensure_ascii=False, indent=2)}\n\n"
        )
        if tables:
            doc_info += f"表格:\n{json.dumps(tables, ensure_ascii=False, indent=2)}\n\n"
        if hf:
            doc_info += f"页眉页脚:\n{json.dumps(hf, ensure_ascii=False, indent=2)}\n\n"

        user_msg = (
            f"{doc_info}\n"
            "请分析这篇文档的类型和结构，给出专业的排版建议。"
        )

        # 初始化对话历史
        self.messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        # 调用 LLM
        result = call_llm_chat(
            api_key=self.api_key,
            messages=self.messages,
            base_url=self.base_url,
            model=self.model,
        )

        # 解析回复
        reply = result.get("reply", "")
        self.formats = result.get("formats", [])

        # 追加 assistant 回复到历史
        self.messages.append({
            "role": "assistant",
            "content": json.dumps(result, ensure_ascii=False),
        })

        return reply, self.formats

    def chat(self, user_message):
        """后续轮：根据用户修改指令调整排版方案"""
        # 追加用户消息到历史
        self.messages.append({"role": "user", "content": user_message})

        # 调用 LLM
        result = call_llm_chat(
            api_key=self.api_key,
            messages=self.messages,
            base_url=self.base_url,
            model=self.model,
        )

        reply = result.get("reply", "")
        self.formats = result.get("formats", self.formats)

        # 追加 assistant 回复到历史
        self.messages.append({
            "role": "assistant",
            "content": json.dumps(result, ensure_ascii=False),
        })

        return reply, self.formats

    def execute(self, output_path):
        """执行当前排版方案"""
        if not self.formatter or not self.formats:
            raise RuntimeError("请先分析文档")
        self.formatter.execute(self.formats)
        self.formatter.save_as(output_path)
        return output_path

    def get_changelog(self):
        """生成人类可读的变更列表"""
        lines = []
        _CN_SIZES = {
            42: "初号", 36: "小初", 26: "一号", 24: "小一",
            22: "二号", 18: "小二", 16: "三号", 15: "小三",
            14: "四号", 12: "小四", 10.5: "五号", 9: "小五",
        }
        _ALIGN_CN = {"center": "居中", "left": "左对齐", "right": "右对齐", "justify": "两端对齐"}

        for item in self.formats:
            if "idx" in item:
                desc = f"段落[{item['idx']}]"
                if "font" in item:
                    desc += f" → {item['font']}"
                if "size_pt" in item:
                    pt = item["size_pt"]
                    cn = _CN_SIZES.get(pt, "")
                    desc += f" {cn}{pt}pt" if cn else f" {pt}pt"
                if item.get("bold"):
                    desc += " 加粗"
                if "align" in item and item["align"] in _ALIGN_CN:
                    desc += f" {_ALIGN_CN[item['align']]}"
                if "indent_chars" in item:
                    desc += f" 缩进{item['indent_chars']}字符"
                if "line_spacing" in item:
                    desc += f" {item['line_spacing']}倍行距"
                elif "line_spacing_pt" in item:
                    desc += f" 行距{item['line_spacing_pt']}磅"
                lines.append(("paragraph", desc))

            elif "table_idx" in item:
                desc = f"表格[{item['table_idx']}]"
                if "row_height_cm" in item:
                    desc += f" 行高{item['row_height_cm']}cm"
                if "col_widths_cm" in item:
                    desc += f" 列宽{item['col_widths_cm']}"
                if "header_bold" in item and item["header_bold"]:
                    desc += " 表头加粗"
                if "font" in item:
                    desc += f" {item['font']}"
                lines.append(("table", desc))

            elif "section_idx" in item:
                desc = f"节[{item['section_idx']}]"
                if "header_text" in item:
                    desc += f" 页眉: {item['header_text']}"
                if "footer_page_num" in item and item["footer_page_num"]:
                    desc += " 页脚: 页码"
                lines.append(("header_footer", desc))

        return lines
