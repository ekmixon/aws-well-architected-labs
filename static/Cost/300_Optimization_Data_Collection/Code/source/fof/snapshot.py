import boto3
from botocore.exceptions import ClientError
import json
import datetime
import logging
from json import JSONEncoder
import os

# subclass JSONEncoder
class DateTimeEncoder(JSONEncoder):
    # Override the default method
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
def main(account_id):
    list_region = lits_regions()
    with open("/tmp/data.json", "w") as f:  # Saving in the temporay folder in the lambda
        for region in list_region:
            print(region)
            client = assume_role(account_id, "ec2", region)
            try:
                paginator = client.get_paginator('describe_snapshots')
                response_iterator = paginator.paginate(OwnerIds=["self"])
                for response in response_iterator:
                    for image in response["Snapshots"]:
                        dataJSONData = json.dumps(image, cls=DateTimeEncoder)
                        f.write(dataJSONData)
                        f.write("\n")
                print(f"{region} ebs data collected")
            except Exception as e:
                print(e)

def assume_role(account_id, service, region):
    role_name = os.environ['ROLENAME']
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}" 
    sts_client = boto3.client('sts')
    
    try:
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


if __name__ == "__main__":
    main()