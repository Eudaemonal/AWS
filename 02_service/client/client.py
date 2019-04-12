#!/usr/bin/python3

import argparse
import uuid
import boto3
import json
import os
import inotify.adapters


# Search for pdfs
# Upload pdf to buckets
# Send sqs message for transcoding job
# Delete pdf in directory

def create_message(prefix, filename):
    # create the message body
    message_body = {}
    message_body['input_bucket'] = config['s3_input_bucket_name']
    message_body['output_bucket'] = config['s3_output_bucket_name']
    message_body['prefix'] = prefix
    message_body['filename'] = filename
    message_body = json.dumps(message_body)

    return message_body


def monitor(path, queue, inputb):
    i = inotify.adapters.Inotify()

    i.add_watch(path)
     
    for event in i.event_gen():
        if event is not None:
            (header, type_names, watch_path, filename) = event
     
            #print("WD=(%d) MASK=(%d) COOKIE=(%d) LEN=(%d) MASK->NAMES=%s WATCH-PATH=[%s] FILENAME=[%s]"%(header.wd, header.mask, header.cookie, header.len, type_names, watch_path, filename))
            if(type_names[0] == 'IN_MOVED_TO'):
                process_file(filename, path, queue, inputb)



def process_file(filename, path, queue, inputb):
    prefix = str(uuid.uuid1())
    message = create_message(prefix, filename)
    # Send sqs message for processing
    response = queue.send_message(MessageBody=message)

    # upload file to s3 bucket
    key = prefix+'/'+filename
    file = path+'/'+filename
    with open(file,'rb') as data:
        inputb.put_object(Key=key, Body=data)

    # delete file on local
    os.remove(file) 


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


    monitor(directory, queue, inputb)



    '''
    filename = prefix+'.zip'
    if args.wait:
        output = s3.Bucket(args.output_bucket)
        finished = False
        while not finished:
            time.sleep(int(configs['client_config']['wait_query_frequency']))
            for obj in output.objects.all():
                if obj.key == filename:
                    finished = True

    file_path = 's3://'+args.output_bucket+'/'+filename
    print("You'll find the output in "+file_path)
    '''

