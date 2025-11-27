# Copyright (c) Opendatalab. All rights reserved.
import os
import time

from loguru import logger

from .utils import enable_custom_logits_processors, set_default_gpu_memory_utilization, set_default_batch_size
from .model_output_to_middle_json import result_to_middle_json
from ...data.data_reader_writer import DataWriter
from mineru.utils.pdf_image_tools import load_images_from_pdf
from ...utils.check_sys_env import is_mac_os_version_supported
from ...utils.config_reader import get_device

from ...utils.enum_class import ImageType
from ...utils.models_download_utils import auto_download_and_get_model_root_path

from mineru_vl_utils import MinerUClient
from packaging import version


class ModelSingleton:
    _instance = None
    _models = {}

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_model(
        self,
        backend: str,
        model_path: str | None,
        server_url: str | None,
        **kwargs,
    ) -> MinerUClient:
        key = (backend, model_path, server_url)
        if key not in self._models:
            start_time = time.time()
            model = None
            processor = None
            vllm_llm = None
            vllm_async_llm = None
            batch_size = kwargs.get("batch_size", 0)  # for transformers backend only
            max_concurrency = kwargs.get("max_concurrency", 100)  # for http-client backend only
            http_timeout = kwargs.get("http_timeout", 600)  # for http-client backend only
            # 从kwargs中移除这些参数，避免传递给不相关的初始化函数
            for param in ["batch_size", "max_concurrency", "http_timeout"]:
                if param in kwargs:
                    del kwargs[param]
            if backend in ['transformers', 'vllm-engine', "vllm-async-engine", "mlx-engine"] and not model_path:
                model_path = auto_download_and_get_model_root_path("/","vlm")
                if backend == "transformers":
                    try:
                        from transformers import (
                            AutoProcessor,
                            Qwen2VLForConditionalGeneration,
                        )
                        from transformers import __version__ as transformers_version
                    except ImportError:
                        raise ImportError("Please install transformers to use the transformers backend.")

                    if version.parse(transformers_version) >= version.parse("4.56.0"):
                        dtype_key = "dtype"
                    else:
                        dtype_key = "torch_dtype"
                    device = get_device()
                    model = Qwen2VLForConditionalGeneration.from_pretrained(
                        model_path,
                        device_map={"": device},
                        **{dtype_key: "auto"},  # type: ignore
                    )
                    processor = AutoProcessor.from_pretrained(
                        model_path,
                        use_fast=True,
                    )
                    if batch_size == 0:
                        batch_size = set_default_batch_size()
                elif backend == "mlx-engine":
                    mlx_supported = is_mac_os_version_supported()
                    if not mlx_supported:
                        raise EnvironmentError("mlx-engine backend is only supported on macOS 13.5+ with Apple Silicon.")
                    try:
                        from mlx_vlm import load as mlx_load
                    except ImportError:
                        raise ImportError("Please install mlx-vlm to use the mlx-engine backend.")
                    model, processor = mlx_load(model_path)
                else:
                    if os.getenv('OMP_NUM_THREADS') is None:
                        os.environ["OMP_NUM_THREADS"] = "1"

                    if backend == "vllm-engine":
                        try:
                            import vllm
                            from mineru_vl_utils import MinerULogitsProcessor
                        except ImportError:
                            raise ImportError("Please install vllm to use the vllm-engine backend.")
                        if "gpu_memory_utilization" not in kwargs:
                            kwargs["gpu_memory_utilization"] = set_default_gpu_memory_utilization()
                        if "model" not in kwargs:
                            kwargs["model"] = model_path
                        if enable_custom_logits_processors() and ("logits_processors" not in kwargs):
                            kwargs["logits_processors"] = [MinerULogitsProcessor]
                        # 使用kwargs为 vllm初始化参数
                        vllm_llm = vllm.LLM(**kwargs)
                    elif backend == "vllm-async-engine":
                        try:
                            from vllm.engine.arg_utils import AsyncEngineArgs
                            from vllm.v1.engine.async_llm import AsyncLLM
                            from mineru_vl_utils import MinerULogitsProcessor
                        except ImportError:
                            raise ImportError("Please install vllm to use the vllm-async-engine backend.")
                        if "gpu_memory_utilization" not in kwargs:
                            kwargs["gpu_memory_utilization"] = set_default_gpu_memory_utilization()
                        if "model" not in kwargs:
                            kwargs["model"] = model_path
                        if enable_custom_logits_processors() and ("logits_processors" not in kwargs):
                            kwargs["logits_processors"] = [MinerULogitsProcessor]
                        # 使用kwargs为 vllm初始化参数
                        vllm_async_llm = AsyncLLM.from_engine_args(AsyncEngineArgs(**kwargs))
            self._models[key] = MinerUClient(
                backend=backend,
                model=model,
                processor=processor,
                vllm_llm=vllm_llm,
                vllm_async_llm=vllm_async_llm,
                server_url=server_url,
                batch_size=batch_size,
                max_concurrency=max_concurrency,
                http_timeout=http_timeout,
            )
            elapsed = round(time.time() - start_time, 2)
            logger.info(f"get {backend} predictor cost: {elapsed}s")
        return self._models[key]


