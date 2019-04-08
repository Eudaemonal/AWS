#!/usr/bin/python3

import sys
import os
import re
import logging
import time
import getopt
import argparse
import json
import boto3
import paramiko

from config import Config



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

            # create aws session
            session = boto3.session.Session(
                configs["basic_config"]["configure"]["access_key_id"],
                configs["basic_config"]["configure"]["secret_access_key"],
                None,
                configs["basic_config"]["configure"]["region"],
                None
            )


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
