import os
from transformers import Qwen2VLForConditionalGeneration, AutoTokenizer
from llmcompressor import oneshot
from llmcompressor.modifiers.quantization import QuantizationModifier

# 1. 设置路径
MODEL_PATH = "/opt/modelscope/hub/OpenDataLab/MinerU2___5-2509-1___2B"
QUANT_PATH = "./MinerU2_AQW_2B_FP8_Dynamic"

# 2. 【核心修复】手动加载模型对象
# 既然 oneshot 猜不对模型类，我们就自己加载
print(f"Loading model manually from: {MODEL_PATH}...")
model = Qwen2VLForConditionalGeneration.from_pretrained(
    MODEL_PATH,
    device_map="auto",
    torch_dtype="auto",
    trust_remote_code=True
)
from llmcompressor.modifiers.awq import AWQModifier
# 加载 tokenizer (为了最后一起保存)
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)

# 3. 定义配方
modifier = AWQModifier(
    targets="Linear", 
    scheme="FP8_DYNAMIC", 
    ignore=["visual", "lm_head"] 
)
recipe = [modifier]

# 4. 执行量化
print("Starting FP8 Dynamic quantization...")

# 将加载好的 model 对象传进去，而不是路径字符串
oneshot(
    model=model, 
    recipe=recipe,
    output_dir=QUANT_PATH,
    # 此时不需要 trust_remote_code 参数了，因为模型已经加载好了
)

# 5. 手动保存 Tokenizer (确保完整性)
print(f"Saving tokenizer to {QUANT_PATH}...")
tokenizer.save_pretrained(QUANT_PATH)

print(f"Done! Model saved to {QUANT_PATH}")