def doc_analyze_with_images(
    images_list,
    pdf_doc,
    image_writer: DataWriter | None,
    predictor: MinerUClient | None = None,
    backend="transformers",
    model_path: str | None = None,
    server_url: str | None = None,
    **kwargs,
):
    if predictor is None:
        predictor = ModelSingleton().get_model(backend, model_path, server_url, **kwargs)

    images_pil_list = [image_dict["img_pil"] for image_dict in images_list]

    # infer_start = time.time()
    results = predictor.batch_two_step_extract(images=images_pil_list)
    # infer_time = round(time.time() - infer_start, 2)
    # logger.info(f"infer finished, cost: {infer_time}, speed: {round(len(results)/infer_time, 3)} page/s")

    middle_json = result_to_middle_json(results, images_list, pdf_doc, image_writer)
    return middle_json, results


def doc_analyze(
    pdf_bytes,
    image_writer: DataWriter | None,
    predictor: MinerUClient | None = None,
    backend="transformers",
    model_path: str | None = None,
    server_url: str | None = None,
    **kwargs,
):
    if predictor is None:
        predictor = ModelSingleton().get_model(backend, model_path, server_url, **kwargs)

    # load_images_start = time.time()
    images_list, pdf_doc = load_images_from_pdf(pdf_bytes, image_type=ImageType.PIL)
    images_pil_list = [image_dict["img_pil"] for image_dict in images_list]
    # load_images_time = round(time.time() - load_images_start, 2)
    # logger.info(f"load images cost: {load_images_time}, speed: {round(len(images_base64_list)/load_images_time, 3)} images/s")

    # infer_start = time.time()
    results = predictor.batch_two_step_extract(images=images_pil_list)
    # infer_time = round(time.time() - infer_start, 2)
    # logger.info(f"infer finished, cost: {infer_time}, speed: {round(len(results)/infer_time, 3)} page/s")

    middle_json = result_to_middle_json(results, images_list, pdf_doc, image_writer)
    return middle_json, results


