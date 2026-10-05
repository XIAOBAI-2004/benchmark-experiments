import pandas as pd
import json
import os
import matplotlib.pyplot as plt
import seaborn as sns

def load_jsonl(file_path):
    """读取 jsonl 文件并转换为 DataFrame"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Skipping invalid line in {file_path}")
    return pd.DataFrame(data)

def analyze_results(file_path):
    print(f"正在分析文件: {file_path} ...")
    
    # 1. 加载数据
    df = load_jsonl(file_path)
    
    # 2. 预处理：判断是否正确
    # 注意：有时候模型输出会有多余空格，strip() 可以增加鲁棒性
    df['is_correct'] = df.apply(lambda row: row['choice'].strip() == row['correct'].strip(), axis=1)
    
    # 3. 计算总体准确率 (Overall Accuracy)
    total_acc = df['is_correct'].mean()
    print(f"\n{'='*30}")
    print(f"总体准确率 (Overall Accuracy): {total_acc:.2%}")
    print(f"总样本数: {len(df)}")
    print(f"{'='*30}\n")
    
    # 4. 按任务细分准确率 (Per-Task Accuracy)
    # 假设 task_name 格式为 task_1_1, task_1_2... 我们可以提取大类
    df['task_category'] = df['task_name'].apply(lambda x: x.split('_')[1] if len(x.split('_')) > 1 else 'other')
    
    # 按具体的 task_name 聚合
    task_metrics = df.groupby('task_name')['is_correct'].agg(['mean', 'count']).reset_index()
    task_metrics.columns = ['Task Name', 'Accuracy', 'Count']
    task_metrics = task_metrics.sort_values(by='Task Name')
    
    print("--- 各子任务准确率 (Per-Task Metrics) ---")
    print(task_metrics.to_string(index=False, float_format='{:.2%}'.format))
    
    # 5. 保存统计结果到 CSV (方便放入论文或报告)
    output_csv = file_path.replace('.jsonl', '_metrics.csv')
    task_metrics.to_csv(output_csv, index=False)
    print(f"\n详细统计数据已保存至: {output_csv}")

    return df, task_metrics


if __name__ == "__main__":
    # 指向你上传的文件路径
    # 如果你的脚本和jsonl在同一目录下，直接写文件名即可
    # 如果在不同目录，请修改这里，例如: './results/hunyuan-large-vision.jsonl'
    target_file = '/workspace/code_dir/benchmark-experiments/eval_result/zh/gemini-3-pro-preview.jsonl' 
    
    if os.path.exists(target_file):
        df_result, metrics_df = analyze_results(target_file)
        
        # 生成图表
        plot_accuracy(metrics_df, 'benchmark_accuracy_plot.png')
    else:
        print(f"错误: 找不到文件 {target_file}，请检查路径。")