import os
import json

# --- 配置部分 ---
ROOT_DIR = "/workspace/code_dir/benchmark-experiments/task_1_6"  # 数据集的根目录名称

# 英文 Prompt 模板
TEMPLATE_EN = """You are a senior power inspection expert with 20 years of experience. You possess keen visual recognition capabilities and are well-versed in the various components of transmission and distribution lines and substation equipment (such as insulators, towers, fittings, transformers, etc.) as well as their common defects (such as breakage, rust, foreign objects, bird nests, vegetation encroachment, etc.). Please carefully analyze the uploaded power inspection image and answer the following multiple-choice question. You must output only one of the options (A), (B), (C), (D) without providing any explanation.For example, output: (A).

Question: {}
Choices:
{}"""

# 中文 Prompt 模板
TEMPLATE_ZH = """你是一位拥有20年经验的资深电力巡检专家。你具备极敏锐的视觉识别能力，熟悉输配电线路、变电站设备的各种组件（如绝缘子、杆塔、金具、变压器等）及其常见缺陷（如破损、锈蚀、异物悬挂、鸟巢、植被入侵等）。
请仔细分析上传的电力巡检图像，并回答随后提出的单项选择题。你只用输出(A),(B),(C),(D)选项中的一个，不用对结果做任何解释。比如，输出：(A).

问题：{}
选项：
{}"""

def format_choices(choices_list):
    """
    将列表 ['a', 'b', 'c'] 转换为格式化的字符串:
    (A) a
    (B) b
    (C) c
    """
    formatted = []
    for idx, item in enumerate(choices_list):
        label = chr(65 + idx)  # 65 is ASCII for 'A'
        formatted.append(f"({label}) {item}")
    return "\n".join(formatted)

def process_files(root_dir):
    count = 0
    print(f"Checking directory: {os.path.abspath(root_dir)}")
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # 只处理 prompts 文件夹下的 json (根据截图结构推断)
        # 如果所有json都在 prompts 文件夹下，可以保留这个判断，否则可以注释掉
        # if 'prompts' not in dirpath:
        #     continue

        for filename in filenames:
            if not filename.endswith('.json'):
                continue
                
            file_path = os.path.join(dirpath, filename)
            
            # 读取 JSON
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"[Error] Failed to read {file_path}: {e}")
                continue
            
            # 提取关键信息
            question = data.get('question', '')
            choices = data.get('choices', [])
            
            # 格式化选项字符串
            choices_str = format_choices(choices)
            
            # 根据文件名判断语言并生成新 Prompt
            new_prompt = ""
            if filename.endswith('_en.json'):
                new_prompt = TEMPLATE_EN.format(question, choices_str)
            elif filename.endswith('_zh.json'):
                new_prompt = TEMPLATE_ZH.format(question, choices_str)
            else:
                # 如果有其他命名格式，跳过或默认处理
                continue
            
            # 更新数据
            data['prompt'] = new_prompt
            
            # 写回 JSON
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    # ensure_ascii=False 确保中文不被转义为 \uXXXX
                    json.dump(data, f, ensure_ascii=False, indent=4)
                print(f"[Updated] {filename}")
                count += 1
            except Exception as e:
                print(f"[Error] Failed to write {file_path}: {e}")

    print(f"\nCompleted! Processed {count} files.")

if __name__ == "__main__":
    # 建议先备份数据，再运行
    if os.path.exists(ROOT_DIR):
        process_files(ROOT_DIR)
    else:
        print(f"Directory '{ROOT_DIR}' not found. Please run this script in the parent folder of '{ROOT_DIR}'.")