# Run a crawl in Google Cloud Platform

Documentation and scripts to launch an OpenWPM crawl on a Kubernetes cluster on GCP GKE.

## Prerequisites

- Access to GCP and the ability to provision resources in a GCP project
- [Google SDK](https://cloud.google.com/sdk/) installed locally
  - This will allow us to provision resources from CLI
- [Docker](https://hub.docker.com/search/?type=edition&offering=community)
  - We will use this to build the OpenWPM docker container
- A GCP Project setup, referred to below as `$PROJECT`
- Visit [GCP Kubernetes Engine API](https://console.cloud.google.com/apis/api/container.googleapis.com/overview) to enable the API.
  - You may need to set the Billing account.

For the remainder of these instructions, you are assumed to be in the `deployment/gcp/` folder, and you should have the following env vars set to the GCP project you're using as well as a prefix to identify your resources within that project (e.g., your username):

```bash
export PROJECT="foo-sandbox"
export CRAWL_PREFIX="foo"
```

## (One time) Provision GCP Resources

### Configure the GCP Project

- `gcloud auth login` to authenticate with GCP.
- `gcloud config set project $PROJECT` to the project that was created.
- `gcloud config set compute/zone us-central1-f` to the default region you want resources to be provisioned.
  - [GCP Regions](https://cloud.google.com/compute/docs/regions-zones/) for current list of regions.
- `gcloud components install kubectl`

### Setup GKE Cluster

The following command will create a zonal GKE cluster with [n1-highcpu-16](https://cloud.google.com/compute/all-pricing) nodes ($0.5672/node/h) with [IP-Alias enabled](https://cloud.google.com/kubernetes-engine/docs/how-to/alias-ips#creating_a_new_cluster_with_ip_aliases) (makes it a bit easier to connect to managed Redis instances from the cluster).

You may want to adjust fields within `./start_gke_cluster.sh` where appropriate such as:

- num-nodes, min-nodes, max-nodes (for a large crawl you may want up to 15 nodes, this is different than the number of pods which is specificed by the parallelism field in the crawl.yaml - one node can host multiple pods)
- [machine-type](https://cloud.google.com/compute/docs/instances/specify-min-cpu-platform)
- See the [GKE Quickstart](https://cloud.google.com/kubernetes-engine/docs/quickstart) guide and [cluster create](https://cloud.google.com/sdk/gcloud/reference/container/clusters/create) documentation.

```bash
./start_gke_cluster.sh $CRAWL_PREFIX-cluster
```

Note: For testing, you can use [preemptible](https://cloud.google.com/preemptible-vms/) nodes ($0.1200/node/h) instead:

```bash
./start_gke_cluster.sh $CRAWL_PREFIX-cluster --preemptible
```

### Fetch kubernetes cluster credentials for use with `kubectl`

```bash
gcloud container clusters get-credentials $CRAWL_PREFIX-cluster
```

This allows subsequent `kubectl` commands to interact with our cluster (using the context `gke_{PROJECT}_{ZONE}_{CLUSTER_NAME}`)

## (Optional) Configure sentry credentials

Set the Sentry DSN as a kubectl secret (change `foo` below):

```bash
kubectl create secret generic sentry-config \
--from-literal=sentry_dsn=foo
```

To run crawls without Sentry, remove the following from the crawl config after it has been generated below:

```bash
        - name: SENTRY_DSN
          valueFrom:
            secretKeyRef:
              name: sentry-config
              key: sentry_dsn
```

## (Optional) Build and push Docker image to GCR

If one of [the pre-built OpenWPM Docker images](https://hub.docker.com/r/openwpm/openwpm/tags) are not sufficient:

```bash
cd path/to/OpenWPM
docker build -t gcr.io/$PROJECT/$CRAWL_PREFIX-openwpm .
cd -
gcloud auth configure-docker
docker push gcr.io/$PROJECT/$CRAWL_PREFIX-openwpm
```

Remember to change the `crawl.yaml` to point to `image: gcr.io/$PROJECT/$CRAWL_PREFIX-openwpm`.

## Deploy the redis server which we use for the work queue

Launch a 1GB Basic tier Google Cloud Memorystore for Redis instance ($0.049/GB/hour):

```bash
gcloud redis instances create $CRAWL_PREFIX-redis --size=1 --region=us-central1 --redis-version=redis_4_0
```

Launch a temporary redis-box pod deployed to the cluster which we use to interact with the above Redis instance:

```bash
kubectl apply -f redis-box.yaml
```

Use the following output:

```bash
gcloud redis instances describe $CRAWL_PREFIX-redis --region=us-central1
```

... to set the corresponding env var:

```bash
export REDIS_HOST=10.0.0.3
```

(See https://cloud.google.com/memorystore/docs/redis/connecting-redis-instance for more information.)

## Adding sites to be crawled to the queue

Create a comma-separated site list as per:

```bash
echo "1,http://www.example.com
2,http://www.example.org
3,http://www.princeton.edu
4,http://citp.princeton.edu/?foo='bar" > site_list.csv

../load_site_list_into_redis.sh crawl-queue site_list.csv 
```

(Optional) To load Alexa Top 1M into redis:

```bash
cd ..; ./load_alexa_top_1m_site_list_into_redis.sh crawl-queue; cd -
```

You can also specify a max rank to load into the queue. For example, to add the
top 1000 sites from the Alexa Top 1M list:

```bash
cd ..; ./load_alexa_top_1m_site_list_into_redis.sh crawl-queue 1000; cd -
```

(Optional) Use some of the `../../utilities/crawl_utils.py` code. For instance, to fetch and store a sample of Alexa Top 1M to `/tmp/sampled_sites.json`:

```bash
source ../../venv/bin/activate
cd ../../; python -m utilities.get_sampled_sites; cd -
```

## Configure the crawl

Since each crawl is unique, you need to configure your `crawl.yaml` deployment configuration. We have provided a template to start from:

```bash
envsubst < ./crawl.tmpl.yaml > crawl.yaml
```

Use of `envsubst` has already replaced `$REDIS_HOST` with the value of the env var set previously, but you may still want to adapt `crawl.yaml`:

- spec.parallelism  (this is the number of pods that can be used - many pods can fit on one node, kubernetes will manage this based on the resources used by any given set of pods on a node)
- spec.containers.image
- spec.containers.env
- spec.containers.resources

Note: A useful naming convention for `CRAWL_DIRECTORY` is `YYYY-MM-DD_description_of_the_crawl`.

### Scale up the cluster before running the crawl

Some nodes including the master node can become temporarily unavailable  during cluster auto-scaling operations. When larger new crawls are started, this can cause disruptions for a couple of minutes after the crawl has started.

To avoid this, set the amount of nodes (to, say, 15) before starting the crawl:

```bash
gcloud container clusters resize $CRAWL_PREFIX-cluster --num-nodes=15
```

## Start the crawl

When you are ready, deploy the crawl:

```bash
kubectl create -f crawl.yaml
```

Note that for the remainder of these instructions, `metadata.name` is assumed to be set to `openwpm-crawl`.

## Monitor the crawl

### Queue status

Launch redis-cli:

```bash
kubectl exec -it redis-box -- sh -c "redis-cli -h $REDIS_HOST"
```

Current length of the queue:

```bash
llen crawl-queue
```

Amount of queue items marked as processing:

```bash
llen crawl-queue:processing 
```

Contents of the queue:

```bash
lrange crawl-queue 0 -1
```

### Crawl progress and logs

Check out the [GCP GKE Console](https://console.cloud.google.com/kubernetes/workload)

Also:

```bash
watch kubectl top nodes
watch kubectl top pods --selector=job-name=openwpm-crawl
watch kubectl get pods --selector=job-name=openwpm-crawl
```

(Optional) To see a more detailed summary of the job as it executes or after it has finished:

```bash
kubectl describe job openwpm-crawl
```

### View Job logs via GCP Stackdriver Logging Interface

- Visit [GCP Logging Console](https://console.cloud.google.com/logs/viewer)
- Select `GKE Container`

### Using the Kubernetes Dashboard UI

(Optional) You can also spin up the Kubernetes Dashboard UI as per [these instructions](https://kubernetes.io/docs/tasks/access-application-cluster/web-ui-dashboard/#deploying-the-dashboard-ui) which will allow for easy access to status and logs related to running jobs/crawls.

### Inspecting crawl results

The crawl data will end up in Parquet format in the S3 bucket that you configured.

## Deleting resources after the crawl

### Discover running instances

If you can't remember which `$CRAWL_PREFIX` you specified to start the crawl,
you can check the currently running clusters using:

```bash
gcloud container clusters list
```

You can check the currently running redis instances using:

```bash
gcloud redis instances list --region=us-central1
```

Be sure that you don't kill clusters or redis instances used by other users of
your GCP project (if any).

### Clean up created pods, instances and local artifacts

```bash
kubectl delete -f crawl.yaml
gcloud redis instances delete $CRAWL_PREFIX-redis --region=us-central1
kubectl delete -f redis-box.yaml
```

### Decrease the size of the cluster while it is not in use

While the cluster has auto-scaling activated, and thus should scale down when not in use, it can sometimes be slow to do this or fail to do this adequately. In these instances, it is a good idea to set the number of nodes to 0 or 1 manually:

```bash
gcloud container clusters resize $CRAWL_PREFIX-cluster --num-nodes=1
```

It will still auto-scale up when the next crawl is executed.

### Deleting the GKE Cluster

If crawls are not to be run and the cluster need not to be accessed within the next hours or days, it is safest to delete the cluster:

```bash
gcloud container clusters delete $CRAWL_PREFIX-cluster
```

### Troubleshooting

In case of any unexpected issues, rinse (clean up) and repeat. If the problems remain, file an issue against https://github.com/mozilla/openwpm-crawler.
