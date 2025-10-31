build-container:
	docker build -f api_server.dockerfile -t mineru-api-server .
start-container:
	docker run -itd --name mineru-api-server \
		--gpus all \
		-v $(PWD):/workspace \
        mineru-api-server:latest bash
start-server:
	bash api_server/start_server.sh
health:
	python3 api_server/api_manager.py health
list:
	python3 api_server/api_manager.py list
batch-tasks:
	python3 api_server/api_manager.py batch-dir  /workspace/extracted_files/ --chunk-id 0001