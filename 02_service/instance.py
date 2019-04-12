#!/usr/bin/python3

import boto3
import json
import uuid
import sys
import paramiko
import logging
import os
import time
import argparse
import datetime

class Instance:
    def __init__(self, session, configs):
        self.session = session
        self.region = configs['basic_config']['configure']['region']
        self.ssh_key_file = configs['basic_config']['remote']['ssh_key_file']
        self.image_id = configs['basic_config']['remote']['image_id']
        self.instance_type = configs['basic_config']['remote']['instance_type']
        self.security_group = configs['basic_config']['security_group']['name']
        self.ssh_wait_time = configs['basic_config']['remote']['ssh_wait_time']
        self.deploy_file = configs['basic_config']['remote']['deploy_file']
        self.deploy_directory = configs['basic_config']['remote']['deploy_directory']
        self.remote_username = configs['basic_config']['remote']['username']

        self.corn_execution_interval = configs['basic_config']['remote']['execution_interval']

    def run(self, cleanup_info):
        ec2 = self.session.resource('ec2', region_name=self.region)
        sshkey_path = self.ssh_key_file
        sshkey_name = sshkey_path.split('/')[-1].split('.')[0]
        self.instance = ec2.create_instances(
            ImageId=self.image_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=self.instance_type,
            KeyName=sshkey_name,
            SecurityGroups=[self.security_group]
        )[0]

        self.instance.wait_until_running()
        self.instance.load()

        self.public_dns_name = self.instance.public_dns_name

        cleanup_info['instance_id'] = self.instance.instance_id
        cleanup_info['remote_deploy_file'] = self.deploy_file
        logging.info('successfully launch ec2 instance')

        return self.public_dns_name

    def config(self):
        # configure the ec2 instance
        os.system("tar -zcvf %s %s > /dev/null 2>&1" % 
                (self.deploy_file, 
                 self.deploy_directory))
        os.system("scp -o 'StrictHostKeyChecking no' -i %s %s %s@%s:~/ > /dev/null 2>&1" % 
                (self.ssh_key_file,
                self.deploy_file,
                self.remote_username,
                self.public_dns_name))
        os.system("scp -o 'StrictHostKeyChecking no' -i %s %s %s@%s:~/ > /dev/null 2>&1" % 
                (self.ssh_key_file,
                self.ssh_key_file,
                self.remote_username,
                self.public_dns_name))
        
        # ssh to remote, run necessary setup and start cron job
        paramiko_private_key = paramiko.RSAKey.from_private_key_file(self.ssh_key_file)
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())


        try:
            ssh.connect(hostname=self.public_dns_name,
                    username=self.remote_username,
                    pkey=paramiko_private_key)

            # unzip the codes on ec2 instance
            unzip_cmd = 'tar xvfz %s' % (self.deploy_file)
            stdin, stdout, stderr = ssh.exec_command(unzip_cmd)
            exit_status = stdout.channel.recv_exit_status()
            
            # move codes in remote folder to home directory
            move_cmd = 'mv %s/* ~/' % (self.deploy_directory)
            stdin, stdout, stderr = ssh.exec_command(move_cmd)
            exit_status = stdout.channel.recv_exit_status()

            # install dependency on ec2 instance
            install_dependency_cmd = 'sudo bash install.sh'
            stdin, stdout, stderr = ssh.exec_command(install_dependency_cmd)
            exit_status = stdout.channel.recv_exit_status()

            # setup ec2 instance and start running
            setup_cmd = 'sudo bash setup.sh'
            stdin, stdout, stderr = ssh.exec_command(setup_cmd)
            exit_status = stdout.channel.recv_exit_status()

            # start the cron job
            #cron_cmd = "echo '*/{} * * * * {}' > cronjob; crontab cronjob; rm cronjob;".format(\
            #        self.corn_execution_interval,\
            #        "sudo python3 application.py")
            #stdin, stdout, stderr = ssh.exec_command(cron_cmd)
            #exit_status = stdout.channel.recv_exit_status()

            # close the connection once the job is done
            ssh.close()
            
        except Exception as e:
            print(e)
            sys.exit()

    def create_image(self, name):
        image = self.instance.create_image(Name=name)
        image.wait_until_exists()

        return image.id



