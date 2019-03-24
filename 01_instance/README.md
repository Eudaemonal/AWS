# Instance

Creation of AWS EC2 Instance, deploying a flask RESTful service able to handle requests. 

## Description

The ```setup.py``` automaticly deploy an EC2 Instance, and setup a flask server. 

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

4. Run the program:   
```python3 setup.py -c configure.json```

5. Test flask server(Replace the Ip with IPv4 Public IP of your Instance):  
```curl -GET 53.64.51.207```   

If you do not change the content in ```remote```, you will see: Default page  

6. Cleanup the the resources created (Note the cleanup_info.json is created by setup.py, it will be removed after cleanup):  
```python3 cleanup.py -c cleanup_info.json```
