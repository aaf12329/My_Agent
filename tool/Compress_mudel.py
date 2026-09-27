"""
Compress_mudel.py —— 记忆压缩模块(原样保留,待改造)

职责:长期记忆(.md)超过阈值(1.5MB)时,调 DeepSeek 把整篇记忆摘要到约5000字并写回

函数结构:
├─ Liberary_Read_Or_Write(model, path, content)   文本读写(与 tools 的读写功能重复,待收敛)
├─ Ai_compress(content, role)                     调 DeepSeek 执行压缩,返回摘要文本
├─ Compress_control(role)                         读记忆 → 压缩 → 写回,一条龙
├─ Memory_Scale_detect(role)                      阈值检测:超 1.5MB 触发 Compress_control
└─ Compress_mudel_link_test()                     连通性自检打印

已知问题(改造清单,本次只加注释不动逻辑):
1. 路径自己拼 tool/AI_memory_SQL/{role}_memory.md —— 旧结构已封存,未走 Store,一调即 FileNotFoundError
2. 第45行调用 Compress_control(file_path=..., role=...) 与其签名 Compress_control(role) 不符,触发即 TypeError
3. Ai_compress 的 system prompt 带 {role} 身份视角 —— 多角色遗产
4. model="deepseek-v4-pro" 写死在函数里,没走参数
5. 当前包内没有任何调用方(待接入:将来可包装成模型可调的 compress_memory 工具)
"""
import os
from openai import OpenAI
from dotenv import load_dotenv

def Liberary_Read_Or_Write(model,path,content=None):
    """文本读写:model='read' 返回内容;model='write' 覆盖写入(无效 model 静默返回 None)"""
    if model=="read":
        with open(path,"r",encoding="utf-8") as f:
            content=f.read()
            return content
    if model=="write":
        with open(path,"w",encoding="utf-8") as f:
            f.write(f"{content}")

def Ai_compress (content,role):
    """调 DeepSeek 把整篇记忆压缩到约5000字。role 会写进 system prompt(多角色遗产,待去)"""
    print("Compress_mudel link Ok,start Compress")
    client = OpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[{"role": "system", "content": f"请以{role}的身份视角进行记忆压缩，压缩到5000字左右"},{"role": "user", "content": content},],
        stream=False,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}}
    )
    result=response.choices[0].message.content
    print("Compress_finish")
    return result

def Compress_control(role):
    """读记忆 → 压缩 → 写回,一条龙。已知问题:路径未走 Store,指向已封存的旧结构"""
    base_path = os.path.dirname(os.path.abspath(__file__))
    file_path=os.path.join(base_path,"AI_memory_SQL",f"{role}_memory.md")
    load_dotenv()
    print("Compress_mudel Engage")
    text=Liberary_Read_Or_Write(model="read",path=file_path)
    result=Ai_compress(text,role=role)
    Liberary_Read_Or_Write(model="write",path=file_path,content=result)
    print("记忆压缩完成")

def Memory_Scale_detect(role):
    """超过 1.5MB 触发压缩。已知问题:下一行调用签名不符,真触发就崩(见改造清单第2条)"""
    base_path = os.path.dirname(os.path.abspath(__file__))
    AI_memory_path=os.path.join(base_path,"AI_memory_SQL",f"{role}_memory.md")
    size_bytes = os.path.getsize(AI_memory_path)
    if size_bytes/(1024*1024) >=1.5:
        Compress_control(file_path=AI_memory_path,role=role)   # ← 已知bug:签名不符,触发即 TypeError

def Compress_mudel_link_test():
    """连通性自检"""
    print("可以接入Compress模块")