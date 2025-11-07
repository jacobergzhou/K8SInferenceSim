# Inference Simulator – Local Kubernetes Workflow

This project lets you simulate CPU-bound inference traffic on a Kind (Kubernetes in Docker) cluster. It ships with a FastAPI app, base Kubernetes manifests, environment-specific overlays, and a small async load-generator.

## Prerequisites

- Docker (required by Kind and for building the image)
- [`kind`](https://kind.sigs.k8s.io/)
- `kubectl`
- Python 3.11+ with `pip` for running `scripts/load.py` (`pip install aiohttp`)

Optional but convenient: GNU `make`, which wraps the common commands below.

## Workflow

### 1. Create the Kind cluster

```bash
make kind-up
```

The make target creates (or reuses) a cluster named `k8s-inference-sim`.

### 2. Build the simulator image

```bash
make image        # builds k8s-inference-sim:local via Dockerfile
```

### 3. Load the image into Kind

Kind nodes cannot see images from your host Docker daemon unless you push to a registry, so load it directly:

```bash
make kind-load
```

### 4. Deploy the stack

```bash
make deploy
```

This applies `k8s/overlays/dev`, which:

- Creates namespace `k8s-inference-sim`
- Prefixes resources with `dev-`
- Deploys the FastAPI app, Service, ConfigMap, and HPA
- Waits for the rollout of `dev-inference-sim`

Verify pods:

```bash
kubectl -n k8s-inference-sim get pods
kubectl -n k8s-inference-sim get hpa
```

### 5. Port-forward the Service

The base `Service` is `ClusterIP` only (internal to Kubernetes). To send traffic from your laptop, open a tunnel:

```bash
kubectl -n k8s-inference-sim port-forward svc/dev-inference-sim 8080:80
```

Leave this command running; it maps `localhost:8080` → Service port `80`, which in turn targets container port `8080`.

### 6. Generate load

In a second terminal, install the load tool dependencies once:

```bash
pip install --user aiohttp
```

Then run sustained traffic against `/infer`:

```bash
python scripts/load.py --host http://localhost:8080 --qps 30 --seconds 180
```

While it runs, watch pods scale:

```bash
kubectl -n k8s-inference-sim get pods -w
kubectl -n k8s-inference-sim get hpa
```

The HorizontalPodAutoscaler (`k8s/base/hpa.yaml`) targets 60% CPU. When sustained load pushes CPU above that threshold, it increases replicas (up to 10). When load drops, it scales back down.

### 7. Tear everything down

```bash
make undeploy      # remove the dev overlay resources
make kind-down     # delete the Kind cluster if you’re done
```

## Understanding the Port Flow

It’s easy to point the load script at the wrong place, so here’s the full path:

1. **Container:** `uvicorn` listens on port `8080` inside each pod (set in the `Dockerfile` and `Deployment`).
2. **Service:** `k8s/base/service.yaml` defines a `ClusterIP` Service that exposes **port 80** and forwards to **targetPort 8080** on matching pods. This IP exists only inside the cluster network.
3. **Your laptop:** When you run `scripts/load.py` locally, `http://localhost:8080` hits your own machine—not the cluster—unless you create a bridge.
4. **Port-forward:** `kubectl port-forward svc/dev-inference-sim 8080:80` opens that bridge by tunneling local port 8080 to the Service’s port 80 (and thus to the pods’ 8080). The terminal stays open because it’s actively holding the tunnel; stop it with Ctrl+C when you’re finished.

If you skip the port-forward (or equivalent exposure like Ingress/NodePort), the load generator will report failures and CPU usage will remain flat because the requests never reach Kubernetes. Changing the load script’s port won’t help until the Service is reachable from your machine.

## Troubleshooting

- **`kubectl rollout status deploy/inference-sim` fails:** Remember the dev overlay uses the prefix `dev-`; target `deploy/dev-inference-sim`.
- **`ImagePullBackOff`:** Make sure you ran `make kind-load` after building the image so the Kind nodes can see it.
- **`port-forward` errors about port 8080:** Use the `local:remote` form (`8080:80`). The Service only exposes port 80, but it routes to container port 8080 under the hood.
- **Load script says OK=0:** Verify port-forward is running and the script points to the forwarded localhost URL.

With those steps, you can reliably build the image, deploy to Kind, drive load, and watch the HPA in action.
