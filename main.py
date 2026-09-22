import Model_Function
import tools
import Compress_mudel

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
import Compress_mudel         #手搓的py文件，记忆压缩模块
import pandas as pd

"""
def Control():
    base_path = os.path.dirname(os.path.abspath(__file__))

    role_list=["Amiya","Kal_tsit","Closure"]
    user_input,role=tools.U_Input()

    Chat_History_base_path=os.path.join(base_path,"AI_memory_SQL",)
    Chat_History_path=os.path.join(Chat_History_base_path,f"{role}_memory.md")

    Chat_History=file_read_write(file_path=Chat_History_path,model="read")

    result=Model_Function.Deepseek_Core(Chat_History+user_input,role=role)
    if result.endswith("@Kal_tsit"):
        Model_Function.Deepseek_Core(user_input,role=role)
    if result.endswith("@Closure"):
        Model_Function.Deepseek_Core(user_input,role=role)
"""
if __name__ == "__main__":
    tools.file_detect()
    tools.U_Input()
