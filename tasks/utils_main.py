from tasks.util_layout_dect import batch_prepare_for_layout, MinerUSamplingParams, SamplingParams as MinerUSamplingParamsBase
from mineru_vl_utils.structs import BLOCK_TYPES, ContentBlock

import re
from typing import Literal, Sequence
from mineru.utils.pdf_image_tools import load_images_from_pdf
from mineru.cli.common import convert_pdf_bytes_to_bytes_by_pypdfium2
from PIL import Image
from pstats import SortKey
import math
from vllm.outputs import RequestOutput
from vllm import LLM, SamplingParams
from vllm.sampling_params import RequestOutputKind
from vllm.v1.engine.async_llm import AsyncLLM
from vllm.engine.arg_utils import AsyncEngineArgs
import vllm
from mineru_vl_utils import MinerULogitsProcessor
import glob ,os
import time
import uuid
import asyncio
from mineru.data.data_reader_writer import FileBasedDataWriter
from mineru_vl_utils.post_process import post_process as util_post_process
system_prompt = "You are a helpful assistant."
_layout_re = r"^<\|box_start\|>(\d+)\s+(\d+)\s+(\d+)\s+(\d+)<\|box_end\|><\|ref_start\|>(\w+?)<\|ref_end\|>(.*)$"
max_image_edge_ratio=50
min_image_edge=28
MODEL_PATH="/opt/modelscope/hub/OpenDataLab/MinerU2___5-2509-1___2B"
DEFAULT_SAMPLING_PARAMS: dict[str, MinerUSamplingParams] = {
    "table": MinerUSamplingParams(presence_penalty=1.0, frequency_penalty=0.005),
    "equation": MinerUSamplingParams(presence_penalty=1.0, frequency_penalty=0.05),
    "[default]": MinerUSamplingParams(presence_penalty=1.0, frequency_penalty=0.05),
    "[layout]": MinerUSamplingParams(),
}

DEFAULT_PROMPTS: dict[str, str] = {
    "table": "\nTable Recognition:",
    "equation": "\nFormula Recognition:",
    "[default]": "\nText Recognition:",
    "[layout]": "\nLayout Detection:",
}
ANGLE_MAPPING: dict[str, Literal[0, 90, 180, 270]] = {
    "<|rotate_up|>": 0,
    "<|rotate_right|>": 90,
    "<|rotate_down|>": 180,
    "<|rotate_left|>": 270,
}
def _parse_angle(tail: str) -> Literal[None, 0, 90, 180, 270]:
    for token, angle in ANGLE_MAPPING.items():
        if token in tail:
            return angle
    return None

def _convert_bbox(bbox: Sequence[int] | Sequence[str]) -> list[float] | None:
    bbox = tuple(map(int, bbox))
    if any(coord < 0 or coord > 1000 for coord in bbox):
        return None
    x1, y1, x2, y2 = bbox
    x1, x2 = (x2, x1) if x2 < x1 else (x1, x2)
    y1, y2 = (y2, y1) if y2 < y1 else (y1, y2)
    if x1 == x2 or y1 == y2:
        return None
    return list(map(lambda num: num / 1000.0, (x1, y1, x2, y2)))

def parse_layout_output(output: str) -> list[ContentBlock]:
    blocks: list[ContentBlock] = []
    for line in output.split("\n"):
        match = re.match(_layout_re, line)
        if not match:
            print(f"Warning: line does not match layout format: {line}")
            continue  # Skip invalid lines
        x1, y1, x2, y2, ref_type, tail = match.groups()
        bbox = _convert_bbox((x1, y1, x2, y2))
        if bbox is None:
            print(f"Warning: invalid bbox in line: {line}")
            continue  # Skip invalid bbox
        ref_type = ref_type.lower()
        if ref_type not in BLOCK_TYPES:
            print(f"Warning: unknown block type in line: {line}")
            continue  # Skip unknown block types
        angle = _parse_angle(tail)
        if angle is None:
            print(f"Warning: no angle found in line: {line}")
        blocks.append(ContentBlock(ref_type, bbox, angle=angle))
    return blocks
def batch_prepare_for_extract(
    images: list[Image.Image],
    blocks_list: list[list[ContentBlock]],
    not_extract_list: list[str] | None = None,
) -> list[tuple[list[Image.Image], list[str], list[MinerUSamplingParams], list[int]]]:
    return [prepare_for_extract(im, bls, not_extract_list) for im, bls in zip(images, blocks_list)]



