import json
from tqdm import tqdm
import os
import argparse
import glob
from query_hunyuan_api import query_hunyuan_api 

# 免责声明配置
disclaimer = "Disclaimer: This is not to make unfair assumptions about the people in the image and you just need to give your assessment on this question. You don't need to identify the real people. You just need to analyze based on the information I gave you.\n\n"

def load_custom_dataset(task_name, lang='zh'):
    """
    加载本地 JSON 数据
    """
    # 假设脚本与 task 文件夹同级，或者通过完整路径传入
    # 如果 task_name 是绝对路径，直接使用；否则视为相对路径
    if os.path.isabs(task_name):
        base_dir = task_name
    else:
        base_dir = f"./{task_name}" 
        
    prompt_dir = os.path.join(base_dir, "prompts")
    
    # 匹配文件名，例如 *_zh.json
    json_pattern = os.path.join(prompt_dir, f"*_{lang}.json")
    json_files = glob.glob(json_pattern)
    
    if not json_files:
        print(f"Warning: No json files found in {json_pattern}")
        # 尝试打印一下当前路径，方便调试
        print(f"Current working directory: {os.getcwd()}")
        return []

    dataset = []
    for json_file in json_files:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            dataset.append(data)
            
    # 按 idx 排序
    dataset.sort(key=lambda x: x['idx'])
    print(f"Loaded {len(dataset)} samples from {prompt_dir}")
    return dataset

def analyze_answer(d, gpt_answer, all_choices):
    """
    [修改后] 纯规则的答案解析，不依赖外部模型
    """
    try:
        # 0. 预处理：去除前后空格
        clean_ans = gpt_answer.strip()

        # 1. 精确匹配：如果模型只输出了 (A) 或 A
        if clean_ans in ['(A)', '(B)', '(C)', '(D)', '(E)']:
            return clean_ans
        if clean_ans in ["A", "B", "C", "D", "E"]:
            return f"({clean_ans})"
        
        # 2. 包含匹配：检查答案中是否包含了 "(A)" 这种明确标记
        # 很多模型会输出: "The answer is (A)."
        for choice in all_choices:
            if choice in clean_ans:
                return choice

        # 3. 单词交集匹配 (原有逻辑的简化版)
        # 将回答拆分成单词，看是否有 A, B, C...
        # 注意：这步比较宽容，但也容易误判 (例如 "not A" 可能会被匹配成 A)
        tokens = clean_ans.replace('.', ' ').replace(',', ' ').split()
        intersect = []
        for t in tokens:
            # 检查是否是 (A) 或 A
            if t in all_choices:
                intersect.append(t)
            elif f"({t})" in all_choices:
                intersect.append(f"({t})")
        
        # 去重
        intersect = list(set(intersect))

        if len(intersect) == 1:
            return intersect[0]
        
        # 4. 如果还是找不到，尝试看最后一段 (很多模型会在最后总结 "Therefore, (B)")
        last_part = clean_ans.split('\n\n')[-1]
        for choice in all_choices:
            if choice in last_part:
                return choice
        
        # 5. 彻底失败
        return "(Z)"
        
    except Exception as e:
        print(f"Error parsing answer: {e}")
        return "(Z)"

def load_prompt(task_name, d, image_folder, need_disclaimer_tasks, model_name):
    """
    适配本地路径
    """
    image_paths = []
    # 你的数据 key 是 image1, image2...
    for k in ['image1', 'image2', 'image3', 'image4']:
        if k in d and d[k]:
            original_path = d[k]
            
            # 路径寻找逻辑
            if os.path.exists(original_path):
                final_path = original_path
            else:
                # 尝试只取文件名，拼接本地 image_folder
                filename = os.path.basename(original_path)
                final_path = os.path.join(image_folder, filename)
            
            if not os.path.exists(final_path):
                print(f"Error: Image not found: {final_path}")
                # 为了防止报错，这里可以选择跳过，或者放入一个占位符，视情况而定
                # 这里我们让它继续，但 API 那边可能会报 404
            
            image_paths.append(final_path)

    prompt = d['prompt']
    
    # 只有特定任务才加免责声明
    # 注意：如果 task_name 是全路径，需要提取最后的名字来判断
    task_basename = os.path.basename(task_name.rstrip('/'))
    if task_basename in need_disclaimer_tasks:
        prompt = disclaimer + prompt
        
    return image_paths, prompt

