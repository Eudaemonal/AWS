#!/usr/bin/python3


import os
import sys
import boto3
import shutil
import pathlib
import subprocess
import json


def main(argv):
    config_file = 'remote_config.json'

    with open(config_file) as f:
        configs = json.load(f)

    session = boto3.session.Session(
        configs['access_key_id'],
        configs['secret_access_key'],
        None,
        configs['region'],
        None
    )

    sqs = session.resource('sqs')
    queue = sqs.get_queue_by_name(QueueName=configs['sqs_name'])

    while True:
        # process the first message in queue
        response = queue.receive_messages(MaxNumberOfMessages=1)

        if len(response) == 0:
            # None in sqs
            continue

        message = response[0]
        content = json.loads(message.body)

        # unpack content
        prefix = content['prefix']
        input_bucket_name = content['input_bucket']
        output_bucket_name = content['output_bucket']
        filename = content['filename']
        input_path = 'input'
        # Delete directory
        try:
            shutil.rmtree(input_path+'/'+prefix)
        except FileNotFoundError:
            pass
        # create a directory and download from s3
        pathlib.Path(input_path+'/'+prefix).mkdir(parents=True)


        s3 = session.resource('s3')
        input_bucket = s3.Bucket(input_bucket_name)
        output_bucket = s3.Bucket(output_bucket_name)

        for object in input_bucket.objects.filter(Prefix=prefix+'/'): # filter specific files
            input_bucket.download_file(object.key, input_path+"/"+object.key)


        output_path = 'service_output'
        pathlib.Path(output_path).mkdir(parents=True, exist_ok=True)

        output_filename = prefix+'.zip'
        output_file_path = output_path+'/'+output_filename


        # remove in case the file exists
        try:
            os.remove(output_file_path)
        except FileNotFoundError:
            pass


        # process
        subprocess.call('python3 proc.py -i '+input_path+'/'+prefix+'/'+filename+' -o '+output_file_path, shell=True)

        try:
            with open(output_file_path, 'rb') as data:
                # upload to output s3 bucket
                output_bucket.put_object(Key=output_filename, Body=data)
        except FileNotFoundError:
            # create empty file and upload
            output_bucket.put_object(Key=output_filename, Body=b'')

        # delete specific images in input bucket
        for object in input_bucket.objects.filter(Prefix=prefix+'/'):
            object.delete()

        # need to delete from sqs
        message.delete()

        # cleanup local files
        shutil.rmtree(input_path+'/'+prefix)

        try:
            os.remove(output_file_path)
        except FileNotFoundError:
            pass


if __name__ == '__main__':
    main(sys.argv)