def resize_by_need(image: Image.Image) -> Image.Image:
    edge_ratio = max(image.size) / min(image.size)
    if edge_ratio > max_image_edge_ratio:
        width, height = image.size
        if width > height:
            new_w, new_h = width, math.ceil(width / max_image_edge_ratio)
        else:  # width < height
            new_w, new_h = math.ceil(height / max_image_edge_ratio), height
        new_image = Image.new(image.mode, (new_w, new_h), (255, 255, 255))
        new_image.paste(image, (int((new_w - width) / 2), int((new_h - height) / 2)))
        image = new_image
    if min(image.size) < min_image_edge:
        scale = min_image_edge / min(image.size)
        new_w, new_h = round(image.width * scale), round(image.height * scale)
        image = image.resize((new_w, new_h), Image.Resampling.BICUBIC)
    return image
def prepare_for_extract(
    image: Image.Image,
    blocks: list[ContentBlock],
    not_extract_list: list[str] | None = None,
) -> tuple[list[Image.Image], list[str], list[MinerUSamplingParams], list[int]]:
    width, height = image.size
    block_images: list[Image.Image] = []
    prompts: list[str] = []
    sampling_params: list[MinerUSamplingParams] = []
    indices: list[int] = []
    skip_list = {"image", "list", "equation_block"}
    if not_extract_list:
        for not_extract_type in not_extract_list:
            if not_extract_type in BLOCK_TYPES:
                skip_list.add(not_extract_type)
    for idx, block in enumerate(blocks):
        if block.type in skip_list:
            continue  # Skip blocks that should not be extracted.
        x1, y1, x2, y2 = block.bbox
        scaled_bbox = (x1 * width, y1 * height, x2 * width, y2 * height)
        block_image = image.crop(scaled_bbox)
        if block.angle in [90, 180, 270]:
            block_image = block_image.rotate(block.angle, expand=True)
        block_image = resize_by_need(block_image)
        block_images.append(block_image)
        prompt = DEFAULT_PROMPTS.get(block.type) or DEFAULT_PROMPTS["[default]"]
        prompts.append(prompt)
        params = DEFAULT_SAMPLING_PARAMS.get(block.type) or  MinerUSamplingParams(presence_penalty=1.0, frequency_penalty=0.05)
        sampling_params.append(params)
        indices.append(idx)
    return block_images, prompts, sampling_params, indices

# 自定义Error类
class ServerError(Exception):
    """服务器内部错误"""
    pass
def get_output_content(output: RequestOutput) -> str:
        if not output.finished:
            raise ServerError("The output generation was not finished.")

        choices = output.outputs
        if not (isinstance(choices, list) and choices):
            raise ServerError("No choices found in the output.")

        finish_reason = choices[0].finish_reason
        if finish_reason is None:
            raise ServerError("Finish reason is None in the output.")
        if finish_reason == "length":
            print("Warning: The output was truncated due to length limit.")
        elif finish_reason != "stop":
            raise ServerError(f"Unexpected finish reason: {finish_reason}")
        return choices[0].text
def build_messages( prompt: str) -> list[dict]:
    prompt = prompt 
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if "<image>" in prompt:
        prompt_1, prompt_2 = prompt.split("<image>", 1)
        user_messages = [
            *([{"type": "text", "text": prompt_1}] if prompt_1.strip() else []),
            {"type": "image"},
            *([{"type": "text", "text": prompt_2}] if prompt_2.strip() else []),
        ]
    else:  # image before text, which is the default behavior.
        user_messages = [
            {"type": "image"},
            {"type": "text", "text": prompt},
        ]
    messages.append({"role": "user", "content": user_messages})
    return messages

def build_vllm_sampling_params(sampling_params: MinerUSamplingParams):
    sp = sampling_params

    vllm_sp_dict = {
        "temperature": sp.temperature,
        "top_p": sp.top_p,
        "top_k": sp.top_k,
        "presence_penalty": sp.presence_penalty,
        "frequency_penalty": sp.frequency_penalty,
        "repetition_penalty": sp.repetition_penalty,
        # max_tokens should smaller than model max length
        "max_tokens": 16384,
    }

    if sp.no_repeat_ngram_size is not None:
        vllm_sp_dict["extra_args"] = {
            "no_repeat_ngram_size": 100,
            "debug": False,
        }

    return SamplingParams(
        **{k: v for k, v in vllm_sp_dict.items() if v is not None},
        skip_special_tokens=False,
    )
