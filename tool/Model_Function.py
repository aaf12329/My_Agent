"""
Model_Function.py —— 模型调用层(纯函数:messages 进,dict 出,不碰任何文件)

解耦规范:
- 本模块不 import tools / Store / Compress_mudel,需要什么文本由调用方(main)传进来
- key 一律从 .env 读,严禁硬编码

返回值契约(重要):
    所有 Core / *_messages 统一返回 dict:
        {"content":   str,          回答文本
         "reasoning": str,          思考过程(开 thinking 才有内容,默认不打印)
         "usage":     usage|None}   token 账单(含 DeepSeek 缓存命中数)
    旧版"返回字符串"契约已废弃(换约时无调用方,零成本)

双层入口:
    *_messages(messages, ...)          低层:收现成 messages 列表,原样透传(Agent 循环用)
    *_Core(user_input, prompt, history) 便捷层:拼装糖,日常聊天用

.env 需要的 key(用到谁配谁):
    DEEPSEEK_API_KEY=sk-xxx
    ZHIPU_API_KEY=xxx        (智谱,GLM)
    OPENAI_API_KEY=sk-xxx    (GPT)

函数结构:
├─ Deepseek_messages / GLM_messages / GPT_messages     低层入口(重试护甲在这里包)
├─ Deepseek_Core / GLM_Core / GPT_Core                 便捷层(history=干净 [{"role","content"}],不带 time)
├─ _create_with_retry(make_call)                       内部:指数退避+抖动,只救暂时性错误
├─ _stream_consume(response, show_thinking)            内部:消费流,三路收集,返回 dict
└─ _print_usage(usage)                                 内部:打印 token 账单与缓存命中率

已退役:Deepseek_Blank、role_dic、GLM_Core 注释草稿、旧版"返回字符串"契约
"""
import os
import time
import random
from dotenv import load_dotenv
from openai import (OpenAI,
                    RateLimitError, APITimeoutError,
                    APIConnectionError, InternalServerError)

# 只有"暂时性错误"值得重试;401(key错)/400(参数错)重试一万次也一样,直接炸出来暴露问题
_RETRYABLE = (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)


# ==================== DeepSeek 适配 ====================
def Deepseek_messages(messages, model="deepseek-flash",
                      reasoning_effort="high", thinking=True, show_thinking=False):
    """低层入口:收现成 messages 列表,原样透传"""
    load_dotenv()
    client = OpenAI(
        api_key=os.environ.get('DEEPSEEK_API_KEY'),
        base_url="https://api.deepseek.com")

    response = _create_with_retry(lambda: client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        reasoning_effort=reasoning_effort,
        stream_options={"include_usage": True},          # 不主动要,流里就没有 usage
        extra_body={"thinking": {"type": "enabled" if thinking else "disabled"}}
    ))
    return _stream_consume(response, show_thinking)


def Deepseek_Core(user_input, prompt="", history=None, model="deepseek-flash",
                  reasoning_effort="high", thinking=True, show_thinking=False):
    """便捷层:拼 [system?] + [history?] + [user] 后转调低层"""
    messages = []
    if prompt:
        messages.append({"role": "system", "content": prompt})
    if history:
        messages.extend(history)                          # 必须是干净 [{"role","content"}],不带 time
    messages.append({"role": "user", "content": user_input})
    return Deepseek_messages(messages, model=model, reasoning_effort=reasoning_effort,
                             thinking=thinking, show_thinking=show_thinking)


# ==================== 智谱 GLM 适配 ====================
def GLM_messages(messages, model="glm-5.3", thinking=True, show_thinking=False):
    """低层入口:走智谱官方 OpenAI 兼容端点,不用额外装 zhipuai SDK"""
    load_dotenv()
    client = OpenAI(
        api_key=os.environ.get('ZHIPU_API_KEY'),
        base_url="https://open.bigmodel.cn/api/paas/v4")

    response = _create_with_retry(lambda: client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        stream_options={"include_usage": True},          # 若该端点不认这个参数,删掉本行即可
        extra_body={"thinking": {"type": "enabled" if thinking else "disabled"}}
    ))
    return _stream_consume(response, show_thinking)


def GLM_Core(user_input, prompt="", history=None, model="glm-5.3",
             thinking=True, show_thinking=False):
    """便捷层:拼装后转调 GLM_messages"""
    messages = []
    if prompt:
        messages.append({"role": "system", "content": prompt})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_input})
    return GLM_messages(messages, model=model, thinking=thinking, show_thinking=show_thinking)


