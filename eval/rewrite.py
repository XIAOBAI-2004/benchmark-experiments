import json
import glob
import os

def batch_rename_overwrite():
    # 1. 扫描当前目录下所有的 .jsonl 文件
    files = glob.glob('*.jsonl')
    
    if not files:
        print("当前目录下没有找到 .jsonl 文件。")
        return

    print(f"检测到 {len(files)} 个文件，准备直接覆盖修改...\n")

    for file_path in files:
        print(f"正在处理: {file_path} ...", end="")
        
        try:
            # --- 第一步：读取所有数据到内存 ---
            modified_data = []
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try:
                        item = json.loads(line)
                        
                        # 核心修改逻辑：如果存在旧key，则改名
                        if 'correct_choice' in item:
                            item['correct'] = item.pop('correct_choice')
                            
                        modified_data.append(item)
                    except json.JSONDecodeError:
                        print(f"\n[警告] 跳过无法解析的行 (文件: {file_path})")
                        continue

            # --- 第二步：直接覆盖原文件 ---
            with open(file_path, 'w', encoding='utf-8') as f:
                for item in modified_data:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')
            
            print(" [完成]")

        except Exception as e:
            print(f"\n[错误] 处理 {file_path} 失败: {e}")

    print("\n所有文件处理完毕。")

if __name__ == "__main__":
    batch_rename_overwrite()