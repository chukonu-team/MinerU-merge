import asyncio
import os
import time
import glob
from mineru.utils.pdf_reader import bytes_to_pil
from mineru.utils.pdf_image_tools import load_images_from_pdf
from mineru.cli.common import convert_pdf_bytes_to_bytes_by_pypdfium2
from mineru.utils.enum_class import ImageType

from tasks.util_layout_dect import MinerUSamplingParams, prepare_for_layout
from tasks.utils_main import (
    aio_predict,
    load_engine,
    parse_layout_output,
    prepare_for_extract,
    post_process,
    self_post_process,
)

# ==============================
# Helpers
# ==============================

def load_pdfs(page_limit):
    from dotenv import load_dotenv
    load_dotenv()
    """Loads PDF bytes into memory (Same as original logic)."""
    pdf_dir = os.environ.get("PDF_DIR", "/app/google")
    # Ensure directory exists or handle error
    if not os.path.exists(pdf_dir):
        print(f"[WARN] Directory {pdf_dir} not found.")
        return [], [], []
        
    pdf_files = glob.glob(os.path.join(pdf_dir, "*.pdf"))[:page_limit]
    
    all_bytes = []
    counts = []
    files_map = [] # To track which file belongs to which page

    print("Loading PDFs...")
    for pdf_path in pdf_files:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        new_pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes)
        imgs, _ = load_images_from_pdf(new_pdf_bytes, image_type=ImageType.BYTES)
        
        page_bytes = [x["img_bytes"] for x in imgs]
        all_bytes.extend(page_bytes)
        counts.append(len(page_bytes))
        
    return all_bytes, pdf_files, counts

def get_page_indices(counts):
    """Maps global image index to (pdf_index, page_index)."""
    indices = []
    for pdf_idx, count in enumerate(counts):
        for page_idx in range(count):
            indices.append((pdf_idx, page_idx))
    return indices

# ==============================
# Async Pipeline
# ==============================

async def run_cpu_bound(func, *args):
    """Run CPU heavy tasks in a separate thread to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)

def _cpu_process_layout_data(img_bytes, layout_output):
    """CPU intensive: Parse layout output and crop images."""
    pil_img = bytes_to_pil(img_bytes)
    blocks_list = parse_layout_output(layout_output)
    
    # Prepare crops for extraction
    # Note: prepare_for_extract returns (block_images, prompts, params, indices)
    # We pass blocks_list to crop all blocks
    block_images, prompts, params, indices = prepare_for_extract(pil_img, blocks_list)
    
    return blocks_list, block_images, prompts, params, indices

async def process_single_page(
    engine, tokenizer, 
    img_bytes, 
    global_idx, 
    pdf_info, 
    sem_layout,
    sem_extract
):
    """
    Full pipeline for a single page: 
    1. Layout Detect
    2. Crop (CPU)
    3. Content Extract (Parallel)
    """
    pdf_idx, page_idx = pdf_info
    
    try:
        # --- Stage 1: Layout Detection ---
        # Convert bytes to PIL (CPU bound)
        pil_img = await run_cpu_bound(bytes_to_pil, img_bytes)
        layout_input_img = await run_cpu_bound(prepare_for_layout, pil_img)
        
        # Limit concurrent layout requests if necessary, though VLLM handles batching best if we flood it
        async with sem_layout:
            # print(f"[{global_idx}] Start Layout...")
            layout_output = await aio_predict(
                engine, 
                tokenizer, 
                layout_input_img, 
                "\nLayout Detection:", 
                MinerUSamplingParams()
            )

        # --- Stage 2: Post-Processing Layout (CPU) ---
        # This is where the old code often froze. We move it off the event loop.
        blocks_list, block_images, prompts, params, indices = await run_cpu_bound(
            _cpu_process_layout_data, img_bytes, layout_output
        )

        # --- Stage 3: Content Extraction ---
        if not block_images:
            # No content to extract
            result = post_process(blocks_list)
            return result

        # We can fire all extraction requests for this page in parallel
        extract_tasks = []
        
        async def extract_one_block(b_img, b_prompt, b_param, b_idx):
            async with sem_extract:
                content = await aio_predict(engine, tokenizer, b_img, b_prompt, b_param)
                blocks_list[indices[b_idx]].content = content

        for i in range(len(block_images)):
            extract_tasks.append(
                extract_one_block(block_images[i], prompts[i], params[i], i)
            )
        
        # Wait for all blocks in this page to be extracted
        await asyncio.gather(*extract_tasks)

        # Finalize
        result = post_process(blocks_list)
        print(f"[{global_idx}] Finished (Blocks: {len(block_images)})")
        return result

    except Exception as e:
        print(f"[ERROR] Page {global_idx} (PDF {pdf_idx} Page {page_idx}) failed: {e}")
        import traceback
        traceback.print_exc()
        return []

# ==============================
# Main
# ==============================

async def main_func(save_dir="./result/one_tasks/async_scheduler_save"):
    # Hardware settings
    os.environ["OMP_NUM_THREADS"] = "4" # Don't set too low, but keep away from all cores
    
    # 1. Load Engine
    print("Initializing Engine...")
    engine, tokenizer = await load_engine()
    
    # 2. Load Data
    b1 = time.time()
    # Load first 2 PDFs (as per your example)
    all_images_bytes, pdf_files, counts = load_pdfs(4) 
    page_indices = get_page_indices(counts)
    b2 = time.time()
    print(f"Data loaded in {b2-b1:.2f}s. Total pages: {len(all_images_bytes)}")

    # 3. Setup Concurrency
    # sem_layout: Controls how many pages are doing Layout Detection simultaneously.
    # High number = better batching, but higher VRAM usage.
    sem_layout = asyncio.Semaphore(32) 
    
    # sem_extract: Controls how many small image blocks are being recognized simultaneously.
    # Can be higher as inputs are smaller.
    sem_extract = asyncio.Semaphore(64) 

    start_time = time.time()

    # 4. Create Tasks
    tasks = []
    total = len(all_images_bytes)
    
    for idx in range(total):
        task = asyncio.create_task(
            process_single_page(
                engine, 
                tokenizer, 
                all_images_bytes[idx], 
                idx, 
                page_indices[idx], 
                sem_layout,
                sem_extract
            )
        )
        tasks.append(task)

    # 5. Execute Pipeline
    print(f"Started processing {total} pages...")
    results = await asyncio.gather(*tasks)
    
    end_time = time.time()

    # 6. Formatting Output
    results_with_metadata = []
    for i, result in enumerate(results):
        pdf_idx, page_idx = page_indices[i]
        results_with_metadata.append({
            'result': result,
            'pdf_idx': pdf_idx,
            'page_idx': page_idx,
            'pdf_path': pdf_files[pdf_idx]
        })

    # 7. Save
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    self_post_process(pdf_files, results_with_metadata, save_dir)

    print("======================================================")
    print(f"Total Pages: {total}")
    print(f"Total Time: {end_time - start_time:.2f}s")
    if total > 0:
        print(f"Speed: {total / (end_time - start_time):.2f} page/s")
    print("======================================================")

if __name__ == "__main__":
    asyncio.run(main_func())