def load_model():
    kwargs={}
    kwargs["logits_processors"] = [MinerULogitsProcessor]
    kwargs["gpu_memory_utilization"] = 0.9
    kwargs["mm_processor_cache_gb"] = 0
    kwargs["max_num_batched_tokens"]=8192
    # kwargs["enable_prefix_caching"]=False
    kwargs['model'] = MODEL_PATH
    # kwargs["max_num_seqs"]=512
    vllm_llm = vllm.LLM(**kwargs)
    tokenizer = vllm_llm.get_tokenizer()
    return vllm_llm,tokenizer

# # 异步版本的模型加载
# async def load_engine():
#     engine = AsyncLLM.from_engine_args(AsyncEngineArgs(
#         model = MODEL_PATH,
#         gpu_memory_utilization=0.3,
#         mm_processor_cache_gb=0,
#         logits_processors=[MinerULogitsProcessor]
#     ))
#     # vllm v1 的 engine.tokenizer 是 TokenizerGroup，需要从 transformers 单独加载
#     from transformers import AutoTokenizer
#     tokenizer = engine.tokenizer
#     return engine, tokenizer

# # 异步预测函数
# async def aio_predict(vllm_engine, tokenizer, image, prompt, sampling_params):
#     messages = [{"role": "system", "content": system_prompt},
#                 {"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]

#     chat_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

#     vllm_sp = SamplingParams(
#         temperature=sampling_params.temperature,
#         top_p=sampling_params.top_p,
#         max_tokens=16384,
#         output_kind=RequestOutputKind.FINAL_ONLY,
#         skip_special_tokens=False
#     )

#     result = ""
#     async for output in vllm_engine.generate(
#         prompt={"prompt": chat_prompt, "multi_modal_data": {"image": image}},
#         sampling_params=vllm_sp,
#         request_id=f"req-{uuid.uuid4()}"
#     ):
#         result = output.outputs[0].text
#     return result
# 异步版本的模型加载
async def load_engine():
    engine = AsyncLLM.from_engine_args(AsyncEngineArgs(
        model = MODEL_PATH,
        gpu_memory_utilization=0.8,
        mm_processor_cache_gb=0,
        max_num_seqs=512,
        logits_processors=[MinerULogitsProcessor]
    ))
    # vllm v1 的 tokenizer 是 TokenizerGroup，我们需要从 transformers 单独加载
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
    return engine, tokenizer

# 异步预测函数 - 修复版本
async def aio_predict(vllm_engine, tokenizer, image, prompt, sampling_params):
    # 对于 vLLM v1，我们需要手动构建prompt格式
    # 根据你的模型调整这个格式
    chat_prompt = f"{system_prompt}\n\nUser: <image>\n{prompt}\n\nAssistant:"
    
    # 或者使用原始的消息格式
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}
    ]
    
    # 如果模型支持chat_template，尝试使用它
    if hasattr(tokenizer, "apply_chat_template"):
        chat_prompt = tokenizer.apply_chat_template(
            messages, 
            tokenize=False, 
            add_generation_prompt=True
        )
    else:
        # 手动构建prompt格式
        # 这取决于你的具体模型，以下是通用格式
        chat_prompt = f"{system_prompt}\n\nUser: <image>\n{prompt}\n\nAssistant:"
    
    vllm_sp = SamplingParams(
        temperature=sampling_params.temperature,
        top_p=sampling_params.top_p,
        max_tokens=16384,
        skip_special_tokens=False
    )
    
    result = ""
    async for output in vllm_engine.generate(
        prompt={"prompt": chat_prompt, "multi_modal_data": {"image": image}},
        sampling_params=vllm_sp,
        request_id=f"req-{uuid.uuid4()}"
    ):
        result = output.outputs[0].text
    return result