# ==================== OpenAI GPT 适配 ====================
def GPT_messages(messages, model="gpt-5", reasoning_effort=None, show_thinking=False):
    """低层入口。reasoning_effort 不传就不带这个参数(非推理模型会报错)"""
    load_dotenv()
    client = OpenAI(
        api_key=os.environ.get('OPENAI_API_KEY'),
        base_url="https://api.openai.com/v1")

    extra = {}
    if reasoning_effort:
        extra["reasoning_effort"] = reasoning_effort

    response = _create_with_retry(lambda: client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        stream_options={"include_usage": True},
        **extra
    ))
    return _stream_consume(response, show_thinking)


def GPT_Core(user_input, prompt="", history=None, model="gpt-5",
             reasoning_effort=None, show_thinking=False):
    """便捷层:拼装后转调 GPT_messages"""
    messages = []
    if prompt:
        messages.append({"role": "system", "content": prompt})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_input})
    return GPT_messages(messages, model=model, reasoning_effort=reasoning_effort,
                        show_thinking=show_thinking)


# ==================== 内部共用 ====================
def _create_with_retry(make_call, retries=3):
    """指数退避+抖动,只包 create 调用;流中途断掉不救,让异常炸出来"""
    for attempt in range(retries + 1):
        try:
            return make_call()
        except _RETRYABLE as e:
            if attempt == retries:
                raise
            wait = 2 ** attempt + random.random()        # 1→2→4 秒,抖动防共振
            print(f"[Model] {type(e).__name__},{wait:.1f}s 后重试({attempt + 1}/{retries})")
            time.sleep(wait)


def _stream_consume(response, show_thinking=False):
    """内部:消费流式响应,三路收集,返回 dict

    DeepSeek 流的时序:reasoning_content 分片先到 → content 分片后到 → 空 choices 收尾(usage 藏这)
    """
    content_buf = ""
    reasoning_buf = ""
    usage = None
    print("Ai_response:")
    for chunk in response:
        if not chunk.choices:                             # 收尾 chunk:choices 空,usage 藏在这
            usage = getattr(chunk, "usage", None)
            continue
        delta = chunk.choices[0].delta
        # getattr 而非直接点:GPT/非思考模型没有 reasoning_content 字段
        piece = getattr(delta, "reasoning_content", None)
        if piece:
            reasoning_buf += piece
            if show_thinking:
                print(piece, end="")
            continue
        if delta and delta.content:
            content_buf += delta.content
            print(delta.content, end="")
    print("\n")
    _print_usage(usage)
    return {"content": content_buf, "reasoning": reasoning_buf, "usage": usage}


def _print_usage(usage):
    """内部:打印 token 账单与缓存命中率(前缀稳定的架构设计,成绩单就看这个百分比)"""
    if not usage:
        return
    total_in = usage.prompt_tokens
    hit = getattr(usage, "prompt_cache_hit_tokens", 0)    # DeepSeek 特有,别家没有就当 0
    rate = f"{hit / total_in * 100:.0f}%" if total_in else "-"
    # 注意:completion_tokens_details.reasoning_tokens 已含在 completion_tokens 里,别二次相加
    print(f"[usage] 输入{total_in}(缓存命中{hit},{rate}) 输出{usage.completion_tokens} 共{usage.total_tokens}")


# ==================== 自测(直接运行本文件才会执行) ====================
if __name__ == "__main__":
    load_dotenv()
    if os.environ.get('DEEPSEEK_API_KEY'):
        result = Deepseek_Core("用一句话介绍你自己", show_thinking=True)
        print("content:", repr(result["content"]))
        print("reasoning 长度:", len(result["reasoning"]))
        print("usage:", result["usage"] is not None)
    else:
        print("[自测] .env 里没有 DEEPSEEK_API_KEY,跳过 DeepSeek")
    if os.environ.get('ZHIPU_API_KEY'):
        result = GLM_Core("用一句话介绍你自己", prompt="回答必须带一个表情符号")
        print("content:", repr(result["content"]))
    else:
        print("[自测] .env 里没有 ZHIPU_API_KEY,跳过 GLM")
    if os.environ.get('OPENAI_API_KEY'):
        result = GPT_Core("用一句话介绍你自己")
        print("content:", repr(result["content"]))
    else:
        print("[自测] .env 里没有 OPENAI_API_KEY,跳过 GPT")
