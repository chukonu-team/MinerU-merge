build-container:
	docker build -f api_server.dockerfile -t mineru-api-server .
start-container:
	docker run -itd --name mineru-api-server \
		--gpus all \
		-p 8001:8001 \
		-v $(PWD):/workspace \
        mineru-api-server:latest bash
start-server:
	bash api_server/start_server.sh

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