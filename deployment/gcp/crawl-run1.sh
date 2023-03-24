#!/bin/bash

job_id=$1
redis_host=$2
num_pods=$3
crawl_id=$4



cat <<EOF > crawl-run1.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: openwpm-crawl-${job_id}
spec:
  # adjust for parallelism
  parallelism: ${num_pods}
  backoffLimit: 10000 # to avoid crawls failing due to sporadic worker crashes
  template:
    metadata:
      name: openwpm-crawl
    spec:
      volumes:
        - name: dshm
          emptyDir:
            medium: Memory
        - name: gcp-credentials
          secret:
            secretName: gcp-credentials
      containers:
      - name: openwpm-crawl
        image: gcr.io/level-gizmo-376804/browse-openwpm
        command: ["python3"]
        args: ["crawler.py"]
        volumeMounts:
          - mountPath: /dev/shm
            name: dshm
          - mountPath: /etc/secrets
            name: gcp-credentials
            readOnly: true
        env:
        - name: REDIS_HOST
          value: '${redis_host}'
        - name: REDIS_QUEUE_NAME
          value: 'crawl-queue'
        - name: CRAWL_DIRECTORY
          value: '03-24-2023-browse-20-10-10-run-${crawl_id}'
        - name: GCS_BUCKET
          value: 'openwpm-bucket'
        - name: GCP_PROJECT
          value: 'level-gizmo-376804'
        - name: HTTP_INSTRUMENT
          value: '1'
        - name: COOKIE_INSTRUMENT
          value: '1'
        - name: NAVIGATION_INSTRUMENT
          value: '1'
        - name: JS_INSTRUMENT
          value: '1'
        - name: CALLSTACK_INSTRUMENT
          value: '1'
        - name: SAVE_CONTENT
          value: 'script'
        - name: DWELL_TIME
          value: '20'
        - name: TIMEOUT
          value: '120'
        - name: LOG_LEVEL_CONSOLE
          value: 'DEBUG'
        - name: LOG_LEVEL_FILE
          value: 'DEBUG'
        - name: LOG_LEVEL_SENTRY_BREADCRUMB
          value: 'DEBUG'
        - name: LOG_LEVEL_SENTRY_EVENT
          value: 'ERROR'
        - name: MAX_JOB_RETRIES
          value: '2'
        - name: GOOGLE_APPLICATION_CREDENTIALS
          value: /etc/secrets/level-gizmo-376804-9ec0c24c2d93.json
        - name: GCP_AUTH_TOKEN
          value: /etc/secrets/level-gizmo-376804-9ec0c24c2d93.json
        - name: BROWSE_OR_GET
          value: BROWSE
        - name: BOT_MITIGATION
          value: Yeah
        - name: NUM_LINKS
          value: '0'
#        - name: AD_BLOCKER_EXT
#          value: ublock-origin
        resources:
          requests:
            cpu: 750m
            memory: 1000Mi
          limits:
            cpu: 1
      restartPolicy: OnFailure
