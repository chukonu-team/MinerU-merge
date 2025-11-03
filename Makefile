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
batch-tasks:
	python3 api_server/api_manager.py batch-dir  /workspace/extracted_files/ --chunk-id 0001
report:
	python3 api_server/api_manager.py report
monitor:
	python3 api_server/api_manager.py monitor
download_chunk:
	python3 api_server/api_manager.py chunk-download  0001
process:
	python3 api_server/api_manager.py progress --chunk-id 0001
report_chunk:
	python3 api_server/api_manager.py report --chunk-id 0001
detailed-report:
	python3 api_server/api_manager.py detailed-report --chunk-id 0001 --output-dir reports/
show-table:
	python3 api_server/api_manager.py detailed-report --chunk-id 0001 --html --show-table --output-dir reports/