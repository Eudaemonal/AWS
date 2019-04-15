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


class WatchDog:
    def __init__(self, session, configs):
        self.configs = configs

        self.cloud_watch_client = session.client('cloudwatch')
        self.sqs_queue_resource = session.resource('sqs')
        self.ec2_resource = session.resource('ec2')
        self.ec2_client = session.client('ec2')


    def get_sqs_length(self):
        queue = self.sqs_queue_resource.get_queue_by_name(\
            QueueName=self.configs['sqs_name'])
        q_len = int(queue.attributes['ApproximateNumberOfMessages'])
        return q_len


    '''
    def get_all_server_instance(self):
        ec2_resource = boto3.resource('ec2')
        ami_filter = {
            'Name': 'image-id',
            'Values': [self.configs['universal_image_id']]
        }
        init_server_filter = {
            'Name': 'instance-id',
            'Values': [self.configs['original_service_instance_id']]
        }
        ami_server_instances = list(ec2_resource.instances.filter(Filters=[ami_filter]))
        init_server_instance = list(ec2_resource.instances.filter(Filters=[init_server_filter]))

        server_instances = ami_server_instances + init_server_instance
        return server_instances
    '''


    def get_running_instances(self, server_instances=None):
        if server_instances == None:
            server_instances = self.get_all_server_instance()

        server_running_instances = []
        for ins in server_instances:
            if ins.state['Name'] == 'running':
                server_running_instances.append(ins)
        return server_running_instances

    def destroy_one_instance(self, instance_id):
        to_destroy_instance = self.ec2_resource.Instance(instance_id)
        to_destroy_instance.terminate()

    def create_one_instance(self):
        key_path = self.configs['private_key_path']
        key_name = os.path.splitext(key_path.split('/')[-1])[0]

        sec_grp_id = self.configs['security_group_id']
        sec_grp_name = self.ec2_client.describe_security_groups(
            GroupIds = [sec_grp_id]
        )['SecurityGroups'][0]['GroupName']

        new_instance = self.ec2_resource.create_instances(
            ImageId=self.configs['service_image_id'],
            MinCount=1,
            MaxCount=1,
            InstanceType=self.configs['instance_type'],
            KeyName=key_name,
            SecurityGroups=[sec_grp_name]
        )
        return new_instance[0]

    def scale_to(self, num):
        running_instances = self.get_running_instances()
        running_count = len(running_instances)
        if num >= 1:
            diff_num = int(num - running_count)
            if diff_num > 0:
                # scale out
                new_instances = []
                for _ in range(diff_num):
                    new_instances.append(self.create_one_instance())
                for instance in new_instances:
                    instance.wait_until_running()
                    instance.load()

            else:
                # scale in
                diff_num = abs(diff_num)
                for i in range(diff_num):
                    self.destroy_one_instance(running_instances[i].id)
                    # TODO Optional: Terminate instance that is currently not processing


    def get_status(self, display=True):
        server_instances = self.get_all_server_instance()
        total_cpu_avg = 0
        total_cpu_count = 0

        for ins in server_instances:
            response = self.cloud_watch_client.get_metric_statistics(Period=300,
                StartTime=datetime.datetime.utcnow() - datetime.timedelta(seconds=600),
                EndTime=datetime.datetime.utcnow(),
                MetricName='CPUUtilization',
                Namespace='AWS/EC2',
                Statistics=['Average'],
                Dimensions=[{'Name':'InstanceId', 'Value':ins.id}])

            # print(response)
            cpu_avg = 0
            instance_state = ins.state['Name']

            for cpu in response['Datapoints']:
                if 'Average' in cpu:
                    cpu_avg = cpu['Average']

                    if instance_state == 'running':
                        total_cpu_avg += cpu_avg
                        total_cpu_count += 1

            if display:
                print("instance: {} {} {}%".format(ins.id, instance_state, cpu_avg))

        if total_cpu_count <= 0:
            total_cpu_avg = 0
        else:
            total_cpu_avg /= total_cpu_count
        if display:
            print("average utilisation: {}%".format(total_cpu_avg))
            print("queue length: {}".format(self.get_sqs_length()))

        if display == False:
            return total_cpu_avg, self.get_sqs_length()

    def monitor(self):
        # TODO: improve the scale strategy
        server_instances = self.get_running_instances()
        total_cpu_avg, q_len = self.get_status(display=False)

        num_instances_there_should_be_by_q_len = ((q_len/int(self.configs['watchdog_config']['unit_queue_len'])) * int(\
            self.configs['watchdog_config']['num_server_neeeded_per_uql_request'])) + 1

        if num_instances_there_should_be_by_q_len != len(server_instances):
            self.scale_to(num_instances_there_should_be_by_q_len)

        # optional: auxiliary monitoring strategy
        if total_cpu_avg < float(self.configs['watchdog_config']['cpu_avg_usage_lower_bound']):
            # scale in
            pass
        elif total_cpu_avg > float(self.configs['watchdog_config']['cpu_avg_usage_higher_bound']):
            # scale out
            pass
        else:
            # do nothing
            pass



def read_config(config_file):
    config_json = None
    if os.path.isfile(config_file):
        config_json = open(config_file)
    else:
        parent_d = os.path.dirname(os.getcwd())
        config_json = open(parent_d+'/'+config_file)
    configs = json.load(config_json)

    return configs

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale_to", help="scale_to certain number of instances")
    parser.add_argument("--status", help="get servers' status", action="store_true")
    args = parser.parse_args()

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

    wd = WatchDog(session, configs)



    # used as debug output
    if wd.configs['overall_config']['logging_level'] == 'disable':
        logging.disable(logging.ERROR)
    else:
        logging.basicConfig(level=int(wd.configs['overall_config']['logging_level']),
            format='%(asctime)s - %(levelname)s - %(message)s')

    if args.status:
        logging.info('get status')
        try:
            wd.get_status()
        except Exception as e:
            pass

    if args.scale_to:
        logging.info('scale to certain number')
        num = int(args.scale_to)
        try:
            wd.scale_to(num)
        except Exception as e:
            pass

    if not args.status and not args.scale_to:
        logging.info('monitor server pool')
        try:
            wd.monitor()
        except Exception as e:
            pass