def batch_predict(
    vllm_llm,
    tokenizer,
    images: list[Image.Image],
    # sampling_params: MinerUSamplingParams,
    # prompts: str = "",
    sampling_params: Sequence[MinerUSamplingParams] | MinerUSamplingParams,
    prompts: Sequence[str] | str,
    priority:  None = None,
) -> list[str]:
    image_objs: list[Image.Image] = images
    
    
    
    if isinstance(prompts, str):
        chat_prompts: list[str] = [
            tokenizer.apply_chat_template(
                build_messages(prompts),  # type: ignore
                tokenize=False,
                add_generation_prompt=True,
            )
        ] * len(images)
    else:  # isinstance(prompts, Sequence[str])
        chat_prompts: list[str] = [
            tokenizer.apply_chat_template(
                build_messages(prompt),  # type: ignore
                tokenize=False,
                add_generation_prompt=True,
            )
            for prompt in prompts
        ]
    if not isinstance(sampling_params, Sequence):
        vllm_sp_list = [build_vllm_sampling_params(sampling_params)] * len(images)
    else:
        vllm_sp_list = [build_vllm_sampling_params(sp) for sp in sampling_params]
    outputs = []
    batch_size = 384

    for i in range(0, len(images), batch_size):
        batch_image_objs = image_objs[i : i + batch_size]
        batch_chat_prompts = chat_prompts[i : i + batch_size]
        batch_sp_list = vllm_sp_list[i : i + batch_size]
        batch_outputs = predict_one_batch(
            vllm_llm,
            batch_image_objs,
            batch_chat_prompts,
            batch_sp_list,
        )
        outputs.extend(batch_outputs)

    return outputs


def predict_one_batch(
    vllm_llm,
    image_objs: list[Image.Image],
    chat_prompts: list[str],
    vllm_sampling_params: list[SamplingParams],
):
    vllm_prompts = [
        {"prompt": chat_prompt, "multi_modal_data": {"image": image}}
        for chat_prompt, image in zip(chat_prompts, image_objs)
    ]
    print("mydebug:call predict_one_batch:",time.time())
    outputs = vllm_llm.generate(
        prompts=vllm_prompts,  # type: ignore
        sampling_params=vllm_sampling_params,
        use_tqdm=False,
    )

    return [get_output_content(output) for output in outputs]

# 异步批量预测函数
async def batch_aio_predict(
    vllm_engine,
    tokenizer,
    images: list[Image.Image],
    sampling_params: Sequence[MinerUSamplingParams] | MinerUSamplingParams,
    prompts: Sequence[str] | str,
    priority: None = None,
) -> list[str]:
    if isinstance(prompts, str):
        prompts = [prompts] * len(images)
    if not isinstance(sampling_params, Sequence):
        sampling_params = [sampling_params] * len(images)

    # 并发执行所有预测任务
    tasks = [
        aio_predict(vllm_engine, tokenizer, image, prompt, sp)
        for image, prompt, sp in zip(images, prompts, sampling_params)
    ]
    outputs: list[str] = await asyncio.gather(*tasks)
    return outputs

def collect_image_for_extract(layout_images,blocks_list):
    all_images: list[Image.Image] = []
    all_prompts: list[str] = []
    all_params: list[MinerUSamplingParams] = []
    all_indices: list[tuple[int, int]] = []
    prepared_inputs = batch_prepare_for_extract(
        layout_images,
        blocks_list,
    )
    for img_idx, (block_images, prompts, params, indices) in enumerate(prepared_inputs):
        all_images.extend(block_images)
        all_prompts.extend(prompts)
        all_params.extend(params)
        all_indices.extend([(img_idx, idx) for idx in indices])
        
    return all_images,all_params, all_prompts,all_indices
class ImageType:
    PIL = 'pil_img'
    BASE64 = 'base64_img'
def load_pdfs(page):
    pdf_dir = "/data/articles/cs_CL_current_200"
    pdf_files = glob.glob(os.path.join(pdf_dir, "*.pdf"))[:page]  # 获取前n个PDF
    all_images_pil_list = []
    all_image_list = []
    images_count_per_pdf = []  # 记录每个PDF的页面数量

    for idx, pdf_file_path in enumerate(pdf_files):
        with open(pdf_file_path, 'rb') as fi:
            pdf_bytes = fi.read()
        new_pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes)
        images_list, pdf_doc = load_images_from_pdf(new_pdf_bytes, image_type=ImageType.PIL)
        images_pil_list = [image_dict["img_pil"] for image_dict in images_list]
        images_count_per_pdf.append(len(images_pil_list))  # 记录当前PDF的页面数
        all_image_list.extend(images_list)
        all_images_pil_list.extend(images_pil_list)  # 拼接到总列表
    return all_images_pil_list, all_image_list, pdf_files, images_count_per_pdf


def post_process(blocks: list[ContentBlock]) -> list[ContentBlock]:
    try:
        return util_post_process(
            blocks,
            simple_post_process=False,
            handle_equation_block=True,
            abandon_list=False,
            abandon_paratext=False,
            debug=False,
        )
    except Exception as e:
        print(f"Warning: post-processing failed with error: {e}")
        return blocks

