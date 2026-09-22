import os
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

from sentence_transformers import SentenceTransformer, util

print("正在加载模型（首次会下载约 100MB）...")
model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
print("模型加载完成")

sents = [
    "帮我看看这段代码为什么报错",
    "这个程序跑不起来",
    "今天天气不错",
]
vecs = model.encode(sents)
print("向量形状:", vecs.shape)          # 期望 (3, 512)
print(util.cos_sim(vecs, vecs).numpy().round(3))