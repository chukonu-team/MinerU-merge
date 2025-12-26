#!/bin/bash

nohup python3 sample-local.py \
    --bucket_map_path /data/MinerU/demo/bucket_map.json \
    --bucket_range 100000-100100 \
    --input_dir /ssd/mnt/data \
    --output_dir ../output/sample \
    > ../logs/sample.log 2>&1 &
