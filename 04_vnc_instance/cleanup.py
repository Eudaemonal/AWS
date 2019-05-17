#!/usr/bin/python3

import sys
import os
import re
import boto3
import argparse
import logging
import time
from botocore.exceptions import ClientError


from config import Config



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

            time.sleep(60) # Wait for ec2 instance to shutdown
            cleanup_sg(cleanup_info)

            os.system('rm %s' % (cleanup_info['remote_deploy_file']))
            # delete cleanup_info file
            os.system('rm %s' % (options.cleanup))
            
            print("cleanup succeeded.")
        except Exception as e:
            logging.error(str(e))
            
            

if __name__=="__main__":
    main(sys.argv)