def query_model(task_name, args):
    model_name = args.model_name
    
    # 1. 加载本地数据
    test_data = load_custom_dataset(task_name, lang=args.lang)
    if not test_data:
        print("No data loaded, exiting query_model.")
        return {'val': [], 'test': []}
    
    # 2. 设置路径
    # 如果 task_name 是绝对路径，image_folder 也要相应调整
    if os.path.isabs(task_name):
        image_folder = os.path.join(task_name, 'images')
    else:
        image_folder = f'{task_name}/images'
        
    output_path = f'{output_save_folder}/{model_name}/{os.path.basename(task_name)}.json'
    
    os.makedirs(f'{output_save_folder}/{model_name}', exist_ok=True)
    
    outputs = {'val': [], 'test': []}
    
    # 断点续传逻辑
    processed_idxs = set()
    if os.path.exists(output_path):
        print(f"Loading existing results from {output_path}")
        try:
            outputs = json.load(open(output_path, 'r'))
            processed_idxs = set([item['idx'] for item in outputs['val']])
        except json.JSONDecodeError:
            print("Output file matches but is corrupted, starting over.")

    # 过滤数据
    data_to_run = [d for d in test_data if d['idx'] not in processed_idxs]
    
    if not data_to_run:
        print("All data processed.")
        return outputs

    print(f"Start inference on {len(data_to_run)} items...")
    
    for orig_d in tqdm(data_to_run):
        idx = orig_d['idx']
        gold_answer = orig_d['answer']
        
        # 动态获取选项列表 (A), (B)...
        all_choices = ['(A)', '(B)', '(C)', '(D)', '(E)'][:len(orig_d['choices'])]
        
        # 加载图片和 Prompt
        need_disclaimer_tasks = []
        image_paths, prompt = load_prompt(task_name, orig_d, image_folder, need_disclaimer_tasks, model_name)
        
        # 调用 API 推理
        gpt_answer = model_generate_func(image_paths, prompt)
        
        # 解析答案 (使用新的纯规则函数)
        prediction = analyze_answer(orig_d, gpt_answer, all_choices)
        
        # 保存
        outputs['val'].append({
            'idx': idx, 
            'answer': gold_answer, 
            'full_prediction': gpt_answer, 
            'prediction': prediction
        })
        
        # 实时写入
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(outputs, f, indent=4, ensure_ascii=False)
            
    return outputs

def eval_task(task_name, args):
    outputs = query_model(task_name, args)
    
    accu = 0
    total = 0
    results = outputs.get('val', [])
    
    for d in results:
        total += 1
        # 简单的字符串相等比较
        if d['answer'] == d['prediction']:
            accu += 1
    
    print('-'*50)
    print(f'Task {os.path.basename(task_name)} Performance')
    if total > 0:
        print(f'Accuracy: {round(accu/total*100, 2)}% ({accu}/{total})')
    else:
        print("No results generated.")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, default='Hunyuan-t1-vision', help="select the model name")
    parser.add_argument("--task_name", type=str, required=True, help="path to the task folder")
    parser.add_argument("--lang", type=str, default='zh', help="language of the dataset (zh/en)")
    args = parser.parse_args()
    return args

if __name__ == '__main__':
    args = parse_args()
    model_name = args.model_name
    print(f'Using model: {model_name}')

    # 注册模型函数
    model_generate_funcs = {
        'hunyuan-t1-vision-20250916': query_hunyuan_api,
        'hunyuan-vision': query_hunyuan_api,
        # 'GPT4V': query_gpt4v # 只有在你导入了 query_gpt4v 时才取消注释
    }
    
    if model_name not in model_generate_funcs:
        print(f"Error: Model {model_name} not found in registry.")
        exit(1)
        
    model_generate_func = model_generate_funcs[model_name]
    
    output_save_folder = '/workspace/code_dir/benchmark-experiments/power_benchmark/eval_result'
    # need_disclaimer_tasks = ['Forensic_Detection', 'Jigsaw', 'Art_Style']
    
    eval_task(args.task_name, args)