class ClientInstance(Instance):
    def __init__(self, session, configs):
        self.session = session
        self.region = configs['basic_config']['configure']['region']
        self.ssh_key_file = configs['basic_config']['remote']['ssh_key_file']
        self.image_id = configs['basic_config']['remote']['image_id']
        self.instance_type = configs['basic_config']['remote']['instance_type']
        self.security_group = configs['basic_config']['security_group']['name']
        self.ssh_wait_time = configs['basic_config']['remote']['ssh_wait_time']
        self.remote_username = configs['basic_config']['remote']['username']

        self.deploy_file = configs['client_config']['deploy_file']
        self.deploy_directory = configs['client_config']['deploy_directory']

        self.corn_execution_interval = configs['basic_config']['remote']['execution_interval']

    def run(self, cleanup_info):
        ec2 = self.session.resource('ec2', region_name=self.region)
        sshkey_path = self.ssh_key_file
        sshkey_name = sshkey_path.split('/')[-1].split('.')[0]
        self.instance = ec2.create_instances(
            ImageId=self.image_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=self.instance_type,
            KeyName=sshkey_name,
            SecurityGroups=[self.security_group]
        )[0]

        self.instance.wait_until_running()
        self.instance.load()

        self.public_dns_name = self.instance.public_dns_name

        cleanup_info['client_instance_id'] = self.instance.instance_id
        cleanup_info['client_deploy_file'] = self.deploy_file
        logging.info('successfully launch client instance')

        return self.public_dns_name



class ServiceInstance(Instance):
    def __init__(self, session, configs):
        self.session = session
        self.region = configs['basic_config']['configure']['region']
        self.ssh_key_file = configs['basic_config']['remote']['ssh_key_file']
        self.image_id = configs['basic_config']['remote']['image_id']
        self.instance_type = configs['basic_config']['remote']['instance_type']
        self.security_group = configs['basic_config']['security_group']['name']
        self.ssh_wait_time = configs['basic_config']['remote']['ssh_wait_time']
        self.remote_username = configs['basic_config']['remote']['username']

        self.deploy_file = configs['service_config']['deploy_file']
        self.deploy_directory = configs['service_config']['deploy_directory']

        self.corn_execution_interval = configs['basic_config']['remote']['execution_interval']

    def run(self, cleanup_info):
        ec2 = self.session.resource('ec2', region_name=self.region)
        sshkey_path = self.ssh_key_file
        sshkey_name = sshkey_path.split('/')[-1].split('.')[0]
        self.instance = ec2.create_instances(
            ImageId=self.image_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=self.instance_type,
            KeyName=sshkey_name,
            SecurityGroups=[self.security_group]
        )[0]

        self.instance.wait_until_running()
        self.instance.load()

        self.public_dns_name = self.instance.public_dns_name

        cleanup_info['service_instance_id'] = self.instance.instance_id
        cleanup_info['service_deploy_file'] = self.deploy_file
        logging.info('successfully launch service instance')

        return self.public_dns_name





class WatchdogInstance(Instance):
    def __init__(self, session, configs):
        self.session = session
        self.region = configs['basic_config']['configure']['region']
        self.ssh_key_file = configs['basic_config']['remote']['ssh_key_file']
        self.image_id = configs['basic_config']['remote']['image_id']
        self.instance_type = configs['basic_config']['remote']['instance_type']
        self.security_group = configs['basic_config']['security_group']['name']
        self.ssh_wait_time = configs['basic_config']['remote']['ssh_wait_time']
        self.remote_username = configs['basic_config']['remote']['username']

        self.deploy_file = configs['watchdog_config']['deploy_file']
        self.deploy_directory = configs['watchdog_config']['deploy_directory']

        self.corn_execution_interval = configs['basic_config']['remote']['execution_interval']

    def run(self, cleanup_info):
        ec2 = self.session.resource('ec2', region_name=self.region)
        sshkey_path = self.ssh_key_file
        sshkey_name = sshkey_path.split('/')[-1].split('.')[0]
        self.instance = ec2.create_instances(
            ImageId=self.image_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=self.instance_type,
            KeyName=sshkey_name,
            SecurityGroups=[self.security_group]
        )[0]

        self.instance.wait_until_running()
        self.instance.load()

        self.public_dns_name = self.instance.public_dns_name

        cleanup_info['watchdog_instance_id'] = self.instance.instance_id
        cleanup_info['watchdog_deploy_file'] = self.deploy_file
        logging.info('successfully launch watchdog instance')

        return self.public_dns_name


