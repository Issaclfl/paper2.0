import json
import requests

DEFAULT_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"


def _extract_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for start_ch, end_ch in [('[', ']'), ('{', '}')]:
        start = text.find(start_ch)
        end = text.rfind(end_ch)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"无法从响应中提取 JSON:\n{text[:500]}")


def call_llm(api_key, user_instruction, system_prompt, paragraphs,
             tables=None, headers_footers=None,
             base_url=DEFAULT_BASE_URL, model="mimo-v2.5",
             temperature=0.1):
    parts = [
        "## 段落内容",
        json.dumps(paragraphs, ensure_ascii=False, indent=2),
    ]
    if tables:
        parts.append("## 表格信息")
        parts.append(json.dumps(tables, ensure_ascii=False, indent=2))
    if headers_footers:
        parts.append("## 页眉页脚")
        parts.append(json.dumps(headers_footers, ensure_ascii=False, indent=2))
    parts.append("## 用户指令")
    parts.append(user_instruction)

    user_msg = "\n\n".join(parts)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = f"{base_url.rstrip('/')}/chat/completions"

    last_err = None
    for _ in range(2):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            result = _extract_json(content)
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                for v in result.values():
                    if isinstance(v, list):
                        return v
            return result
        except Exception as e:
            last_err = e
    raise RuntimeError(f"API 调用失败: {last_err}")


def call_llm_chat(api_key, messages,
                  base_url=DEFAULT_BASE_URL, model="mimo-v2.5",
                  temperature=0.1):
    """多轮对话调用，messages 是完整的对话历史。
    统一返回 {"reply": str, "formats": list}。
    """
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = f"{base_url.rstrip('/')}/chat/completions"

    last_err = None
    for _ in range(2):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            result = _extract_json(content)
            # 归一化：不管 LLM 返回 dict 还是 list，都转成标准格式
            if isinstance(result, dict):
                return {
                    "reply": result.get("reply", ""),
                    "formats": result.get("formats", []),
                }
            if isinstance(result, list):
                return {"reply": "", "formats": result}
            return {"reply": str(result), "formats": []}
        except Exception as e:
            last_err = e
    raise RuntimeError(f"API 调用失败: {last_err}")
