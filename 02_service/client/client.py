#!/usr/bin/python3

import argparse
import boto3
import json
import os
import inotify.adapters
from multiprocessing import Process, Queue
import time


# Search for pdfs
# Upload pdf to buckets
# Send sqs message for transcoding job
# Delete pdf in directory


def monitor(path, queue, inputb, outputb, pqueue):
    i = inotify.adapters.Inotify()

    i.add_watch(path)
     
    for event in i.event_gen():
        if event is not None:
            (header, type_names, watch_path, filename) = event
     
            #print("WD=(%d) MASK=(%d) COOKIE=(%d) LEN=(%d) MASK->NAMES=%s WATCH-PATH=[%s] FILENAME=[%s]"%(header.wd, header.mask, header.cookie, header.len, type_names, watch_path, filename))
            if(type_names[0] == 'IN_MOVED_TO'):
                process_file(filename, path, queue, inputb, outputb, pqueue)

# process file and send sqs message for processing
# fork seprate process to handle processed file
def process_file(filename, path, queue, inputb, outputb, pqueue):
    message, prefix = create_message(filename)
    # Send sqs message for processing
    response = queue.send_message(MessageBody=message)

    # upload file to s3 bucket
    key = prefix+'/'+filename
    file = path+'/'+filename
    with open(file,'rb') as data:
        inputb.put_object(Key=key, Body=data)
    # delete file on local
    os.remove(file) 

    # create fetcher
    fetcher_p = Process(target=fetch_file, args=(pqueue, outputb))
    fetcher_p.daemon = True
    fetcher_p.start() 

    pqueue.put(prefix)

    fetcher_p.join()

def create_message(filename):
    # create the message body
    prefix = filename.split('.')[0]

    message_body = {}
    message_body['input_bucket'] = config['s3_input_bucket_name']
    message_body['output_bucket'] = config['s3_output_bucket_name']
    message_body['prefix'] = prefix
    message_body['filename'] = filename
    message_body = json.dumps(message_body)

    return message_body, prefix


# fetch processed file from s3 bucket
def fetch_file(queue, outputb):
    ## Read from the queue; this will be spawned as a separate Process
    while True:
        prefix = queue.get()
        filename = prefix+".zip"
        while True:
            objs = list(outputb.objects.filter(Prefix=filename))

            # file exisits, put into download
            if len(objs) > 0 and objs[0].key == filename:
                for object in outputb.objects.filter(Prefix=filename): # filter specific files
                    outputb.download_file(object.key, "download/"+object.key)
                break

            # file not exisits, wait and query again
            else:
                time.sleep(0.5) 




if __name__ == '__main__':
    directory = 'uploaded'
    config_file = 'remote_config.json'

    with open(config_file) as f:
        config = json.load(f)

    session = boto3.session.Session(
        config['access_key_id'],
        config['secret_access_key'],
        None,
        config['region'],
        None
    )

    sqs = session.resource('sqs')
    queue = sqs.get_queue_by_name(QueueName=config['sqs_name'])

    s3 = session.resource('s3')
    inputb = s3.Bucket(config['s3_input_bucket_name'])
    outputb = s3.Bucket(config['s3_output_bucket_name'])

    pqueue = Queue() # process queue

    monitor(directory, queue, inputb, outputb, pqueue)
