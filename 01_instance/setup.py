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



def create_s3_bucket(session, configs, UNIQUE_ID, cleanup_info):
    s3 = session.resource('s3')

    inBucketName = configs['basic_config']['s3_bucket']['input_bucket_name'] + '.' + UNIQUE_ID
    outBucketName = configs['basic_config']['s3_bucket']['output_bucket_name'] + '.' + UNIQUE_ID

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


def run_remote_instance(session, configs, cleanup_info):
    ec2 = session.resource('ec2', region_name=configs['basic_config']['configure']['region'])
    sshkey_path = configs['basic_config']['remote']['ssh_key_file']
    sshkey_name = sshkey_path.split('/')[-1].split('.')[0]
    instance = ec2.create_instances(
        ImageId=configs['basic_config']['remote']['image_id'],
        MinCount=1,
        MaxCount=1,
        InstanceType=configs['basic_config']['remote']['instance_type'],
        KeyName=sshkey_name,
        SecurityGroups=[configs['basic_config']['security_group']['name']]
    )[0]

    instance.wait_until_running()
    instance.load()

    time.sleep(int(configs['basic_config']['remote']['ssh_wait_time']))

    cleanup_info['instance_id'] = instance.instance_id
    cleanup_info['remote_deploy_file'] = configs['basic_config']['remote']['deploy_file']
    logging.info('successfully launch ec2 instance')

    # configure the ec2 instance
    os.system("tar -zcvf %s %s > /dev/null 2>&1" % 
            (configs['basic_config']['remote']['deploy_file'], 
            configs['basic_config']['remote']['deploy_directory']))
    os.system("scp -o 'StrictHostKeyChecking no' -i %s %s %s@%s:~/ > /dev/null 2>&1" % 
            (sshkey_path,
            configs['basic_config']['remote']['deploy_file'],
            configs['basic_config']['remote']['username'],
            instance.public_dns_name))
    os.system("scp -o 'StrictHostKeyChecking no' -i %s %s %s@%s:~/ > /dev/null 2>&1" % 
            (sshkey_path,
            sshkey_path,
            configs['basic_config']['remote']['username'],
            instance.public_dns_name))
    
    # ssh to remote, run necessary setup and start cron job
    paramiko_private_key = paramiko.RSAKey.from_private_key_file(sshkey_path)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())


    try:
        ssh.connect(hostname=instance.public_dns_name,
                username=configs['basic_config']['remote']['username'],
                pkey=paramiko_private_key)

        # unzip the codes on ec2 instance
        unzip_cmd = 'tar xvfz %s' % (configs['basic_config']['remote']['deploy_file'])
        stdin, stdout, stderr = ssh.exec_command(unzip_cmd)
        exit_status = stdout.channel.recv_exit_status()
        
        # move codes in remote folder to home directory
        move_cmd = 'mv %s/* ~/' % (configs['basic_config']['remote']['deploy_directory'])
        stdin, stdout, stderr = ssh.exec_command(move_cmd)
        exit_status = stdout.channel.recv_exit_status()

        # install dependency on ec2 instance
        install_dependency_cmd = 'sudo bash install.sh'
        stdin, stdout, stderr = ssh.exec_command(install_dependency_cmd)
        exit_status = stdout.channel.recv_exit_status()

        # setup ec2 instance and start running
        setup_cmd = 'sudo nohup bash setup.sh >/dev/null 2>&1 &'
        stdin, stdout, stderr = ssh.exec_command(setup_cmd)
        exit_status = stdout.channel.recv_exit_status()

        # start the cron job
        #cron_cmd = "echo '*/{} * * * * {}' > cronjob; crontab cronjob; rm cronjob;".format(\
        #        configs['basic_config']['remote']['execution_interval'],\
        #        "sudo python3 application.py")
        #stdin, stdout, stderr = ssh.exec_command(cron_cmd)
        #exit_status = stdout.channel.recv_exit_status()

        # close the connection once the job is done
        ssh.close()
        
    except Exception as e:
        print(e)
        sys.exit()
    
    return instance



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
            logging.info('successfully load config')

            # loggine config
            if options.verbose:
                logging.basicConfig(level=logging.DEBUG, 
                                    format='%(asctime)s %(levelname)s %(message)s',
                                    filename=configs["basic_config"]["local"]["logging_filename"],
                                    filemode='w')

            else:
                logging.disable(logging.ERROR)

            # container for cleanup info
            cleanup_info = {}

            # generate unique id
            UNIQUE_ID = str(uuid.uuid4())

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
            s3_bucket_input, s3_bucket_output = create_s3_bucket(session, configs, UNIQUE_ID, cleanup_info)
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

            logging.info('successfully create security group, allow ssh and http')


            # create ec2 instance
            instance = run_remote_instance(session, configs, cleanup_info)

            # store the json cleanup_info
            with open('cleanup_info.json', 'w') as outfile:
                json.dump(cleanup_info, outfile)
            print('Remote setup succeeded:')
            print(cleanup_info)
            

        except Exception as e:
            logging.error(str(e))


if __name__=="__main__":
    main(sys.argv)
