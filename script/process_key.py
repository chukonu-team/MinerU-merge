import os
import random

import pandas as pd

def extract_obs_key(input,output):
    df = pd.read_json(input,lines=True)
    with open(output,'w',encoding="utf-8") as f:
        for url in df['obs_key']:
            f.write(url + '\n')


def dedup_keys(input,output):
    seen_filenames = set()
    unique_urls = []
    with open(input,'r',encoding="utf-8") as f:
        for url in f:
            url = url.strip()
            if url:
                filename = url.split('/')[-1]
                if filename in seen_filenames:
                    continue
                seen_filenames.add(filename)
                unique_urls.append(url)

    with open(output,'w',encoding="utf-8") as f:
        for url in unique_urls:
            f.write(url + '\n')


def dedup_keys1(input,output):
    seen_filenames = set()
    unique_urls = []
    with open(input,'r',encoding="utf-8") as f:
        for url in f:
            url = url.strip()
            if url:
                if url in seen_filenames:
                    continue
                seen_filenames.add(url)
                unique_urls.append(url)

    with open(output,'w',encoding="utf-8") as f:
        for url in unique_urls:
            f.write(url + '\n')


def random_select(input,output,sample_size=10000):
    with open(input,'r',encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    sample_urls = random.sample(urls,sample_size)

    with open(output,'w',encoding="utf-8") as f:
        for url in sample_urls:
            f.write(url + '\n')

def write_to_new_file(file_count, lines):
    output_filename = f"batch3_keys_part_{file_count}.txt"
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f"已创建: {output_filename} 包含 {len(lines):,} 行")

def split_large_file(input_file, lines_per_file=6_000_000):
    file_count = 1
    line_buffer = []

    with open(input_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            line_buffer.append(line)

            # 每5000万行写入新文件
            if i % lines_per_file == 0:
                write_to_new_file(file_count, line_buffer)
                file_count += 1
                line_buffer = []
        # 处理剩余行
        if line_buffer:
            write_to_new_file(file_count, line_buffer)



def remove_existing_records(source_file, exclude_file, output_file):
    """
    从source_file中去掉在exclude_file中已存在的记录，输出到output_file

    参数:
        source_file: 源文件路径
        exclude_file: 包含要排除的记录的文件路径
        output_file: 输出文件路径
    """
    # 读取要排除的记录
    with open(exclude_file, 'r', encoding='utf-8') as f:
        exclude_records = set(line.strip() for line in f if line.strip())

    # 处理源文件并写入输出文件
    with open(source_file, 'r', encoding='utf-8') as src, \
            open(output_file, 'w', encoding='utf-8') as out:

        for line in src:
            stripped_line = line.strip()
            if stripped_line and stripped_line not in exclude_records:
                out.write(line)  # 保留原始行的换行符

def get_file_name(input,output):
    records = []
    with open(input, 'r', encoding='utf-8') as f:
        for url in f:
            url = url.strip()
            filename = url.split('/')[-1]
            records.append(filename)

    with open(output, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(record + '\n')


def merge_keys(intput,output):
    url_set = set()
    for file in os.listdir(intput):
        if file.endswith('.txt'):
            with open(os.path.join(intput, file), 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip().split("/")[-1]
                    url_set.add(line)
    unique_urls = list(url_set)
    with open(output, 'w', encoding='utf-8') as f:
        for url in unique_urls:
            f.write(url + '\n')

def merge_keys1(intput,output):
    url_list = []
    file_name_set = set()
    for file in os.listdir(intput):
        if file.endswith('.txt'):
            with open(os.path.join(intput, file), 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    file_name = line.split("/")[-1]
                    if file_name not in file_name_set:
                        file_name_set.add(file_name)
                        url_list.append(line)

    with open(output, 'w', encoding='utf-8') as f:
        for url in url_list:
            f.write(url + '\n')


def find_ori_url(key_path,ori_path,output):
    key_set = set()
    with open(key_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            key_set.add(line)

    url_list = []
    matched_urls = set()
    with open(ori_path, 'r', encoding='utf-8') as f:
        for url in f:
            url = url.strip()
            filename = url.split('/')[-1]
            if filename in key_set and filename not in matched_urls:
                url_list.append(url)
                matched_urls.add(filename)

    with open(output, 'w', encoding='utf-8') as f:
        for url in url_list:
            f.write(url + '\n')



def split_batch_keys(all_path , processed_path, output, num):
    processed_set = set()
    for file in os.listdir(processed_path):
        if file.endswith('.txt'):
            with open(os.path.join(processed_path, file), 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    processed_set.add(line)

    new_list = []
    count = 0
    with open(all_path, 'r', encoding='utf-8') as f:
        for line in f:
            if count >= num:
                break
            line = line.strip()
            if line not in processed_set:
                new_list.append(line)
                count += 1

    with open(output, 'w', encoding='utf-8') as f:
        for new_url in new_list:
            f.write(new_url + '\n')

if __name__ == '__main__':
    # extract_obs_key("pdf_en_zh_and_no_lang.txt","pdf_en_zh_and_no_lang_obs_key.txt")
    # dedup_keys("../batch5/qikan_1009_obs_key.txt","../batch5/batch5_keys.txt")
    # random_select("../batch5/batch5_keys.txt","../batch5/batch5_10000.txt")
    # split_large_file("pdf_en_zh_and_no_lang_obs_key_unique.txt")
    # count_lang()
    # remove_existing_records("/root/wangshd/batch3/download/upload_done.txt","/root/wangshd/batch3/upload_done_bak.txt","/root/wangshd/batch3/new_keys.txt")
    # get_file_name("../batch5/batch5_keys.txt","../batch5/batch5_10000.txt")
    # dedup_keys1("/root/wangshd/batch6/download/upload_done.txt","/root/wangshd/batch6/download/upload_done_unique.txt")
    # merge_keys("/root/wangshd/batch6/vlm/chunk_keys", "/root/wangshd/batch6/batch_1.txt")
    # find_ori_url("/root/wangshd/batch6/batch_1.txt","/root/wangshd/batch6/download/full_key.txt","/root/wangshd/batch6/processed/batch_1.txt")
    split_batch_keys("/root/wangshd/batch6/download/full_key.txt","/root/wangshd/batch6/processed","/root/wangshd/batch6/processed/batch_2.txt", 2000 * 10000)
