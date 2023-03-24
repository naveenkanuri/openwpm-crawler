import subprocess, re
import time

# Define the Redis host and queue names
REDIS_HOST_RUN1 = "10.53.40.131"
# REDIS_HOST_RUN2 = "10.129.108.123"
PROCESSING_QUEUE = "crawl-queue:processing"
PENDING_QUEUE = "crawl-queue"

JOB_NUM = 1
ELEMS_PER_JOB = 1000
NUM_PODS = 4
MAX_ELEMS = 1000
PROCESSED_ELEMS = 0


def add_to_redis(redis_host):
    print(f'Adding {ELEMS_PER_JOB} from {(JOB_NUM - 1) * ELEMS_PER_JOB + 1} to redis = {redis_host}')
    command_add_queue = f"cd ..; ./load_alexa_top_1m_site_list_into_redis.sh crawl-queue {(JOB_NUM - 1) * ELEMS_PER_JOB + 1} {ELEMS_PER_JOB} {redis_host}; cd -"
    subprocess.check_call(command_add_queue, shell=True)


def create_job(redis_host, run_id):
    print('creating crawl.yaml')
    command_create_crawl_yaml = f"./crawl-run1.sh {JOB_NUM} {redis_host} {NUM_PODS} {run_id}"
    subprocess.check_call(command_create_crawl_yaml, shell=True)
    print('creating job')
    command_create_job = f"kubectl create -f crawl-run1.yaml"
    subprocess.check_call(command_create_job, shell=True)
    print('job creation done')


def delete_job():
    print(f'deleting job {JOB_NUM}')
    command_delete_job = f"kubectl delete job openwpm-crawl-{JOB_NUM}"
    subprocess.check_call(command_delete_job, shell=True)
    print('job deleted')


def get_redis_status(redis_host, processing_queue, pending_queue):
    command_processing = f"kubectl exec -it redis-box -- sh -c 'redis-cli -h {redis_host} <<EOF\nllen {processing_queue}\nquit\nEOF'"
    command_pending = f"kubectl exec -it redis-box -- sh -c 'redis-cli -h {redis_host} <<EOF\nllen {pending_queue}\nquit\nEOF'"
    output = subprocess.check_output(command_processing, shell=True)
    output_str = output.decode('utf-8')  # Decode the bytes object into a string
    processing_length_temp = int(re.search(r'\d+', output_str).group())  # Extract the integer value using regex

    output = subprocess.check_output(command_pending, shell=True)
    output_str = output.decode('utf-8')  # Decode the bytes object into a string
    pending_length_temp = int(re.search(r'\d+', output_str).group())  # Extract the integer value using regex

    return processing_length_temp, pending_length_temp


# while PROCESSED_ELEMS <= MAX_ELEMS:
    # command_kube1 = f"gcloud container clusters get-credentials config-20-10-10-run1-cluster"
    # subprocess.check_call(command_kube1, shell=True)
add_to_redis(REDIS_HOST_RUN1)
create_job(REDIS_HOST_RUN1, 1)

    # command_kube2 = f"gcloud container clusters get-credentials config-20-10-10-run2-cluster"
    # subprocess.check_call(command_kube2, shell=True)
    # add_to_redis(REDIS_HOST_RUN2)
    # create_job(REDIS_HOST_RUN2, 2)

    # while True:
    #     # command_kube1 = f"gcloud container clusters get-credentials config-20-10-10-run1-cluster"
    #     # subprocess.check_call(command_kube1, shell=True)
    #     processing_length1, pending_length1 = get_redis_status(REDIS_HOST_RUN1, PROCESSING_QUEUE, PENDING_QUEUE)
    #     # command_kube2 = f"gcloud container clusters get-credentials config-20-10-10-run2-cluster"
    #     # subprocess.check_call(command_kube2, shell=True)
    #     # processing_length2, pending_length2 = get_redis_status(REDIS_HOST_RUN1, PROCESSING_QUEUE, PENDING_QUEUE)
    #     if processing_length1 == 0 and pending_length1 == 0:
    #         print('it seems redis queue is cleared. sleeping for 120sec before deleting job')
    #         time.sleep(120)
    #         delete_job()
    #         PROCESSED_ELEMS += ELEMS_PER_JOB
    #         JOB_NUM += 1
    #         break
    #     else:
    #         print(
    #             f'processing_length1 = {processing_length1}, pending_length1= {pending_length1}. Sleeping for 5sec')
    #         time.sleep(5)
