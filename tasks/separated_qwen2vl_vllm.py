"""
分离Qwen2-VL模型测试 (使用vLLM实现确定性输出)
确保与原始测试使用相同的推理引擎和参数
"""

import torch
import vllm
import numpy as np
from PIL import Image
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


class SeparatedQwen2VLTesterVLLM:
    """分离Qwen2-VL推理测试器 - 使用vLLM确保一致性"""

    def __init__(self, model_path: str, **vllm_kwargs):
        """
        初始化分离模型测试器（使用vLLM）

        Args:
            model_path: 模型路径
            **vllm_kwargs: vLLM参数
        """
        print("🔧 初始化分离Qwen2-VL模型 (vLLM)...")

        self.model_path = model_path

        # 设置种子
        set_seeds(42)

        # 使用与原始测试完全相同的vLLM配置
        print("📦 加载vLLM模型...")
        self.llm = vllm.LLM(
            model=model_path,
            seed=42,
            **vllm_kwargs
        )

        self.tokenizer = self.llm.get_tokenizer()

        # 获取processor用于处理图像
        from transformers import Qwen2VLProcessor
        self.processor = Qwen2VLProcessor.from_pretrained(model_path)

        print("✅ 分离模型初始化完成")

    def load_test_images(self) -> List[Image.Image]:
        """加载测试图像"""
        images = []
        image_dir = "test_images"

        if not os.path.exists(image_dir):
            raise FileNotFoundError(f"测试图像目录不存在: {image_dir}")

        # 加载现有图像
        for i in range(1, 4):
            img_path = f"{image_dir}/test_image_{i}.png"
            if os.path.exists(img_path):
                img = Image.open(img_path)
                images.append(img)

        print(f"✅ 加载了 {len(images)} 张测试图像")
        return images

    def get_test_prompts(self) -> List[str]:
        """获取测试提示词"""
        prompts = [
            "请详细描述这张图片的内容，包括颜色、形状和文字。",
            "这张图片的主要颜色是什么？",
            "图片中有什么几何形状？",
            "如果这张图片是一个logo，它可能代表什么？",
            "用一句话总结这张图片的特征。",
        ]
        return prompts

    def run_inference_tests(self, images: List[Image.Image], prompts: List[str]) -> Dict[str, Any]:
        """运行分离模型推理测试（使用vLLM）"""
        print("🧪 运行分离模型推理测试 (vLLM)...")

        results = {
            "model_type": "separated_vllm",
            "model_info": {
                "seed": 42,
                "num_images": len(images),
                "num_prompts": len(prompts),
                "engine": "vllm",
                "architecture": "vit_encoder + llm_generator (vllm)"
            },
            "tests": []
        }

        # 使用与原始测试完全相同的采样参数（贪婪解码）
        sampling_params = vllm.SamplingParams(
            temperature=0.0,  # 完全确定性（贪婪解码）
            top_p=1.0,  # 不使用nucleus sampling
            max_tokens=150,
            seed=42,
            stop_token_ids=None
        )

        # 对每个图像和提示词组合运行测试
        for img_idx, image in enumerate(images):
            print(f"\n处理图片 {img_idx+1}/{len(images)}")

            for prompt_idx, prompt in enumerate(prompts):
                print(f"  测试提示词 {prompt_idx+1}/{len(prompts)}: {prompt[:30]}...")

                try:
                    # 使用processor处理输入（与原始测试相同）
                    conversation = [
                        {
                            "role": "user",
                            "content": [
                                {"type": "image", "image": image},
                                {"type": "text", "text": prompt}
                            ]
                        }
                    ]

                    # 应用对话模板
                    text = self.processor.apply_chat_template(
                        conversation,
                        tokenize=False,
                        add_generation_prompt=True
                    )

                    # 使用vLLM生成（与原始测试完全相同的方式）
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
                    print(f"    ✓ 生成文本长度: {len(generated_text)} 字符")

                except Exception as e:
                    print(f"    ❌ 推理失败: {str(e)}")
                    test_result = {
                        "image_id": img_idx + 1,
                        "prompt_id": prompt_idx + 1,
                        "prompt": prompt,
                        "generated_text": f"ERROR: {str(e)}",
                        "output_hash": "error",
                        "token_count": 0,
                        "finish_reason": "error"
                    }
                    results["tests"].append(test_result)

        print("\n✅ 分离模型推理测试完成")
        return results

    def save_results(self, results: Dict[str, Any], filename: str = "separated_vllm_results.json"):
        """保存测试结果"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"💾 结果已保存到: {filename}")

    def run_full_test(self):
        """运行完整测试流程"""
        print("🚀 开始分离Qwen2-VL推理测试 (vLLM)...")

        # 加载测试数据
        images = self.load_test_images()
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
        print("分离模型测试摘要 (vLLM)")
        print("="*60)
        print(f"模型类型: {results['model_type']}")
        print(f"推理引擎: {results['model_info']['engine']}")
        print(f"架构: {results['model_info']['architecture']}")
        print(f"种子: {results['model_info']['seed']}")
        print(f"测试图片数: {results['model_info']['num_images']}")
        print(f"测试提示词数: {results['model_info']['num_prompts']}")
        print(f"总测试用例: {len(results['tests'])}")

        # 统计成功和失败
        successful = [t for t in results['tests'] if t['output_hash'] != 'error']
        failed = [t for t in results['tests'] if t['output_hash'] == 'error']

        print(f"成功: {len(successful)}, 失败: {len(failed)}")

        # 显示部分结果示例
        print("\n示例结果:")
        for i, test in enumerate(successful[:3]):
            print(f"\n测试 {i+1}:")
            print(f"  图片ID: {test['image_id']}")
            print(f"  提示词: {test['prompt'][:50]}...")
            print(f"  生成长度: {len(test['generated_text'])} 字符")
            print(f"  输出哈希: {test['output_hash'][:16]}...")
            print(f"  生成文本: {test['generated_text'][:80]}...")


def compare_with_original(original_file: str = "original_results.json",
                         separated_file: str = "separated_vllm_results.json"):
    """对比原始和分离模型的结果"""
    print("\n" + "="*80)
    print("结果一致性对比分析 (vLLM vs vLLM)")
    print("="*80)

    # 加载结果
    try:
        with open(original_file, 'r', encoding='utf-8') as f:
            original_results = json.load(f)
        print(f"✅ 已加载原始结果: {original_file}")
    except FileNotFoundError:
        print(f"❌ 未找到原始结果文件: {original_file}")
        return

    try:
        with open(separated_file, 'r', encoding='utf-8') as f:
            separated_results = json.load(f)
        print(f"✅ 已加载分离结果: {separated_file}")
    except FileNotFoundError:
        print(f"❌ 未找到分离结果文件: {separated_file}")
        return

    # 对比分析
    original_tests = {(t["image_id"], t["prompt_id"]): t for t in original_results["tests"]}
    separated_tests = {(t["image_id"], t["prompt_id"]): t for t in separated_results["tests"]}

    print(f"\n📊 对比统计:")
    print(f"原始模型测试数: {len(original_tests)}")
    print(f"分离模型测试数: {len(separated_tests)}")

    # 详细对比
    exact_matches = 0
    hash_matches = 0
    length_differences = []

    comparison_results = []

    for key in original_tests:
        if key not in separated_tests:
            print(f"⚠️ 分离模型缺失测试用例: 图片{key[0]}, 提示词{key[1]}")
            continue

        orig = original_tests[key]
        sep = separated_tests[key]

        # 跳过错误的测试
        if orig.get("output_hash") == "error" or sep.get("output_hash") == "error":
            continue

        # 文本完全一致
        text_match = orig["generated_text"] == sep["generated_text"]
        # 哈希一致
        hash_match = orig["output_hash"] == sep["output_hash"]
        # 长度差异
        length_diff = abs(len(orig["generated_text"]) - len(sep["generated_text"]))

        if text_match:
            exact_matches += 1
        if hash_match:
            hash_matches += 1

        length_differences.append(length_diff)

        if not text_match:
            comparison_results.append({
                "image_id": key[0],
                "prompt_id": key[1],
                "prompt": orig["prompt"][:50] + "...",
                "text_match": text_match,
                "hash_match": hash_match,
                "length_diff": length_diff,
                "original_text": orig["generated_text"][:100] + "...",
                "separated_text": sep["generated_text"][:100] + "..."
            })

    # 统计结果
    valid_tests = len(original_tests)
    if valid_tests > 0:
        exact_match_rate = (exact_matches / valid_tests) * 100
        hash_match_rate = (hash_matches / valid_tests) * 100
        avg_length_diff = sum(length_differences) / len(length_differences) if length_differences else 0

        print(f"\n📈 一致性分析结果:")
        print(f"有效测试用例: {valid_tests}")
        print(f"✅ 完全匹配率: {exact_match_rate:.2f}% ({exact_matches}/{valid_tests})")
        print(f"✅ 哈希匹配率: {hash_match_rate:.2f}% ({hash_matches}/{valid_tests})")
        print(f"📏 平均长度差异: {avg_length_diff:.2f} 字符")

        # 显示不匹配的情况
        if exact_matches < valid_tests:
            print(f"\n⚠️ 发现 {valid_tests - exact_matches} 个不匹配的案例:")
            for i, comp in enumerate(comparison_results[:5], 1):
                print(f"\n案例 {i} - 图{comp['image_id']}提示{comp['prompt_id']}:")
                print(f"  提示词: {comp['prompt']}")
                print(f"  原始: {comp['original_text']}")
                print(f"  分离: {comp['separated_text']}")
                print(f"  长度差异: {comp['length_diff']} 字符")

        # 结论
        if exact_match_rate == 100:
            print("\n🎉🎉🎉 完美！分离推理与原始推理100%一致！")
        elif exact_match_rate > 95:
            print("\n🎉 优秀！分离推理与原始推理高度一致！")
        elif exact_match_rate > 80:
            print("\n✅ 良好！分离推理与原始推理基本一致")
        else:
            print("\n⚠️ 仍存在差异，可能需要进一步调试")


def main():
    """主测试函数"""

    # 配置模型路径
    MODEL_PATH = "Qwen/Qwen2-VL-2B-Instruct"

    try:
        # 初始化分离测试器（使用vLLM）
        tester = SeparatedQwen2VLTesterVLLM(
            model_path=MODEL_PATH,
            tensor_parallel_size=1,
            gpu_memory_utilization=0.8,
            enforce_eager=True  # 与原始测试相同
        )

        # 运行完整测试
        results = tester.run_full_test()

        print("\n🎉 分离模型测试完成！")

        # 自动进行结果对比
        print("\n🔍 开始对比原始和分离模型结果...")
        compare_with_original()

    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
