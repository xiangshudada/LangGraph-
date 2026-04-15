import os

from langchain.chat_models import init_chat_model

from dotenv import load_dotenv  # 导入工具
load_dotenv()

qwen = init_chat_model(
    model="qwen-plus",  # 千问模型名
    model_provider="openai",  # 关键：指定为openai兼容
    temperature=0.5,
    timeout=30,
    max_tokens=1000,
    api_key="sk-9ae18d6b0bc04e88a7f5777450ab632a",  # 必须写
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",  # 必须写
)
