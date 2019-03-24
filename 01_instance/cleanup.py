#!/usr/bin/python3

import sys
import os
import re
import boto3
import argparse
import logging
from botocore.exceptions import ClientError


from config import Config

def cleanup_sqs(cleanup_info):
    try:
        sqs_client = boto3.client('sqs')
        sqs_resource = boto3.resource('sqs')
        sqs_q = sqs_resource.get_queue_by_name(QueueName=cleanup_info['sqs_name'])
        sqs_client.delete_queue(QueueUrl=sqs_q.url)
    except Exception as e:
        print(e)


def cleanup_s3(cleanup_info):
    try:
        s3 = boto3.resource('s3')
        bucket = s3.Bucket(cleanup_info['input_bucket_name'])
        bucket.objects.all().delete()
        bucket.delete()

        bucket = s3.Bucket(cleanup_info['output_bucket_name'])
        bucket.objects.all().delete()
        bucket.delete()
    except Exception as e:
        print(e)

def cleanup_ec2_instance(cleanup_info):
    try:
        if 'instance_id' in cleanup_info:
            ec2 = boto3.resource('ec2')
            instance = ec2.Instance(cleanup_info['instance_id'])
            instance.terminate()
    except Exception as e:
        print(e)


def cleanup_sg(cleanup_info):
    if 'security_group_id' not in cleanup_info:
        return

    ec2 = boto3.client('ec2')
    try:
        # delete security group by id
        response = ec2.delete_security_group(GroupId=cleanup_info['security_group_id'])
    except ClientError as e:
        print(e)



def main(argv):
    # Parse argument
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--cleanup", 
                        action="store", dest="cleanup", help="cleanup info file path", required=True)
    parser.add_argument("-v", "--verbose", 
                        action="store_true", help="print debug messages")
    options = parser.parse_args()

    # Create configure 
    cfg = Config(options.cleanup)

    if not cfg.success():
        exit(1)

    else:
        try:
            cleanup_info = cfg.load()

            # executing cleanup procedure
            cleanup_ec2_instance(cleanup_info)
            cleanup_sqs(cleanup_info)
            cleanup_s3(cleanup_info)
            cleanup_sg(cleanup_info)

            os.system('rm %s' % (cleanup_info['remote_deploy_file']))
            # delete cleanup_info file
            os.system('rm %s' % (options.cleanup))
            
        except Exception as e:
            logging.error(str(e))
            
            

if __name__=="__main__":
    main(sys.argv)

