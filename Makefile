build-api-container:
	docker build -f api_server.dockerfile -t mineru-api-server .
build-origin-container:
	docker build -f docker/china/Dockerfile -t mineru:origin .
start-api-container:
	docker run -itd --name mineru-api-server \
		--gpus all \
		-p 8001:8001 \
		-v $(PWD):/workspace \
        mineru-api-server:latest bash
start-origin-container:
	docker run -d --name mineru-origin-server --gpus all  -p 8000:8000 \
        mineru:origin \
        /bin/bash -c "mineru-api --host 0.0.0.0 --port 8000"
start-server:
	bash api_server/start_server.sh
aaa:
	docker build -f docker/china/Dockerfile.multi_gpu -t mineru:multi_gpu .
bbb:
	docker rm mineru_multi_gpu
	docker run -d \
		--name mineru_multi_gpu \
		--gpus all \
		-p 8000:8000 \
		mineru:multi_gpu
health:
	python3 api_server/api_manager.py health
list:
	python3 api_server/api_manager.py list
list-by-chunk:
	python3 api_server/api_manager.py list --chunk-id 0001
batch-tasks:
	python3 api_server/api_manager.py batch-dir  /home/ubuntu/pdfs --chunk-id 0005
batch-process:
	python3 api_server/api_manager.py batch-process  /workspace/extracted_files/ result/ --chunk-id 0006
task-download:
	python3 api_server/api_manager.py task-download $(TASK_IDS) $(OUTPUT_DIR)
chunk-download:
	python3 api_server/api_manager.py chunk-download $(CHUNK_ID) $(OUTPUT_DIR)
clean-up:
	python3 api_server/api_manager.py cleanup --older-than-days 7 --dry-run
	python3 api_server/api_manager.py cleanup --cleanup-all
	python3 api_server/api_manager.py cleanup --chunk-id "0005"
demo-origin-parse:
	curl -X POST "http://localhost:8000/file_parse" \
		-H "accept: application/json" \
		-H "Content-Type: multipart/form-data" \
		-F "files=@/home/ubuntu/MinerU/demo/pdfs/demo1.pdf" \
		-F "output_dir=./output" \
		-F "lang_list=ch" \
		-F "lang_list=en" \
		-F "backend=vlm-vllm-async-engine" \
		-F "parse_method=auto" \
		-F "formula_enable=true" \
		-F "table_enable=true" \
		-F "return_md=true" \
		-F "return_middle_json=false" \
		-F "return_model_output=false" \
		-F "return_content_list=false" \
		-F "return_images=false" \
		-F "response_format_zip=false" \
		-F "start_page_id=0" \
		-F "end_page_id=99999"