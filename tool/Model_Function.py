
from openai import OpenAI
#from zai import ZhipuAiClient
from . import tools

import os
import json
from datetime import datetime
from openai import OpenAI
import csv                          #搞csv的
from openpyxl import load_workbook   #搞excel的
import base64
from docx import Document
import sys
from dotenv import load_dotenv   #加载env文件
from . import Compress_mudel         #手搓的py文件，记忆压缩模块
import pandas as pd

#路径区(start)
base_path = os.path.dirname(os.path.abspath(__file__))
#路径区(stop)
"""
#GLM的文档暂时还没有看太明白过一段时间再做
def GLM_Core(user_input):
    base_path = os.path.dirname(os.path.abspath(__file__))
    client = ZhipuAiClient(api_key="YOUR_API_KEY")
    response = client.chat.completions.create(
            {
    "model": "glm-5.3",
    "thinking": { "type": "enabled" },
    "reasoning_effort": "max"
    },
        #model 选项 glm-5.3 glm-5.3-flash
        messages=[
            {
                "role": "system",
                "content": "您是一个有用的AI助手。"
            },
            {
                "role": "user",
                "content": "您好，请介绍一下自己。"
            }
        ],
        temperature=0.6
        #(temperature你调得越高，模型越“放飞自我”；调得越低，模型越“照本宣科”)
    )
    print(response.choices[0].message.content)
"""
"""
deepseek2.0(第四次调整架构)
"""

#deepseek白模用于在文件损失的时候去修复(仅限于prompt)
def Deepseek_Blank(role):
    client = OpenAI(
        api_key=os.environ.get('DEEPSEEK_API_KEY'),
        base_url="https://api.deepseek.com")

    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": f"帮我生成{role}的prompt,300字左右要贴近角色"},
        ],
        stream=False,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}}
    )
    return response.choices[0].message.content

#Deepseek_Core 主调函数(在这个版本中prompt直接集成进入Core函数)
def Deepseek_Core(user_input,role="Amiya"):
    load_dotenv()
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    #角色prompt及其他设置
    role_dic={
    "Amiya":["deepseek-v4-flash-vision-exp","medium","disabled"],
    "Kal_tsit":["deepseek-v4-pro","high","enabled"],
    "Closure":["deepseek-v4-pro","high","enabled"]
    }

    Prompt_path=os.path.join(base_path,"Prompt",f"{role}.md")
    History_path=os.path.join(base_path,"AI_memory_SQL",f"{role}_memory.md")

    prompt=tools.file_read_write(Prompt_path,"read")
    History=tools.file_read_write(Prompt_path,"read")

    client = OpenAI(api_key=os.environ.get('DEEPSEEK_API_KEY'),base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model=role_dic[role][0],
        messages=[{"role": "system", "content": prompt},{"role": "user", "content": user_input },],
        stream=True,reasoning_effort=role_dic[role][1],
        extra_body={"thinking": {"type": role_dic[role][2]}}
    )
    collected=""
    print("Ai_response:")
    for chunk in response:
        delta=chunk.choices[0].delta.content
        if delta:
            collected+=delta
            print(delta,end="")
    print("\n")
    return collected