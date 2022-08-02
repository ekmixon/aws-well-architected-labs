import boto3
import logging
from datetime import date
import json
import os
from botocore.exceptions import ClientError
from botocore.client import Config


def lambda_handler(event, context):
bucket = os.environ["BUCKET_NAME"] #Using enviroment varibles below the lambda will use your S3 bucket
DestinationPrefix =  os.environ["PREFIX"]

####CODE TO GET DATA CAN BE REPLACED######
client = boto3.client('ecs')
paginator = client.get_paginator("list_clusters") #Paginator for a large list of accounts
response_iterator = paginator.paginate()
with open('/tmp/data.json', 'w') as f: # Saving in the temporay folder in the lambda
    for response in response_iterator: # extracts the needed info
        for cluster in response['clusterArns']:
            listservices = client.list_services(cluster=cluster.split( '/')[1],maxResults=100)
            for i in listservices['serviceArns']:
                #print (i)
                services = client.describe_services(
                    cluster=cluster.split( '/')[1],
                    services=[
                    i.split( '/')[2],
                    ],
                    include=[
                        'TAGS',
                    ]
                )
                for service in services['services']:
                    data = {'cluster':cluster.split( '/')[1], 'services':i.split( '/')[2], 'serviceName': service.get('serviceName'), 'tags':service.get('tags') }
                    print(data)
####CODE TO GET DATA######    
                    jsondata = json.dumps(data) #converts datetime to be able to placed in json

                    f.write(jsondata)
                    f.write('\n')
print("respose gathered")
today = date.today()
year = today.year
month = today.month
try:
    s3 = boto3.client('s3', config=Config(s3={'addressing_style': 'path'}))
    s3.upload_file(
        '/tmp/data.json', bucket, f"{DestinationPrefix}-data/year={year}/month={month}/{DestinationPrefix}.json") #uploading the file with the data to s3
    print(f"Data in s3 - {DestinationPrefix}-data/year={year}/month={month}")
except Exception as e:
    print(e)
start_crawler()

def start_crawler():
    glue_client = boto3.client('glue')
    os.environ['ROLE_ARN']
    try:
        glue_client.start_crawler(Name=os.environ['CRAWLER_NAME'])
    except Exception as e:
        # Send some context about this error to Lambda Logs
        logging.warning(f"{e}")     


def assume_role(account_id, service, region):
    role_name = os.environ['ROLENAME']
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}" #OrganizationAccountAccessRole
    sts_client = boto3.client('sts')
    
    try:
        #region = sts_client.meta.region_name
        assumedRoleObject = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName="AssumeRoleRoot"
            )
        
        credentials = assumedRoleObject['Credentials']
        client = boto3.client(
            service,
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken'],
            region_name = region
        )
        return client

    except ClientError as e:
        logging.warning(f"Unexpected error Account {account_id}: {e}")
        return None


def lits_regions():
    from boto3.session import Session

    s = Session()
    return s.get_available_regions('ecs')
