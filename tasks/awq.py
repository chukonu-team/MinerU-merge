from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer

from llmcompressor import oneshot
from llmcompressor.modifiers.awq import AWQModifier
from llmcompressor.utils import dispatch_for_generation
import os
from transformers import Qwen2VLForConditionalGeneration, AutoTokenizer
from llmcompressor import oneshot
from llmcompressor.modifiers.quantization import QuantizationModifier
from llmcompressor.modifiers.awq import AWQModifier
# 1. 设置路径
MODEL_PATH = "/opt/modelscope/hub/OpenDataLab/MinerU2___5-2509-1___2B"
QUANT_PATH = "./MinerU2_2B_AWQ_FP8_Dynamic"

model = Qwen2VLForConditionalGeneration.from_pretrained(
    MODEL_PATH,
    device_map="auto",
    torch_dtype="auto",
    trust_remote_code=True
)

# 加载 tokenizer (为了最后一起保存)
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)


# Configure the quantization algorithm to run.
recipe = [
    AWQModifier(
        ignore=["lm_head"], scheme="FP8_BLOCK", targets=["Linear"], duo_scaling="both"
    ),
]

# Apply algorithms.
oneshot(
    model=model,
    recipe=recipe,
    output_dir=QUANT_PATH,
)
tokenizer.save_pretrained(QUANT_PATH)
