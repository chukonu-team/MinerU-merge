#!/bin/bash

work_dir=/root/wangshd/batch6

python3 split_key.py \
        --input $work_dir/batch_3.txt \
        --output $work_dir/vlm/chunk_keys \
        --num 10000 \
	--start 100000

#rclone delete houdutech:batch2/batch3/vlm/chunk_keys/

#rclone copy $work_dir/vlm/chunk_keys/ houdutech:batch2/batch6/vlm/chunk_keys/