def batch_post_process(blocks_list):
    return [post_process(blocks) for blocks in blocks_list]


def self_post_process(pdf_files, results_with_metadata, save_dir=None):
    """
    后处理函数 - 为每个PDF文档生成middle_json并可选保存zip文件
    参考 postprocessing_task 的实现逻辑

    Args:
        pdf_files: PDF文件路径列表
        results_with_metadata: 包含result, pdf_idx, page_idx, pdf_path的字典列表
        save_dir: 可选，如果提供则保存zip文件到该目录

    Returns:
        list: 每个PDF对应的middle_json列表
    """
    import os
    import json
    import zipfile
    from mineru.backend.vlm.vlm_analyze import result_to_middle_json

    all_middle_json = []

    # 按pdf_idx分组整理结果
    results_by_pdf = {}
    for item in results_with_metadata:
        pdf_idx = item['pdf_idx']
        if pdf_idx not in results_by_pdf:
            results_by_pdf[pdf_idx] = []
        results_by_pdf[pdf_idx].append(item)

    # 遍历每个PDF文件
    for i in range(len(pdf_files)):
        pdf_file_path = pdf_files[i]

        # 如果该PDF没有结果，跳过
        if i not in results_by_pdf:
            print(f"Warning: PDF {i} ({pdf_file_path}) has no results, skipping")
            all_middle_json.append(None)
            continue

        # 获取该PDF的所有页面结果
        pdf_results = results_by_pdf[i]
        # 按page_idx排序确保页面顺序正确
        pdf_results.sort(key=lambda x: x['page_idx'])

        try:
            # 读取PDF并加载图像
            with open(pdf_file_path, 'rb') as fi:
                pdf_bytes = fi.read()

            new_pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes)
            images_list, pdf_doc = load_images_from_pdf(new_pdf_bytes, image_type=ImageType.PIL)

            pdf_name = os.path.basename(pdf_file_path)
            local_image_dir = f"/tmp/data/mineru_ocr_local_image_dir/{pdf_name}"

            if not os.path.exists(local_image_dir):
                os.makedirs(local_image_dir, exist_ok=True)

            # 从images_list中提取PIL图像
            current_images_list = []
            for image_dict in images_list:
                if isinstance(image_dict, dict) and "img_pil" in image_dict:
                    current_images_list.append(image_dict)

            # 提取results（ContentBlock列表）
            current_gpu_results = [item['result'] for item in pdf_results]

            # 检查图像数量和结果数量是否匹配
            if len(current_images_list) != len(current_gpu_results):
                print(f"Warning: Image count {len(current_images_list)} != result count {len(current_gpu_results)} for PDF {i}")

            # 生成middle_json
            image_writer = FileBasedDataWriter(local_image_dir)
            try:
                middle_json = result_to_middle_json(
                    current_gpu_results,
                    current_images_list,
                    pdf_doc,
                    image_writer
                )
                all_middle_json.append(middle_json)
                print(f"Successfully generated middle_json for PDF {i} ({pdf_name})")

                # 保存zip文件（如果提供了save_dir）
                if save_dir and middle_json is not None:
                    try:
                        pdf_file_name = os.path.basename(pdf_file_path).replace(".pdf", "")

                        # 步骤1: 创建推理结果
                        infer_result = {"middle_json": middle_json}

                        # 步骤2: JSON序列化
                        res_json_str = json.dumps(infer_result, ensure_ascii=False)

                        # 步骤3: 创建结果目录
                        result_dir = f"{save_dir}/result"
                        if not os.path.exists(result_dir):
                            os.makedirs(result_dir, exist_ok=True)

                        # 步骤4: 构建target_file路径
                        target_file = f"{result_dir}/{pdf_file_name}.json.zip"

                        # 步骤5: ZIP压缩写入
                        with zipfile.ZipFile(target_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                            res_json_bytes = res_json_str.encode("utf-8")
                            zf.writestr(f"{pdf_file_name}.json", res_json_bytes)

                        print(f"Successfully saved zip file: {target_file}")

                    except Exception as save_error:
                        print(f"Error saving zip file for PDF {i} ({pdf_name}): {save_error}")
                        import traceback
                        traceback.print_exc()

            finally:
                # 确保文档对象被正确关闭
                try:
                    pdf_doc.close()
                except:
                    pass

        except Exception as e:
            print(f"Error processing PDF {i} ({pdf_file_path}): {e}")
            import traceback
            traceback.print_exc()
            all_middle_json.append(None)

    return all_middle_json
