import os
import json

# --- 配置部分 ---
ROOT_DIR = "/workspace/code_dir/benchmark-experiments/rebuild_prompts/power_benchmark" # 数据集的根目录名称

# 1. 路径映射配置 (关键部分)
# 格式: "原始路径前缀": "你本地的实际路径前缀"
# 脚本会将 value 中的 key 替换为 value
PATH_MAPPING = {
    "/workspace/code_dir/benchmark/": "/workspace/code_dir/benchmark-experiments/rebuild_prompts/power_benchmark/",
    "/workspace/data_dir/": "/workspace/code_dir/benchmark-experiments/rebuild_prompts/power_benchmark/data_dir/" # 假设还有其他路径需要映射，可在此添加
}

# 2. Prompt 模板配置
TEMPLATE_EN = """You are a senior power inspection expert with 20 years of experience. You possess keen visual recognition capabilities and are well-versed in the various components of transmission and distribution lines and substation equipment (such as insulators, towers, fittings, transformers, etc.) as well as their common defects (such as breakage, rust, foreign objects, bird nests, vegetation encroachment, etc.). Please carefully analyze the uploaded power inspection image and answer the following multiple-choice question. You must output only one of the options (A), (B), (C), (D) without providing any explanation.For example, output: (A).

Question: {}
Choices:
{}"""

TEMPLATE_ZH = """你是一位拥有20年经验的资深电力巡检专家。你具备极敏锐的视觉识别能力，熟悉输配电线路、变电站设备的各种组件（如绝缘子、杆塔、金具、变压器等）及其常见缺陷（如破损、锈蚀、异物悬挂、鸟巢、植被入侵等）。
请仔细分析上传的电力巡检图像，并回答随后提出的单项选择题。你只用输出(A),(B),(C),(D)选项中的一个，不用对结果做任何解释。比如，输出：(A).

问题：{}
选项：
{}"""

def format_choices(choices_list):
    formatted = []
    for idx, item in enumerate(choices_list):
        label = chr(65 + idx)
        formatted.append(f"({label}) {item}")
    return "\n".join(formatted)

def fix_path_string(path_str):
    """
    检查字符串是否包含需要映射的旧路径，如果包含则替换
    """
    if not path_str or not isinstance(path_str, str):
        return path_str
        
    for old_prefix, new_prefix in PATH_MAPPING.items():
        if path_str.startswith(old_prefix):
            # 替换路径
            return path_str.replace(old_prefix, new_prefix)
    
    return path_str

def update_json_paths(data):
    """
    遍历 JSON 字典，修复所有可能的路径字段
    """
    # 需要检查的字段列表
    path_fields = ['image1', 'image2', 'image3', 'image4', 'image5']
    
    # 1. 修复 imageX 字段 (字符串)
    for field in path_fields:
        if field in data:
            data[field] = fix_path_string(data[field])
            
    # 2. 修复 source 字段 (列表)
    if 'source' in data and isinstance(data['source'], list):
        data['source'] = [fix_path_string(item) for item in data['source']]
        
    return data

def process_files(root_dir):
    count = 0
    updated_paths_count = 0
    print(f"Checking directory: {os.path.abspath(root_dir)}")
    print(f"Applying path mappings: {json.dumps(PATH_MAPPING, indent=2, ensure_ascii=False)}\n")
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if not filename.endswith('.json'):
                continue
                
            file_path = os.path.join(dirpath, filename)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"[Error] Failed to read {file_path}: {e}")
                continue
            
            # --- 步骤 1: 修复路径 ---
            # 保留原始数据的快照用于对比（可选）
            original_image_path = data.get('image1', '')
            
            data = update_json_paths(data)
            
            # 简单的日志：如果路径发生了变化
            if original_image_path != data.get('image1', ''):
                updated_paths_count += 1

            # --- 步骤 2: 更新 Prompt ---
            question = data.get('question', '')
            choices = data.get('choices', [])
            choices_str = format_choices(choices)
            
            new_prompt = ""
            if filename.endswith('_en.json'):
                new_prompt = TEMPLATE_EN.format(question, choices_str)
            elif filename.endswith('_zh.json'):
                new_prompt = TEMPLATE_ZH.format(question, choices_str)
            else:
                continue
            
            data['prompt'] = new_prompt
            
            # --- 步骤 3: 保存文件 ---
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                count += 1
            except Exception as e:
                print(f"[Error] Failed to write {file_path}: {e}")

    print(f"\nCompleted!")
    print(f"Processed {count} files.")
    print(f"Fixed paths in {updated_paths_count} files (based on image1 check).")

if __name__ == "__main__":
    if os.path.exists(ROOT_DIR):
        process_files(ROOT_DIR)
    else:
        print(f"Directory '{ROOT_DIR}' not found.")