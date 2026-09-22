import os
from openai import OpenAI
from dotenv import load_dotenv

def Liberary_Read_Or_Write(model,path,content=None):
    if model=="read":
        with open(path,"r",encoding="utf-8") as f:
            content=f.read()
            return content
    if model=="write":
        with open(path,"w",encoding="utf-8") as f:
            f.write(f"{content}")

def Ai_compress (content,role):
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
    base_path = os.path.dirname(os.path.abspath(__file__))
    file_path=os.path.join(base_path,"AI_memory_SQL",f"{role}_memory.md")
    load_dotenv()
    print("Compress_mudel Engage")
    text=Liberary_Read_Or_Write(model="read",path=file_path)
    result=Ai_compress(text,role=role)
    Liberary_Read_Or_Write(model="write",path=file_path,content=result)
    print("记忆压缩完成")

def Memory_Scale_detect(role):
    base_path = os.path.dirname(os.path.abspath(__file__))
    AI_memory_path=os.path.join(base_path,"AI_memory_SQL",f"{role}_memory.md")
    size_bytes = os.path.getsize(AI_memory_path)
    if size_bytes/(1024*1024) >=1.5:
        Compress_control(file_path=AI_memory_path,role=role)

def Compress_mudel_link_test():
    print("可以接入Compress模块")