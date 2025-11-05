IMAGE?=k8s-inference-sim:local
NS?=k8s-inference-sim

kind-up:
	kind create cluster --name k8s-inference-sim || true

kind-down:
	kind delete cluster --name k8s-inference-sim || true

image:
	docker build -t $(IMAGE) .

kind-load:
	kind load docker-image $(IMAGE) --name k8s-inference-sim

deploy:
	kubectl apply -k k8s/overlays/dev
	kubectl -n $(NS) rollout status deploy/inference-sim --timeout=120s
	kubectl -n $(NS) get pods

undeploy:
	kubectl delete -k k8s/overlays/dev || true
