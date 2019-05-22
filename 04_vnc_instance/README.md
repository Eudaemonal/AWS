# VNC Instance

Creation of AWS EC2 Instance with vncserver.

Supported AMI:
Ubuntu Server 18.04 LTS (HVM), SSD Volume Type - ami-0b76c3b150c6b1423

## Description

The ```setup.py``` automaticly deploy an EC2 Instance, and setup the vncserver. 

The ```cleanup.py``` delete all resources created during setup, including the EC2 Instance

## How to use

1. Create Access key ID and Secret access key follow the steps in: https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html
Modify the ```access_key_id``` and ```secret_access_key``` regions in configure.json file

2. Create key pairs under EC2 resources, download the private key and give access, It would be needed for ssh

```chmod 400 key.pem```

Modify the ```ssh_key_file``` region in configure.json file 

3. Install essential packages:
```pip3 install boto3```  
```pip3 install uuid```  
```pip3 install paramiko```  
```pip3 install cryptography==2.4.2```  

4. Run the program to setup:   
```python3 setup.py -c configure.json```  

The installation takes more than 20 mins, logs will be shown during installation.  

5. connect the server with VNC Viewer (add ":1" to ssh address of your Instance):  
```ec2-13-239-26-16.ap-southeast-2.compute.amazonaws.com:1```  

The password is: ```newpass``` by default, modify it in ```remote/install.sh```

6. Cleanup the the resources created (Note the cleanup_info.json is created by setup.py, it will be removed after cleanup):  
```python3 cleanup.py -c cleanup_info.json```

