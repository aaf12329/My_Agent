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


def Name_list_operation(model,context=None):
    base_path = os.path.dirname(os.path.abspath(__file__))
    Name_list_path=os.path.join(base_path,"Name_list.txt")
    if model=="read":
        with open(Name_list_path,"r",encoding="utf-8") as f:
            Names=f.read()
        return Names
    if model=="write":
        print(f"写入内容:{context}")
        with open(Name_list_path,"w",encoding="utf-8") as f:
            f.write(context)
        

#文件完整性检查(调用前文Name_list_operation函数读取name_list)
#先检查AI记忆与AI_prompt完整性
#具体过程先读取Name_list.txt返回的切断然后丢尽循环里面迭代么一轮迭代去扫描一个role的prompt与memory
def file_detect():
    from Model_Function import Deepseek_Blank
    base_path=os.path.dirname(os.path.abspath(__file__))
    Name=Name_list_operation(model="read")
    Name_list=Name.split("\n")
    print(f"Name_list:{Name_list}")
    for role in Name_list:
        Memory_path=os.path.join(base_path,"AI_memory_SQL",f"{role}_memory.md")
        Prompt_path=os.path.join(base_path,"Prompt",f"{role}.md")
        if os.path.exists(Memory_path):
            print(f"{Memory_path}文件路径存在")
        else:
            with open(Memory_path,"w",encoding="utf-8") as f:
                f.write("")
            print(f"{Memory_path}路径不存在文件已建立")

        if os.path.exists(Prompt_path):
            print(f"{Prompt_path}路径存在")
        else:
            with open(Prompt_path,"w",encoding="utf-8") as f:
                f.write(Deepseek_Blank(role))
            print(f"{Prompt_path}路径不存在文件已建立")
    #AI_Memory与Prompt检测到这里结束接下来是检查用户记忆的json(.csv不搞了换成SQL)
    print("用户数据自检部分")
    Chat_History_path=os.path.join(base_path,"User_Memory","Chat_History.json")
    if os.path.exists(Chat_History_path):
        print(f"{Chat_History_path}路径存在")
    else:
        with open(Chat_History_path, "w", encoding="utf-8") as f:
            json.dump({}, f)
        print(f"{Chat_History_path}路径不存在文件已建立")


#文件读写操作函数仅用于文件读写并不判定文件是否存在，读写范围覆盖AI记忆，用户记忆，json动态加载记忆(在中控调用部分用)
def file_read_write(file_path,mode,role=None,content=None):
    if mode == "write":
        if file_path.endswith(".json"):
            if os.path.getsize(file_path)==0:
                data = []
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data.append({
                "role": role,
                "content": content,
                "time": f"{datetime.now()}"
            })
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now()}  {role}:{content}\n")
    elif mode == "read":
        with open(file_path,"r",encoding="utf-8") as f:
            return f.read()
    else:
        print("mode error: 请使用'read'或'write'")


    

#输入逻辑
def U_Input():
    user_input = input(f"{datetime.now()}  用户输入:")
    if user_input == "exit()":
        print("程序正常退出")
        sys.exit(0)
    if user_input.startswith("Name list operation"):
        model=input("模式:delete or write:")

        if model=="write":
            Name=Name_list_operation(model="read")
            Name_list=Name.split("\n")

            Name=""          #Name掷空等待再次用于写入.txt

            Name_append=input("输入角色:")
            Name_list.append(Name_append)
            for role in Name_list:
                Name=Name+f"{role}\n"
            print(Name)
        elif model=="delete":
            Name=Name_list_operation(model="read")
            Name_list=Name.split("\n")

            Name=""          #Name掷空等待再次用于写入.txt
            Name_append=input("输入角色")
            Name_list.remove(Name_append)
            for role in Name_list:
                Name=Name+f"{role}\n"
            print(Name)
        Name_list_operation(model="write",context=Name)
        print("操作完成，自检开始")
        file_detect()