import os
from openai import OpenAI

# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')

client = OpenAI(
    base_url='https://ark.cn-beijing.volces.com/api/v3',
    api_key=api_key,
)

# 创建一个对话请求
response = client.responses.create(
    # 替换为模型的Model ID
    model="doubao-seed-2-0-lite-260215",
    input="你好呀。"
)

print(response)