def batch_doc_analyze(
        pdf_bytes_list,
        image_writer_list,
        predictor: MinerUClient | None = None,
        backend="transformers",
        model_path: str | None = None,
        server_url: str | None = None,
        **kwargs,
):
    if predictor is None:
        predictor = ModelSingleton().get_model(backend, model_path, server_url, **kwargs)

    # load_images_start = time.time()
    all_images_list = []
    all_pdf_docs = []
    images_count_per_pdf = []  # 记录每个PDF的图像数量
    pdf_processing_status = []  # 记录每个PDF的处理状态

    # 遍历所有PDF文档，加载图像并拼接
    for pdf_bytes in pdf_bytes_list:
        try:
            images_list, pdf_doc = load_images_from_pdf(pdf_bytes, image_type=ImageType.PIL)
            all_images_list.extend(images_list)
            all_pdf_docs.append(pdf_doc)
            images_count_per_pdf.append(len(images_list))
            pdf_processing_status.append(True)  # 标记为成功处理
        except Exception as e:
            # 捕获load_images_from_pdf异常，记录失败状态
            logger.warning(f"Failed to load images from PDF: {e}")
            # 不添加空列表到all_images_list，因为后面会通过images_count_per_pdf来正确处理
            all_pdf_docs.append(None)   # 添加None作为pdf_doc
            images_count_per_pdf.append(0)  # 图像数量为0
            pdf_processing_status.append(False)  # 标记为处理失败

    # 正确生成images_pil_list，只处理有效的图像
    images_pil_list = []
    for image_dict in all_images_list:
        if image_dict and isinstance(image_dict, dict) and "img_pil" in image_dict:
            images_pil_list.append(image_dict["img_pil"])

    # 如果没有有效的图像，直接返回空结果
    if not images_pil_list:
        return [None] * len(pdf_bytes_list), []

    # load_images_time = round(time.time() - load_images_start, 2)
    # logger.info(f"load images cost: {load_images_time}, speed: {round(len(images_base64_list)/load_images_time, 3)} images/s")

    # infer_start = time.time()
    results = predictor.batch_two_step_extract(images=images_pil_list)
    # infer_time = round(time.time() - infer_start, 2)
    # logger.info(f"infer finished, cost: {infer_time}, speed: {round(len(results)/infer_time, 3)} page/s")

    # 需要为每个PDF文档分别生成middle_json
    all_middle_json = []
    image_idx = 0

    for i, (pdf_doc, is_success) in enumerate(zip(all_pdf_docs, pdf_processing_status)):
        if not is_success or pdf_doc is None:
            # 对于处理失败的PDF，返回None
            all_middle_json.append(None)
            continue

        # 获取当前PDF的图像数量
        current_pdf_images_count = images_count_per_pdf[i]

        if current_pdf_images_count == 0:
            # 对于没有图像的PDF，返回None
            all_middle_json.append(None)
            continue

        # 获取当前PDF的图像列表和结果
        current_images_list = all_images_list[image_idx: image_idx + current_pdf_images_count]
        current_results = results[image_idx: image_idx + current_pdf_images_count]

        # 为当前PDF生成middle_json
        image_writer = image_writer_list[i] if i < len(image_writer_list) else None
        middle_json = result_to_middle_json(current_results, current_images_list, pdf_doc, image_writer)
        all_middle_json.append(middle_json)

        # 更新图像索引
        image_idx += current_pdf_images_count

    return all_middle_json, results


async def aio_doc_analyze(
    pdf_bytes,
    image_writer: DataWriter | None,
    predictor: MinerUClient | None = None,
    backend="transformers",
    model_path: str | None = None,
    server_url: str | None = None,
    **kwargs,
):
    if predictor is None:
        predictor = ModelSingleton().get_model(backend, model_path, server_url, **kwargs)

    # load_images_start = time.time()
    images_list, pdf_doc = load_images_from_pdf(pdf_bytes, image_type=ImageType.PIL)
    images_pil_list = [image_dict["img_pil"] for image_dict in images_list]
    # load_images_time = round(time.time() - load_images_start, 2)
    # logger.debug(f"load images cost: {load_images_time}, speed: {round(len(images_pil_list)/load_images_time, 3)} images/s")

    # infer_start = time.time()
    results = await predictor.aio_batch_two_step_extract(images=images_pil_list)
    # infer_time = round(time.time() - infer_start, 2)
    # logger.info(f"infer finished, cost: {infer_time}, speed: {round(len(results)/infer_time, 3)} page/s")
    middle_json = result_to_middle_json(results, images_list, pdf_doc, image_writer)
    return middle_json, results
