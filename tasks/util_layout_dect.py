from PIL import Image
from dataclasses import dataclass
from multiprocessing import Pool, cpu_count
from typing import Optional

layout_image_size = (1036, 1036)

def get_rgb_image(image: Image.Image) -> Image.Image:
    if image.mode == "P":
        image = image.convert("RGBA")
    if image.mode != "RGB":
        image = image.convert("RGB")
    return image

def prepare_for_layout(image: Image.Image) -> Image.Image:
    image = get_rgb_image(image)
    image = image.resize(layout_image_size, Image.Resampling.BICUBIC)
    return image

def batch_prepare_for_layout(
    images: list[Image.Image],
    num_workers: Optional[int] = None,
) -> list[Image.Image]:
    """使用多进程批量预处理图像

    Args:
        images: 图像列表
        num_workers: 进程数，默认使用 CPU 核心数

    Returns:
        处理后的图像列表
    """
    if num_workers is None:
        num_workers = cpu_count()

    if len(images) == 0:
        return []

    if num_workers <= 1 or len(images) == 1:
        return [prepare_for_layout(im) for im in images]

    with Pool(processes=num_workers) as pool:
        return pool.map(prepare_for_layout, images)

@dataclass
class SamplingParams:
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    presence_penalty: float | None = None  # not supported by hf
    frequency_penalty: float | None = None  # not supported by hf
    repetition_penalty: float | None = None
    no_repeat_ngram_size: int | None = None
    max_new_tokens: int | None = None

class MinerUSamplingParams(SamplingParams):
    def __init__(
        self,
        temperature: float | None = 0.0,
        top_p: float | None = 0.01,
        top_k: int | None = 1,
        presence_penalty: float | None = 0.0,
        frequency_penalty: float | None = 0.0,
        repetition_penalty: float | None = 1.0,
        no_repeat_ngram_size: int | None = 100,
        max_new_tokens: int | None = None,
    ):
        super().__init__(
            temperature,
            top_p,
            top_k,
            presence_penalty,
            frequency_penalty,
            repetition_penalty,
            no_repeat_ngram_size,
            max_new_tokens,
        )

