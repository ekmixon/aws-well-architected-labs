#!/usr/bin/env python3

#Gets org data, grouped by ous and tags from managment accounts in json
import argparse
import boto3
from botocore.exceptions import ClientError
from botocore.client import Config
import os
import datetime
import json

def myconverter(o):
    if isinstance(o, datetime.datetime):
        return o.__str__()

def list_tags(client, resource_id):
    tags = []
    paginator = client.get_paginator("list_tags_for_resource")
    response_iterator = paginator.paginate(ResourceId=resource_id)
    for response in response_iterator:
        tags.extend(response['Tags'])
    return tags
    
def lambda_handler(event, context):

    sts_connection = boto3.client('sts')
    acct_b = sts_connection.assume_role(
        RoleArn="arn:aws:iam::(account id):role/OrganizationLambdaAccessRole",
        RoleSessionName="cross_acct_lambda"
    )
    
    ACCESS_KEY = acct_b['Credentials']['AccessKeyId']
    SECRET_KEY = acct_b['Credentials']['SecretAccessKey']
    SESSION_TOKEN = acct_b['Credentials']['SessionToken']

    # create service client using the assumed role credentials
    client = boto3.client(
        "organizations", region_name="us-east-1", #Using the Organizations client to get the data. This MUST be us-east-1 regardless of region you have the Lamda in
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        aws_session_token=SESSION_TOKEN,
    )

    root_id    = client.list_roots()['Roots'][0]['Id']
    ou_id_list = get_ou_ids(root_id, client)
    
    with open('/tmp/ou-org.json', 'w') as f: # Saving in the temporay folder in the lambda
        for ou in ou_id_list.keys():
            account_data(f, ou, ou_id_list[ou][0], client)
    s3_upload('ou-org')

    with open('/tmp/acc-org.json', 'w') as f: # Saving in the temporay folder in the lambda
        account_data(f, root_id, root_id, client)
    s3_upload('acc-org')

def account_data(f, parent, parent_name, client):
    tags_check = os.environ["TAGS"]
    account_id_list = get_acc_ids(parent, client)
    for account_id in account_id_list:
        response = client.describe_account(AccountId=account_id)
        account  = response["Account"]          
        if tags_check != '':
            tags_list = list_tags(client, account["Id"]) #gets the lists of tags for this account
            
            for tag in os.environ.get("TAGS").split(","): #looking at tags in the enviroment variables split by a space
                for org_tag in tags_list:
                    if tag == org_tag['Key']: #if the tag found on the account is the same as the current one in the environent varibles, add it to the data
                        value = org_tag['Value']
                        kv = {tag : value}
                        account.update(kv)
        account.update({'Parent' : parent_name})        
        data = json.dumps(account, default = myconverter) #converts datetime to be able to placed in json

        f.write(data)
        f.write('\n')

def s3_upload(file_name):
    bucket = os.environ["BUCKET_NAME"] #Using environment variables below the Lambda will use your S3 bucket
    try:
        s3 = boto3.client('s3', os.environ["REGION"],
                        config=Config(s3={'addressing_style': 'path'}))
        s3.upload_file(
            f'/tmp/{file_name}.json', bucket, f"organisation-data/{file_name}.json") #uploading the file with the data to s3
        print(f"{file_name}org data in s3")
    except Exception as e:
        print(e)
def ou_loop(parent_id, test, client):
    print(parent_id)
    paginator = client.get_paginator('list_children')
    iterator = paginator.paginate( ParentId=parent_id, ChildType='ORGANIZATIONAL_UNIT')
    for page in iterator:
        for ou in page['Children']:
            test.append(ou['Id'])
            ou_loop(ou['Id'], test, client)
    return test

def get_ou_ids(parent_id, client):
    full_result = {}
    test = []
    ous = ou_loop(parent_id, test, client)
    print(ous)

    for ou in ous:
        ou_info = client.describe_organizational_unit(OrganizationalUnitId=ou)
        full_result[ou] = [ou_info['OrganizationalUnit']['Name']]
    return full_result

def get_acc_ids(parent_id,  client):
  full_result = []
  paginator = client.get_paginator('list_accounts_for_parent')
  iterator  = paginator.paginate(ParentId=parent_id)
  for page in iterator:
    for acc in page['Accounts']:
      print(acc['Id'])
      full_result.append(acc['Id'])
  return full_result