#!/bin/bash
set -e

if [[ $# -lt 1 ]]; then
    echo "Usage: load_alexa_top_1m_site_list_into_redis.sh redis_queue_name [max_rank]" >&2
    exit 1
fi
REDIS_QUEUE_NAME="$1"
START_POS="$2"
NUMBER_ELEMS="$3"
REDIS_HOST="$4"

echo -e "\nAttempting to clean up any leftover lists from a previous run..."
rm top-1m.csv.zip* || true
rm top-1m.csv* || true

echo -e "\nDownloading and unzipping site list..."
wget http://s3.amazonaws.com/alexa-static/top-1m.csv.zip
unzip -o top-1m.csv.zip

if [[ -n "$START_POS" ]]; then
  echo "NUMBER_ELEMS = $NUMBER_ELEMS"
  echo "START_POS = $START_POS"
  tail -n +"$START_POS" top-1m.csv | head -n "$NUMBER_ELEMS" > temp.csv
#  head -n $MAX_RANK top-1m.csv > temp.csv
  mv temp.csv top-1m.csv
fi

./load_site_list_into_redis.sh "$REDIS_QUEUE_NAME" top-1m.csv "$REDIS_HOST"

echo -e "\nCleaning up..."
rm top-1m.csv.zip
rm top-1m.csv
