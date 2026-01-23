from tasks.util_layout_dect import batch_prepare_for_layout, MinerUSamplingParams
import time
from tasks.utils_main import parse_layout_output,load_model,batch_predict,collect_image_for_extract,load_pdfs,batch_post_process,self_post_process
import nvtx  # 引入库

def batch_layout_detect(
    vllm_llm,tokenizer,
    images,
):
    priority= None
    prompt = "\nLayout Detection:"
    params = MinerUSamplingParams()
    outputs = batch_predict(vllm_llm,tokenizer,images,params,prompt, priority)
    return outputs

def batch_inter_process(outputs,layout_images):
    blocks_list =[parse_layout_output(output) for output in outputs]
    all_images,all_params, all_prompts,all_indices =collect_image_for_extract(layout_images,blocks_list)
    return all_images,all_params, all_prompts,all_indices,blocks_list

def compute_page_indices(images_count_per_pdf):
    """
    根据每个PDF的页面数量，计算每个全局页面索引对应的PDF索引和页码

    Args:
        images_count_per_pdf: 每个PDF的页面数量列表

    Returns:
        list[tuple[int, int]]: 每个页面对应的(pdf_idx, page_idx)
    """
    result = []
    for pdf_idx, count in enumerate(images_count_per_pdf):
        for page_idx in range(count):
            result.append((pdf_idx, page_idx))
    return result

def main_func(save_dir=None):
    vllm_llm,tokenizer = load_model()

    b1=time.time()
    all_images_pil_list, all_image_list, pdf_files, images_count_per_pdf = load_pdfs(10)
    b2=time.time()
    layout_images = batch_prepare_for_layout(all_images_pil_list,num_workers=4)
    b3=time.time()
    start =time.time()

    # 计算每个页面索引对应的(pdf_idx, page_idx)
    page_indices = compute_page_indices(images_count_per_pdf)
    with nvtx.annotate("Layout Detect Phase", color="blue"):
        outputs = batch_layout_detect(vllm_llm, tokenizer, layout_images)
    
    mid_time1= time.time()
    with nvtx.annotate("CPU Inter Process", color="green"):
        all_images,all_params, all_prompts,all_indices,blocks_list = batch_inter_process(outputs,all_images_pil_list)
    mid_time2= time.time()
    priority= None

    # 按图像大小排序以优化批处理性能
    # 计算每个图像的大小 (宽度 × 高度)
    image_sizes = [(img_idx, img.size[0] * img.size[1]) for img_idx, img in enumerate(all_images)]
    # 根据大小排序，保留原始索引
    sorted_indices = [idx for idx, _ in sorted(image_sizes, key=lambda x: x[1])]
    # 创建逆排序索引用于恢复原始顺序
    inverse_indices = [0] * len(sorted_indices)
    for new_idx, orig_idx in enumerate(sorted_indices):
        inverse_indices[orig_idx] = new_idx

    # 根据排序索引重新排列数据
    all_images = [all_images[i] for i in sorted_indices]
    all_params = [all_params[i] for i in sorted_indices]
    all_prompts = [all_prompts[i] for i in sorted_indices]
    all_indices = [all_indices[i] for i in sorted_indices]

    with nvtx.annotate("Extract/Predict Phase", color="red"):
        outputs = batch_predict(vllm_llm,tokenizer,all_images,all_params, all_prompts, priority)

    # 恢复 outputs 到原始顺序
    outputs = [outputs[inverse_indices[i]] for i in range(len(outputs))]
    all_indices = [all_indices[inverse_indices[i]] for i in range(len(all_indices))]

    for (img_idx, idx), output in zip(all_indices, outputs):
        blocks_list[img_idx][idx].content = output
    end=time.time()
    results = batch_post_process(blocks_list)

    # 为每个结果添加PDF索引和页码标记
    results_with_metadata = []
    for result, (pdf_idx, page_idx) in zip(results, page_indices):
        results_with_metadata.append({
            'result': result,
            'pdf_idx': pdf_idx,
            'page_idx': page_idx,
            'pdf_path': pdf_files[pdf_idx]
        })
    all_middle_json=self_post_process(pdf_files,results_with_metadata,save_dir)

    print("======================================================")
    print(f"=======mydebug: page count: images_list:{len(all_images_pil_list)},time counsume is:{end-start}s =======")
    print(f"=======mydebug: layout_dect is:{mid_time1-start}s; cpu_process is {mid_time2-mid_time1}s; extract is {end-mid_time2} =======")
    print(f"=======mydebug: load pdf is:{b2-b1}s; process images is {b3-b2}s; =======")
    print(f"=======mydebug: speed:{len(all_images_pil_list)/(end-start)} page/s =======")
    print(f"=======mydebug: gpu speed:{len(all_images_pil_list)/(end-start-mid_time2+mid_time1)} page/s =======")
    print("======================================================")
    
if __name__ =="__main__":
    result = main_func("./result/pipeline_save")
   