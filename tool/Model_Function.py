"""
Model_Function.py —— 模型调用层(纯函数:文本进,文本出,不碰任何文件)

解耦规范:
- 本模块不 import tools / Store / Compress_mudel,需要什么文本由调用方(main)传进来
- key 一律从 .env 读,严禁硬编码
- 三个 Core 同构,想换厂商只换函数名

函数结构:
├─ Deepseek_Core(user_input, prompt, model, reasoning_effort, thinking)   DeepSeek 适配
├─ GLM_Core(user_input, prompt, model, thinking)                          智谱 GLM 适配(OpenAI兼容端点)
├─ GPT_Core(user_input, prompt, model, reasoning_effort)                  OpenAI GPT 适配
└─ _stream_print(response)       内部共用:消费流式响应,边打印边收集,返回完整文本

.env 需要的 key(用到谁配谁):
    DEEPSEEK_API_KEY=sk-xxx
    ZHIPU_API_KEY=xxx        (智谱,GLM)
    OPENAI_API_KEY=sk-xxx    (GPT)

已退役:Deepseek_Blank(旧自检生成角色prompt用)、role_dic(多角色配置)、
       GLM_Core 的注释草稿(本版已实现)
"""
import os
from dotenv import load_dotenv
from openai import OpenAI


# ==================== DeepSeek 适配 ====================
def Deepseek_Core(user_input, prompt="", model="deepseek-flash",
                  reasoning_effort="high", thinking=True):
    """DeepSeek 调用。prompt 为空则不带 system(纯对话)"""
    load_dotenv()
    client = OpenAI(
        api_key=os.environ.get('DEEPSEEK_API_KEY'),
        base_url="https://api.deepseek.com")

    messages = []
    if prompt:
        messages.append({"role": "system", "content": prompt})
    messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        reasoning_effort=reasoning_effort,
        extra_body={"thinking": {"type": "enabled" if thinking else "disabled"}}
    )
    return _stream_print(response)


# ==================== 智谱 GLM 适配 ====================
def GLM_Core(user_input, prompt="", model="glm-5.3", thinking=True):
    """智谱 GLM 调用。走官方 OpenAI 兼容端点,不用额外装 zhipuai SDK"""
    load_dotenv()
    client = OpenAI(
        api_key=os.environ.get('ZHIPU_API_KEY'),
        base_url="https://open.bigmodel.cn/api/paas/v4")

    messages = []
    if prompt:
        messages.append({"role": "system", "content": prompt})
    messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        extra_body={"thinking": {"type": "enabled" if thinking else "disabled"}}
    )
    return _stream_print(response)


# ==================== OpenAI GPT 适配 ====================
def GPT_Core(user_input, prompt="", model="gpt-5", reasoning_effort=None):
    """OpenAI GPT 调用。reasoning_effort 不传就不带这个参数(非推理模型会报错)"""
    load_dotenv()
    client = OpenAI(
        api_key=os.environ.get('OPENAI_API_KEY'),
        base_url="https://api.openai.com/v1")

    messages = []
    if prompt:
        messages.append({"role": "system", "content": prompt})
    messages.append({"role": "user", "content": user_input})

    extra = {}
    if reasoning_effort:
        extra["reasoning_effort"] = reasoning_effort

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        **extra
    )
    return _stream_print(response)


# ==================== 内部共用 ====================
def _stream_print(response):
    """内部共用:消费流式响应,边打印边收集,返回完整文本(三家格式一致,一份代码)"""
    collected = ""
    print("Ai_response:")
    for chunk in response:
        if not chunk.choices:            # 最后一个 chunk 只带 usage,choices 是空的
            continue
        delta = chunk.choices[0].delta
        if delta and delta.content:
            collected += delta.content
            print(delta.content, end="")
    print("\n")
    return collected


# ==================== 自测(直接运行本文件才会执行) ====================
if __name__ == "__main__":
    load_dotenv()
    if os.environ.get('DEEPSEEK_API_KEY'):
        Deepseek_Core("用一句话介绍你自己")
    else:
        print("[自测] .env 里没有 DEEPSEEK_API_KEY,跳过 DeepSeek")
    if os.environ.get('ZHIPU_API_KEY'):
        GLM_Core("用一句话介绍你自己", prompt="回答必须带一个表情符号")
    else:
        print("[自测] .env 里没有 ZHIPU_API_KEY,跳过 GLM")
    if os.environ.get('OPENAI_API_KEY'):
        GPT_Core("用一句话介绍你自己")
    else:
        print("[自测] .env 里没有 OPENAI_API_KEY,跳过 GPT")
