start-api-container:
	sudo docker run -itd \
		--gpus='"device=1"' \
		--network=host \
		-v /home/zz/MinerU-merge:/data/MinerU \
		-v /ssd/dataset/google:/data/google \
		-e "OMP_NUM_THREADS=3" \
		-e "MKL_NUM_THREADS=3" \
		-e "OPENBLAS_NUM_THREADS=3" \
		-e "PYTHONUNBUFFERED=1" \
		-e "BACKEND=vllm-engine" \
		-e "MINERU_MODEL_SOURCE=local" \
		-e "GPU_MEMORY_UTILIZATION=0.3" \
		-e "DEFAULT_BATCH_SIZE=100" \
		--name mineru-api-server \
		mineru:v2.6.4

run-scheduler:
	python3 tasks/scheduler.py > scheduler.log 2>&1
run-pipeline:
	python3 tasks/pipeline.py > pipeline.log 2>&1
profile-pipeline:
	ncu --set full -o pipeline_profile python3 tasks/pipeline.py > pipeline.log 2>&1
exportto-html:
	ncu-ui pipeline_profile.ncu-rep
profile-basic:
	ncu --set basics -o pipeline_profile_fast python3 tasks/pipeline.py  > pipeline_basic.log 2>&1
profile-pipeline-essential:
	ncu --metrics sm__pipe_tensor_cycles_active.avg.pct_of_peak:sat4_activity,sm__sass_thread_inst_executed_op_* -o pipeline_profile_essential python3 tasks/pipeline.py > pipeline.log 2>&1
profile-bandwidth:
	ncu --metrics dram__throughput.avg.pct_of_peak,dram__bytes_read.sum,dram__bytes_written.sum,lts__throughput.avg.pct_of_peak -o pipeline_profile_bandwidth python3 tasks/pipeline.py > pipeline_bandwidth.log 2>&1
monitor-gpu:
	nvidia-smi dmon -s puct -d 1
profile-nsys:
	nsys profile --trace=cuda,nvtx,osrt --force-overwrite=true -o pipeline_nsys python3 tasks/pipeline.py > pipeline_nsys.log 2>&1
profile-nsys-30s:
	nsys profile --trace=cuda,nvtx,osrt --duration=30 --force-overwrite=true -o pipeline_nsys_30s python3 tasks/pipeline.py > pipeline_nsys_30s.log 2>&1
feel:
	nsys profile \
	--trace=cuda,nvtx,osrt,cudnn,cublas \
	--gpu-metrics-devices=all \
	--cuda-memory-usage=true \
	--python-sampling=true \
	--output=pipeline_report \
	python3 tasks/pipeline.py > feel.log 2>&1
sfeel:
	nsys profile \
	--trace=cuda,nvtx,osrt,cudnn,cublas \
	--gpu-metrics-devices=all \
	--cuda-memory-usage=true \
	--python-sampling=true \
	--output=async_pipeline_report \
	python3 tasks/scheduler.py > sfeel.log 2>&1
parallel:
	python3 tasks/parallel.py -n 3 > parallel.log 2>&1