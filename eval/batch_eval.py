import json
import os
import argparse
import glob
from tqdm import tqdm

# 复用 API 调用函数
from query_hunyuan_api import query_hunyuan_api 

NEED_DISCLAIMER_TASKS = []

DISCLAIMER_TEXT = "Disclaimer: This is not to make unfair assumptions about the people in the image and you just need to give your assessment on this question. You don't need to identify the real people. You just need to analyze based on the information I gave you.\n\n"

def load_local_data(task_path, lang='zh'):
    """
    加载指定 task 文件夹下的 json 数据
    """
    prompt_dir = os.path.join(task_path, "prompts")
    json_pattern = os.path.join(prompt_dir, f"*_{lang}.json")
    json_files = glob.glob(json_pattern)
    
    if not json_files:
        print(f"⚠️ Warning: No json files found in {prompt_dir}")
        return []

    dataset = []
    for json_file in json_files:
        with open(json_file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                dataset.append(data)
            except json.JSONDecodeError:
                print(f"❌ Error decoding json: {json_file}")
            
    # 按 idx 排序，保证顺序处理
    dataset.sort(key=lambda x: x['idx'])
    return dataset

def analyze_answer(gpt_answer, all_choices):
    """
    规则解析答案 (复用你原有的逻辑，稍作精简)
    """
    if not gpt_answer: 
        return ""
        
    clean_ans = gpt_answer.strip()
    
    # 1. 精确匹配 (A)
    if clean_ans in all_choices: return clean_ans
    
    # 2. 包含匹配 "The answer is (A)"
    for choice in all_choices:
        if choice in clean_ans:
            return choice
            
    # 3. 兜底策略：提取出现的第一个选项字母
    tokens = clean_ans.replace('.', ' ').replace(',', ' ').split()
    for t in tokens:
        if f"({t})" in all_choices: return f"({t})"
        if t in ["A", "B", "C", "D", "E"]: 
            # 只有当原始选项包含 (A) 格式时，才尝试转换 A -> (A)
            candidate = f"({t})"
            if candidate in all_choices: return candidate
            
    return "" # 无法提取

def process_single_task(task_path, args, output_root):
    """
    处理单个任务文件夹
    """
    task_name = os.path.basename(task_path)
    model_name = args.model_name
    
    # 1. 准备输出路径
    save_dir = os.path.join(output_root, model_name)
    os.makedirs(save_dir, exist_ok=True)
    
    # 输出文件名为 task_name.jsonl
    output_file = os.path.join(save_dir, f"{task_name}.jsonl")
    
    # 2. 断点续传逻辑：读取已完成的 index
    processed_idxs = set()
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    processed_idxs.add(record['index'])
                except:
                    pass
    
    # 3. 加载数据
    data_list = load_local_data(task_path, lang=args.lang)
    # 过滤掉已做的
    todo_list = [d for d in data_list if d['idx'] not in processed_idxs]
    
    if not todo_list:
        print(f"✅ Task [{task_name}] already finished.")
        return

    print(f"🚀 Processing [{task_name}]: {len(todo_list)} items remaining...")
    
    image_folder = os.path.join(task_path, "images")

    # 4. 循环推理
    # 使用 append 模式打开文件，实现流式写入
    with open(output_file, 'a', encoding='utf-8') as f_out:
        for item in tqdm(todo_list, desc=f"Running {task_name}"):
            idx = item['idx']
            prompt = item['prompt']
            ground_truth = item.get('answer', item.get('correct', ''))
            # 处理免责声明
            if task_name in NEED_DISCLAIMER_TASKS:
                prompt = DISCLAIMER_TEXT + prompt
            
            # 处理图片路径
            image_paths = []
            for k in ['image1', 'image2', 'image3', 'image4']:
                if k in item and item[k]:
                    # 优先使用本地拼接路径
                    fname = os.path.basename(item[k])
                    local_path = os.path.join(image_folder, fname)
                    if os.path.exists(local_path):
                        image_paths.append(local_path)
                    else:
                        # 如果找不到，回退到原始路径尝试（防止绝对路径情况）
                        if os.path.exists(item[k]):
                            image_paths.append(item[k])

            # 动态获取选项列表 (A), (B)... 用于解析
            current_choices = ['(A)', '(B)', '(C)', '(D)', '(E)'][:len(item.get('choices', []))]
            
            # === API 调用 ===
            response = query_hunyuan_api(image_paths, prompt)
            
            # === 答案解析 ===
            choice_pred = analyze_answer(response, current_choices)
            
            # === 构造符合要求的 JSONL 对象 ===
            result_record = {
                "task_name": task_name,
                "index": idx,
                "response": response,
                "choice": choice_pred,
                "correct_choice": ground_truth
            }
            
            # === 写入文件 (加换行符 \n) ===
            f_out.write(json.dumps(result_record, ensure_ascii=False) + "\n")
            f_out.flush() # 强制刷新缓冲区，确保写入硬盘

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, default='hunyuan-vision', help="Model name")
    # 这里修改为输入 benchmark 的根目录，例如 ./power_benchmark
    parser.add_argument("--benchmark_dir", type=str, required=True, help="Root directory containing all task folders")
    parser.add_argument("--lang", type=str, default='zh', help="zh or en")
    parser.add_argument("--output_dir", type=str, default='outputs', help="Output directory")
    args = parser.parse_args()

    # 1. 扫描所有 task_* 文件夹
    # 假设结构是 benchmark_dir/task_1_1, benchmark_dir/task_1_2 ...
    search_pattern = os.path.join(args.benchmark_dir, "task_*")
    task_dirs = sorted(glob.glob(search_pattern))
    
    if not task_dirs:
        print(f"❌ No task folders found in {args.benchmark_dir}")
        print("Expected structure: benchmark_dir/task_1_1, etc.")
        return

    print(f"📦 Found {len(task_dirs)} tasks. Starting batch evaluation...")
    print(f"🤖 Model: {args.model_name}")

    # 2. 依次处理每个 Task
    for task_path in task_dirs:
        if not os.path.isdir(task_path): continue
        process_single_task(task_path, args, args.output_dir)
        
    print("\n🎉 All tasks processed!")

if __name__ == "__main__":
    main()