"""
Token Usage Normalization

参考 Langfuse _parse_usage_model() 实现。
将各 LLM 厂商的 token 用量统一为标准格式 {input, output, total}。
支持 OpenAI, Anthropic, Bedrock, Vertex AI, IBM watsonx 等。
"""

from typing import Any, Optional

# 各厂商 key -> 标准化 key 的映射表
# 顺序很重要：先尝试特定厂商的 key，最后才是通用 key
USAGE_KEY_MAPPING: list[tuple[str, str]] = [
    # Anthropic (via langchain-anthropic, also Bedrock-Anthropic)
    ("input_tokens", "input"),
    ("output_tokens", "output"),
    # OpenAI / ChatBedrock (non-Converse API)
    ("prompt_tokens", "input"),
    ("completion_tokens", "output"),
    # Generic
    ("total_tokens", "total"),
    # Google Vertex AI
    ("prompt_token_count", "input"),
    ("candidates_token_count", "output"),
    ("total_token_count", "total"),
    # AWS Bedrock (CloudWatch format)
    ("inputTokenCount", "input"),
    ("outputTokenCount", "output"),
    ("totalTokenCount", "total"),
    # IBM watsonx (langchain-ibm)
    ("input_token_count", "input"),
    ("generated_token_count", "output"),
]


def normalize_usage(raw_usage: Any) -> Optional[dict[str, int]]:
    """
    将各厂商的 token 用量统一为 {input, output, total}。

    参考 Langfuse CallbackHandler._parse_usage_model()

    Args:
        raw_usage: 原始 usage 数据，可以是 dict、pydantic model 或其他对象

    Returns:
        标准化的 {input: int, output: int, total: int}，若无法解析返回 None
    """
    if raw_usage is None:
        return None

    # 转为 dict
    usage: dict
    if isinstance(raw_usage, dict):
        usage = raw_usage.copy()
    elif hasattr(raw_usage, "__dict__"):
        usage = {k: v for k, v in raw_usage.__dict__.items() if not k.startswith("_")}
    elif hasattr(raw_usage, "model_dump"):
        try:
            usage = raw_usage.model_dump()
        except Exception:
            return None
    else:
        return None

    if not usage:
        return None

    # 检测是否是标准 OpenAI 格式（直接返回，不做转换）
    openai_keys_full = {
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_tokens_details",
        "completion_tokens_details",
    }
    openai_keys_basic = {"prompt_tokens", "completion_tokens", "total_tokens"}
    if set(usage.keys()) == openai_keys_full or set(usage.keys()) == openai_keys_basic:
        return {
            "input": usage.get("prompt_tokens", 0) or 0,
            "output": usage.get("completion_tokens", 0) or 0,
            "total": usage.get("total_tokens", 0) or 0,
        }

    # 按映射表转换
    result: dict[str, int] = {}
    for source_key, target_key in USAGE_KEY_MAPPING:
        if source_key in usage:
            value = usage.pop(source_key)
            # Bedrock 流式返回可能是 list
            if isinstance(value, list):
                value = sum(v for v in value if isinstance(v, (int, float)))
            if isinstance(value, (int, float)):
                result[target_key] = int(value)

    # 确保 total 存在
    if "total" not in result and "input" in result and "output" in result:
        result["total"] = result["input"] + result["output"]

    # 只保留有效整数值
    result = {k: v for k, v in result.items() if isinstance(v, int) and v >= 0}

    return result if result else None


def extract_usage_from_output(output: Any) -> Optional[dict[str, int]]:
    """
    从 LangChain LLM output 中多源提取 token usage。

    参考 Langfuse CallbackHandler._parse_usage()，按优先级尝试多个源：
    1. output.usage_metadata (langchain_core >= 0.2, 最直接)
    2. output.response_metadata["token_usage"] (OpenAI)
    3. output.response_metadata["usage"] (Bedrock-Anthropic)
    4. output.response_metadata["amazon-bedrock-invocationMetrics"] (Bedrock-Titan)
    5. output.response_metadata["usage_metadata"] (legacy)

    Args:
        output: LLM 输出对象 (通常是 AIMessage 或 ChatGeneration)

    Returns:
        标准化的 token 用量，或 None
    """
    if output is None:
        return None

    raw_usage = None

    # 1. output.usage_metadata (langchain_core >= 0.2, most direct)
    if hasattr(output, "usage_metadata") and output.usage_metadata:
        raw_usage = output.usage_metadata

    # 2-5. response_metadata 内的各种位置
    if raw_usage is None and hasattr(output, "response_metadata"):
        rm = output.response_metadata
        if isinstance(rm, dict):
            # 2. token_usage (OpenAI via langchain-openai)
            raw_usage = rm.get("token_usage")
            # 3. usage (Bedrock-Anthropic)
            if raw_usage is None:
                raw_usage = rm.get("usage")
            # 4. amazon-bedrock-invocationMetrics (Bedrock-Titan)
            if raw_usage is None:
                raw_usage = rm.get("amazon-bedrock-invocationMetrics")
            # 5. usage_metadata (legacy fallback)
            if raw_usage is None:
                raw_usage = rm.get("usage_metadata")

    if raw_usage is None:
        return None

    return normalize_usage(raw_usage)


def extract_usage_from_llm_result(response: Any) -> Optional[dict[str, int]]:
    """
    从 LLMResult 对象提取 token usage。

    Args:
        response: LLMResult 对象 (on_llm_end 的 response 参数)

    Returns:
        标准化的 token 用量，或 None
    """
    if response is None:
        return None

    raw_usage = None

    # 从 llm_output 中提取
    llm_output = getattr(response, "llm_output", None)
    if isinstance(llm_output, dict):
        raw_usage = llm_output.get("token_usage") or llm_output.get("usage")

    # 从 generations 中提取
    if raw_usage is None:
        generations = getattr(response, "generations", None)
        if generations and len(generations) > 0:
            gen_list = generations[0] if isinstance(generations[0], list) else generations
            if gen_list and len(gen_list) > 0:
                gen = gen_list[0]
                # ChatGeneration.message
                msg = getattr(gen, "message", None)
                if msg:
                    return extract_usage_from_output(msg)
                # Generation.generation_info
                gen_info = getattr(gen, "generation_info", None)
                if isinstance(gen_info, dict):
                    raw_usage = gen_info.get("usage_metadata") or gen_info.get("usage")

    if raw_usage is None:
        return None

    return normalize_usage(raw_usage)
