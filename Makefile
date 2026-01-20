run-pipeline:
	/home/ubuntu/MinerU-merge/venv/bin/python demo/demo.py 
run-vlm:
	/home/ubuntu/MinerU-merge/venv/bin/python demo/vlm.py 
run-consumer:
	/home/ubuntu/MinerU-merge/venv/bin/python demo/consumer.py --pdf-dir /home/ubuntu/MinerU-merge/demo/pdfs --output-dir /home/ubuntu/MinerU-merge/demo/output
start-api-container:
	docker run --privileged -itd --name mineru-api-server \
		--gpus all \
		-p 8001:8001 \
		-v /home/ubuntu/MinerU-merge:/data/MinerU \
		-v /home/ubuntu/articles:/data/articles \
        mineru-api-server:latest bash