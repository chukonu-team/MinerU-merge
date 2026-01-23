"""
原始Qwen2-VL模型测试 (完整推理)
用于对比验证分离推理的一致性
"""

import torch
import vllm
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import json
import hashlib
from typing import List, Dict, Any
import os

# 设置随机种子确保结果可复现
def set_seeds(seed: int = 42):
    """设置所有随机种子"""
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    # vLLM的随机种子通过sampling_params设置

class OriginalQwen2VLTester:
    """原始Qwen2-VL完整推理测试器"""

    def __init__(self, model_path: str, **vllm_kwargs):
        """
        初始化原始模型测试器

        Args:
            model_path: 模型路径
            **vllm_kwargs: vLLM参数
        """
        print("🔥 初始化原始Qwen2-VL模型...")

        # 设置种子
        set_seeds(42)

        # 初始化完整的vLLM实例
        self.llm = vllm.LLM(
            model=model_path,
            seed=42,  # vLLM种子
            **vllm_kwargs
        )

        self.tokenizer = self.llm.get_tokenizer()
        print("✅ 原始模型初始化完成")

    def create_test_images(self) -> List[Image.Image]:
        """创建标准测试图像"""
        images = []

        # 图像1: 红色正方形
        img1 = Image.new('RGB', (336, 336), color='red')
        draw1 = ImageDraw.Draw(img1)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 24)
        except:
            font = ImageFont.load_default()
        draw1.text((50, 150), "RED SQUARE", fill='white', font=font)
        images.append(img1)

        # 图像2: 蓝色圆形
        img2 = Image.new('RGB', (336, 336), color='lightblue')
        draw2 = ImageDraw.Draw(img2)
        draw2.ellipse([68, 68, 268, 268], fill='blue')
        draw2.text((120, 150), "BLUE", fill='white', font=font)
        images.append(img2)

        # 图像3: 彩色条纹
        img3 = Image.new('RGB', (336, 336), color='white')
        draw3 = ImageDraw.Draw(img3)
        colors = ['red', 'orange', 'yellow', 'green', 'blue', 'purple']
        for i, color in enumerate(colors):
            y = i * 56
            draw3.rectangle([0, y, 336, y+56], fill=color)
        images.append(img3)

        # 保存测试图像
        os.makedirs("test_images", exist_ok=True)
        for i, img in enumerate(images):
            img.save(f"test_images/test_image_{i+1}.png")

        print(f"✅ 创建了 {len(images)} 张测试图像")
        return images

    def get_test_prompts(self) -> List[str]:
        """获取标准测试提示词"""
        prompts = [
            "请详细描述这张图片的内容，包括颜色、形状和文字。",
            "这张图片的主要颜色是什么？",
            "图片中有什么几何形状？",
            "如果这张图片是一个logo，它可能代表什么？",
            "用一句话总结这张图片的特征。",
        ]
        return prompts

    def run_inference_tests(self, images: List[Image.Image], prompts: List[str]) -> Dict[str, Any]:
        """运行原始模型推理测试"""
        print("🧪 运行原始模型推理测试...")

        results = {
            "model_type": "original",
            "model_info": {
                "seed": 42,
                "num_images": len(images),
                "num_prompts": len(prompts)
            },
            "tests": []
        }

        # 固定的生成参数确保完全一致性（贪婪解码）
        sampling_params = vllm.SamplingParams(
            temperature=0.0,  # 完全确定性（贪婪解码）
            top_p=1.0,  # 不使用nucleus sampling
            max_tokens=150,
            seed=42,  # 设置种子（贪婪解码下不需要，但保留）
            stop_token_ids=None
        )

        # 需要使用processor处理图像
        from transformers import Qwen2VLProcessor
        processor = Qwen2VLProcessor.from_pretrained(self.llm.llm_engine.model_config.model)

        for img_idx, image in enumerate(images):
            for prompt_idx, prompt in enumerate(prompts):
                print(f"  测试图片 {img_idx+1}/{len(images)}, 提示词 {prompt_idx+1}/{len(prompts)}")

                # 使用processor处理输入
                conversation = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "image": image},
                            {"type": "text", "text": prompt}
                        ]
                    }
                ]

                # 处理对话
                text = processor.apply_chat_template(
                    conversation,
                    tokenize=False,
                    add_generation_prompt=True
                )

                # 处理图像和文本
                inputs = processor(
                    text=text,
                    images=[image],
                    return_tensors="pt"
                )

                # 提取multimodal数据 - 需要将tensor转换为正确的格式
                mm_data = {}
                if "pixel_values" in inputs:
                    mm_data["pixel_values"] = inputs["pixel_values"]
                if "image_grid_thw" in inputs:
                    mm_data["image_grid_thw"] = inputs["image_grid_thw"]

                # 执行推理 - 使用正确的vLLM API传递多模态数据
                from vllm.inputs import TextPrompt
                prompt_input = TextPrompt(
                    prompt=text,
                    multi_modal_data={"image": image}
                )

                outputs = self.llm.generate(
                    prompt_input,
                    sampling_params=sampling_params
                )

                # 提取结果
                generated_text = outputs[0].outputs[0].text.strip()

                # 计算输出哈希用于对比
                output_hash = hashlib.md5(generated_text.encode()).hexdigest()

                test_result = {
                    "image_id": img_idx + 1,
                    "prompt_id": prompt_idx + 1,
                    "prompt": prompt,
                    "generated_text": generated_text,
                    "output_hash": output_hash,
                    "token_count": len(self.tokenizer.encode(generated_text)),
                    "finish_reason": outputs[0].outputs[0].finish_reason
                }

                results["tests"].append(test_result)
                print(f"    生成文本长度: {len(generated_text)} 字符")

        print("✅ 原始模型推理测试完成")
        return results

    def save_results(self, results: Dict[str, Any], filename: str = "original_results.json"):
        """保存测试结果"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"💾 结果已保存到: {filename}")

    def run_full_test(self):
        """运行完整测试流程"""
        print("🚀 开始原始Qwen2-VL完整推理测试...")

        # 创建测试数据
        images = self.create_test_images()
        prompts = self.get_test_prompts()

        # 运行推理测试
        results = self.run_inference_tests(images, prompts)

        # 保存结果
        self.save_results(results)

        # 显示摘要
        self.print_summary(results)

        return results

    def print_summary(self, results: Dict[str, Any]):
        """打印测试摘要"""
        print("\n" + "="*60)
        print("原始模型测试摘要")
        print("="*60)
        print(f"模型类型: {results['model_type']}")
        print(f"种子: {results['model_info']['seed']}")
        print(f"测试图片数: {results['model_info']['num_images']}")
        print(f"测试提示词数: {results['model_info']['num_prompts']}")
        print(f"总测试用例: {len(results['tests'])}")

        # 显示部分结果示例
        print("\n示例结果:")
        for i, test in enumerate(results['tests'][:3]):
            print(f"\n测试 {i+1}:")
            print(f"  图片ID: {test['image_id']}")
            print(f"  提示词: {test['prompt'][:50]}...")
            print(f"  生成长度: {len(test['generated_text'])} 字符")
            print(f"  输出哈希: {test['output_hash'][:16]}...")
            print(f"  生成文本: {test['generated_text'][:100]}...")


def main():
    """主测试函数"""

    # 配置模型路径 - 请根据实际情况修改
    MODEL_PATH = "Qwen/Qwen2-VL-2B-Instruct"

    try:
        # 初始化测试器
        tester = OriginalQwen2VLTester(
            model_path=MODEL_PATH,
            tensor_parallel_size=1,
            gpu_memory_utilization=0.8,
            enforce_eager=True  # 确保结果一致性
        )

        # 运行完整测试
        results = tester.run_full_test()

        print("\n🎉 原始模型测试完成！")
        print("请继续运行分离模型测试 (separated_qwen2vl_test.py) 进行对比")

    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()