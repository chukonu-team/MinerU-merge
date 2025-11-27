import argparse
import os
import random


def write_to_new_file(file_count, lines, output):
    os.makedirs(output, exist_ok=True)
    output_filename = f"{file_count:06d}.txt"
    output_path = os.path.join(output, output_filename)
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(line + '\n')
    print(f"已创建: {output_filename} 包含 {len(lines):,} 行")


def split_key(prefix, input, output, num , start_num):
    url_list = set()
    max = 0
    for file in os.listdir(output):
            if file.endswith('.txt'):
                file_num = int(file.split(".")[0])
                if file_num > max:
                    max = file_num
                with open(os.path.join(output, file), 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip().split("/")[-1]
                        url_list.add(line)
    start = max + 1
    if max == 0:
        start = max

    if start_num:
        start = start_num

    # 读取所有行并添加前缀
    all_lines = set()
    with open(input, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() not in url_list:
                if prefix:
                    line = f"{prefix}{line.strip()}"
                else:
                    line = line.strip()
                all_lines.add(line)

    # 分割成多个文件
    all_lines_list = list(all_lines)
    file_count = start
    for i in range(0, len(all_lines), num):
        chunk = all_lines_list[i:i + num]
        write_to_new_file(file_count, chunk, output)
        file_count += 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--num", required=True, type=int)
    parser.add_argument("--start", type=int)
    args = parser.parse_args()
    split_key(args.prefix, args.input, args.output, args.num , args.start)
