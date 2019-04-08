#!/usr/bin/python3

import sys
import os
import re
import logging
import time
import getopt
import argparse
import json
import uuid
import boto3
import paramiko

from config import Config
from instance import *


def create_s3_bucket(session, configs, cleanup_info):
    s3 = session.resource('s3')

    inBucketName = configs['basic_config']['s3_bucket']['input_bucket_name']
    outBucketName = configs['basic_config']['s3_bucket']['output_bucket_name']

    response1 = s3.create_bucket(Bucket=inBucketName,
        CreateBucketConfiguration={'LocationConstraint': configs['basic_config']['configure']['region']})
    response2 = s3.create_bucket(Bucket=outBucketName,
        CreateBucketConfiguration={'LocationConstraint': configs['basic_config']['configure']['region']})

    try:
        s3.meta.client.head_bucket(Bucket=inBucketName)
        s3.meta.client.head_bucket(Bucket=outBucketName)
    except botocore.exceptions.ClientError as e:
        # If a client error is thrown, then check that it was a 404 error.
        # If it was a 404 error, then the bucket does not exist.
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            # TODO: update the bucket name and try to create bucket again
            print('FAIL TO CREATE S3 BUCKET!')
            sys.exit()

    cleanup_info['input_bucket_name'] = inBucketName
    cleanup_info['output_bucket_name'] = outBucketName

    input_bucket = s3.Bucket(inBucketName)
    output_bucket = s3.Bucket(outBucketName)

    return input_bucket, output_bucket



def generate_remote_config(configs, cleanup_info):
    client_directory = configs['basic_config']['remote']['client_deploy_directory']
    service_directory = configs['basic_config']['remote']['service_deploy_directory']
    watchdog_directory = configs['basic_config']['remote']['watchdog_deploy_directory']


    # store the config for remote 
    remote_config = {}
    remote_config['access_key_id'] = configs["basic_config"]["configure"]["access_key_id"]
    remote_config['secret_access_key'] = configs["basic_config"]["configure"]["secret_access_key"]
    remote_config['region'] = configs["basic_config"]["configure"]["region"]

    remote_config['sqs_name'] = configs['basic_config']['sqs']['name']
    remote_config['s3_input_bucket_name'] = configs['basic_config']['s3_bucket']['input_bucket_name']
    remote_config['s3_output_bucket_name'] = configs['basic_config']['s3_bucket']['output_bucket_name']


    with open('remote_config.json', 'w') as outfile:
        json.dump(remote_config, outfile)

    os.system("cp remote_config.json "+client_directory)
    os.system("cp remote_config.json "+service_directory)
    os.system("cp remote_config.json "+watchdog_directory)

    cleanup_info['remote_config'] = 'remote_config.json'

def main(argv):
    # Parse argument
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", 
                        action="store", dest="config", help="configure file path", required=True)
    parser.add_argument("-v", "--verbose", 
                        action="store_true", help="print debug messages")
    options = parser.parse_args()

    # Create configure 
    cfg = Config(options.config)

    if not cfg.success():
        exit(1)

    else:
        try:
            configs = cfg.load()
            # loggine config
            if options.verbose == True:
                logging.basicConfig(level=logging.DEBUG, 
                                    format='%(asctime)s %(levelname)s %(message)s',
                                    filename=configs["basic_config"]["local"]["logging_filename"],
                                    filemode='w')

            else:
                logging.disable(logging.ERROR)

            logging.info('successfully load config')

            # container for cleanup info
            cleanup_info = {}


            # create aws session
            session = boto3.session.Session(
                configs["basic_config"]["configure"]["access_key_id"],
                configs["basic_config"]["configure"]["secret_access_key"],
                None,
                configs["basic_config"]["configure"]["region"],
                None
            )

            # Create an SQS request queue.
            sqs = session.resource('sqs')
            sqs.create_queue(QueueName=configs['basic_config']['sqs']['name'],
                Attributes={'VisibilityTimeout': configs['basic_config']['sqs']['visibility_timeout']})

            cleanup_info['sqs_name'] = configs['basic_config']['sqs']['name']
            logging.info('successfully created sqs')
            
            # Create two S3 buckets: one for input, one for output.
            s3_bucket_input, s3_bucket_output = create_s3_bucket(session, configs, cleanup_info)
            logging.info('successfully created s3 bucket')


            # create security group, allow inbound http, ssh
            ec2 = session.resource('ec2', region_name=configs['basic_config']['configure']['region'])

            security_group = ec2.create_security_group(\
                GroupName=configs['basic_config']['security_group']['name'],
                Description=configs['basic_config']['security_group']['description'])

            cleanup_info['security_group_id'] = security_group.id
            auth_ssh_response = security_group.authorize_ingress(IpProtocol="tcp",
                                    CidrIp="0.0.0.0/0",FromPort=22,ToPort=22)

            auth_http_response = security_group.authorize_ingress(IpProtocol="tcp",
                                    CidrIp="0.0.0.0/0",FromPort=80,ToPort=80)

            # TODO port for testing, remove
            auth_http_response = security_group.authorize_ingress(IpProtocol="tcp",
                                    CidrIp="0.0.0.0/0",FromPort=80,ToPort=8080)


            logging.info('successfully create security group, allow ssh and http')


            generate_remote_config(configs, cleanup_info)

            # create ec2 instances
            client_instance = ClientInstance(session, configs)
            service_instance = ServiceInstance(session, configs)
            watchdog_instance = WatchdogInstance(session, configs)

            client_instance.run(cleanup_info)
            service_instance.run(cleanup_info)
            watchdog_instance.run(cleanup_info)

            time.sleep(int(configs['basic_config']['remote']['ssh_wait_time']))

            client_instance.config()
            service_instance.config()
            watchdog_instance.config()

            # store the json cleanup_info
            with open('cleanup_info.json', 'w') as outfile:
                json.dump(cleanup_info, outfile)
            print('Remote setup succeeded:')
            print(cleanup_info)



        except Exception as e:
            logging.error(str(e))


if __name__=="__main__":
    main(sys.argv)
