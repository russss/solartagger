deploy:
	docker build . -t ghcr.io/russss/solartagger:latest
	docker push ghcr.io/russss/solartagger:latest
