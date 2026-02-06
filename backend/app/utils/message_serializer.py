"""
LangChain Message Serializer

参考 Langfuse _convert_message_to_dict() 实现。
将 LangChain BaseMessage 对象序列化为可存储的 dict 格式。
"""

from typing import Any

from loguru import logger


def serialize_message(msg: Any) -> dict:
    """
    将 LangChain BaseMessage 转换为可 JSON 序列化的 dict。

    参考 Langfuse CallbackHandler._convert_message_to_dict()

    Args:
        msg: LangChain BaseMessage 实例或类似对象

    Returns:
        {"role": str, "content": str, ...} 格式的 dict
    """
    # 已经是 dict，直接返回
    if isinstance(msg, dict):
        return msg

    # 获取 content
    content = _extract_content(msg)

    # 按类型判断 role
    class_name = type(msg).__name__

    if class_name == "HumanMessage" or class_name == "HumanMessageChunk":
        result: dict[str, Any] = {"role": "user", "content": content}
    elif class_name == "AIMessage" or class_name == "AIMessageChunk":
        result = {"role": "assistant", "content": content}
        # 保留 tool_calls
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            result["tool_calls"] = _serialize_tool_calls(tool_calls)
        # 保留 additional_kwargs 中的重要信息
        additional = getattr(msg, "additional_kwargs", None)
        if additional and isinstance(additional, dict):
            if "function_call" in additional:
                result["function_call"] = additional["function_call"]
            if "tool_calls" in additional and "tool_calls" not in result:
                result["tool_calls"] = additional["tool_calls"]
    elif class_name == "SystemMessage" or class_name == "SystemMessageChunk":
        result = {"role": "system", "content": content}
    elif class_name == "ToolMessage" or class_name == "ToolMessageChunk":
        result = {"role": "tool", "content": content}
        tool_call_id = getattr(msg, "tool_call_id", None)
        if tool_call_id:
            result["tool_call_id"] = tool_call_id
    elif class_name == "FunctionMessage" or class_name == "FunctionMessageChunk":
        result = {"role": "function", "content": content}
        name = getattr(msg, "name", None)
        if name:
            result["name"] = name
    elif class_name == "ChatMessage" or class_name == "ChatMessageChunk":
        role = getattr(msg, "role", "unknown")
        result = {"role": role, "content": content}
    else:
        # 兜底：尝试通用提取
        role = getattr(msg, "type", "unknown")
        result = {"role": role, "content": content}

    # 保留 name（如果有）
    name = getattr(msg, "name", None)
    if name and "name" not in result:
        result["name"] = name

    return result


def serialize_messages(messages: Any) -> list[dict]:
    """
    序列化消息列表。支持嵌套列表（LangChain 有时会传递 list[list[BaseMessage]]）。

    Args:
        messages: BaseMessage 列表或嵌套列表

    Returns:
        扁平化的 dict 列表
    """
    if not messages:
        return []

    result = []
    for msg in messages:
        if isinstance(msg, list):
            # 处理嵌套列表
            for sub_msg in msg:
                result.append(serialize_message(sub_msg))
        else:
            result.append(serialize_message(msg))
    return result


def _extract_content(msg: Any) -> Any:
    """提取消息内容，处理多模态内容"""
    content = getattr(msg, "content", None)
    if content is None:
        return str(msg)

    # 多模态内容可能是 list（如包含图片的消息）
    if isinstance(content, list):
        # 保持原始结构，但确保可序列化
        serialized: list[dict[str, Any]] = []
        for part in content:
            if isinstance(part, dict):
                serialized.append(part)
            elif isinstance(part, str):
                serialized.append({"type": "text", "text": part})
            else:
                # 兜底：保持元素类型一致（dict），避免 mypy 类型不匹配
                serialized.append({"type": "unknown", "raw": str(part)})
        return serialized

    return content


def _serialize_tool_calls(tool_calls: list) -> list[dict]:
    """序列化 tool_calls 列表"""
    result = []
    for tc in tool_calls:
        if isinstance(tc, dict):
            result.append(tc)
        elif hasattr(tc, "model_dump"):
            try:
                result.append(tc.model_dump())
            except Exception:
                result.append({"name": getattr(tc, "name", ""), "args": getattr(tc, "args", {})})
        elif hasattr(tc, "__dict__"):
            result.append({k: v for k, v in tc.__dict__.items() if not k.startswith("_")})
        else:
            # 兜底：返回 dict，保持元素类型一致
            result.append({"type": "raw", "raw": str(tc)})
    return result


def truncate_data(data: Any, max_length: int = 10000) -> Any:
    """
    截断数据到指定长度，记录 warning。

    Args:
        data: 要截断的数据
        max_length: 最大字符数

    Returns:
        截断后的数据
    """
    if data is None:
        return None

    serialized = str(data)
    if len(serialized) <= max_length:
        return data

    logger.warning(f"Data truncated from {len(serialized)} to {max_length} chars (type={type(data).__name__})")

    if isinstance(data, str):
        return data[:max_length] + "... [truncated]"
    elif isinstance(data, dict):
        # 逐个截断 value
        result = {}
        current_len = 0
        for k, v in data.items():
            v_str = str(v)
            if current_len + len(v_str) > max_length:
                remaining = max(0, max_length - current_len)
                result[k] = v_str[:remaining] + "... [truncated]"
                break
            result[k] = v
            current_len += len(v_str)
        return result
    else:
        return serialized[:max_length] + "... [truncated]"
