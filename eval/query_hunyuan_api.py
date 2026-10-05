import os
import time
import base64
from openai import OpenAI

# ================= 配置 =================
API_KEY = os.environ.get("HUNYUAN_API_KEY", "")
API_URL = "https://api.hunyuan.cloud.tencent.com/v1"
MODEL_NAME = "hunyuan-large-vision" 
# =======================================

client = OpenAI(
    api_key=API_KEY,
    base_url=API_URL,
)

def encode_image_to_base64(image_path):
    """将本地图片转换为 Base64 格式"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"❌ 读取图片出错: {image_path}, {e}")
        return None

def query_hunyuan_api(image_paths, prompt):
    """
    适配 BLINK 的接口函数
    Args:
        image_paths: 本地图片路径列表 ['path/to/img1.png']
        prompt: 问题文本
    """
    if not API_KEY:
        print("Error: No API Key provided")
        return "(Z)"

    # 1. 构造消息体
    content_list = [{"type": "text", "text": prompt}]
    
    # 2. 处理图片 (支持多图)
    for img_path in image_paths:
        base64_img = encode_image_to_base64(img_path)
        if base64_img is None:
            return "(Z)" # 图片读取失败直接跳过
            
        content_list.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img}"
            }
        })

    # 3. 发送请求 (增加重试机制)
    for attempt in range(1):
        try:
            print(f"🚀 Sending request to {MODEL_NAME} (Attempt {attempt+1})...")
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "user",
                        "content": content_list
                    }
                ],
                temperature=0.0, 
                max_tokens=1000
            )
            
            # 提取回答
            answer = response.choices[0].message.content
            
            # <--- 修改点：防止 API 返回 None 导致后续报错
            if answer is None:
                print("⚠️ API returned None content.")
                answer = "" 
            
            print(f"✅ Hunyuan Response: {answer}")
            return answer

        except Exception as e:
            print(f"⚠️ API 请求失败 (尝试 {attempt+1}/3): {e}")
            time.sleep(2)
            
    return "(Z)" # 失败标记