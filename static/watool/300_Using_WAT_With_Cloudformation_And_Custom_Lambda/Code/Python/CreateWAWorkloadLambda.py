import botocore
import boto3
import json
import datetime
from aws_lambda_powertools import Logger
import jmespath
import cfnresponse
from pkg_resources import packaging

__author__    = "Eric Pullen"
__email__     = "eppullen@amazon.com"
__copyright__ = "Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved."
__credits__   = ["Eric Pullen"]

# Default region listed here
REGION_NAME = "us-east-1"
blankjson = {}
response = ""
logger = Logger()

# Helper class to convert a datetime item to JSON.
class DateTimeEncoder(json.JSONEncoder):
    def default(self, z):
        return (str(z)) if isinstance(z, datetime.datetime) else super().default(z)

def CreateNewWorkload(
    waclient,
    workloadName,
    description,
    reviewOwner,
    environment,
    awsRegions,
    lenses,
    tags
    ):

    # Create your workload
    try:
        waclient.create_workload(
        WorkloadName=workloadName,
        Description=description,
        ReviewOwner=reviewOwner,
        Environment=environment,
        AwsRegions=awsRegions,
        Lenses=lenses,
        Tags=tags
        )
    except waclient.exceptions.ConflictException as e:
        workloadId,workloadARN = FindWorkload(waclient,workloadName)
        logger.warning(
            f"WARNING - The workload name {workloadName} already exists as workloadId {workloadId}"
        )

        UpdateWorkload(waclient,workloadId,workloadARN, workloadName,description,reviewOwner,environment,awsRegions,lenses,tags)

            # Maybe we should "update" the above variables?

    except botocore.exceptions.ParamValidationError as e:
        logger.error(f"ERROR - Parameter validation error: {e}")
    except botocore.exceptions.ClientError as e:
        logger.error(f"ERROR - Unexpected error: {e}")


def FindWorkload(
    waclient,
    workloadName
    ):

    # Finding your WorkloadId
    try:
        response=waclient.list_workloads(
        WorkloadNamePrefix=workloadName
        )
    except botocore.exceptions.ParamValidationError as e:
        logger.error(f"ERROR - Parameter validation error: {e}")
    except botocore.exceptions.ClientError as e:
        logger.error(f"ERROR - Unexpected error: {e}")

    # print("Full JSON:",json.dumps(response['WorkloadSummaries'], cls=DateTimeEncoder))
    workloadId = response['WorkloadSummaries'][0]['WorkloadId']
    workloadARN = response['WorkloadSummaries'][0]['WorkloadArn']
    # print("WorkloadId",workloadId)
    return workloadId, workloadARN

def UpdateWorkload(
    waclient,
    workloadId,
    workloadARN,
    workloadName,
    description,
    reviewOwner,
    environment,
    awsRegions,
    lenses,
    tags
    ):

    logger.info("Updating workload properties")
    # Create your workload
    try:
        waclient.update_workload(
        WorkloadId=workloadId,
        WorkloadName=workloadName,
        Description=description,
        ReviewOwner=reviewOwner,
        Environment=environment,
        AwsRegions=awsRegions,
        )
    except botocore.exceptions.ParamValidationError as e:
        logger.error(f"ERROR - Parameter validation error: {e}")
    except botocore.exceptions.ClientError as e:
        logger.error(f"ERROR - Unexpected error: {e}")
    # Should add updates for the lenses?
    # Should add the tags as well
    logger.info("Updating workload tags")
    try:
        waclient.tag_resource(WorkloadArn=workloadARN,Tags=tags)
    except botocore.exceptions.ParamValidationError as e:
        logger.error(f"ERROR - Parameter validation error: {e}")
    except botocore.exceptions.ClientError as e:
        logger.error(f"ERROR - Unexpected error: {e}")



def lambda_handler(event, context):
    boto3_min_version = "1.16.38"
    # Verify if the version of Boto3 we are running has the wellarchitected APIs included
    if (packaging.version.parse(boto3.__version__) < packaging.version.parse(boto3_min_version)):
        logger.error(
            f"Your Boto3 version ({boto3.__version__}) is less than {boto3_min_version}. You must ugprade to run this script (pip3 upgrade boto3)"
        )

        exit()
    responseData = {}
    # print(json.dumps(event))
    try:
        WORKLOADNAME = event['ResourceProperties']['WorkloadName']
        DESCRIPTION = event['ResourceProperties']['WorkloadDesc']
        REVIEWOWNER = event['ResourceProperties']['WorkloadOwner']
        ENVIRONMENT= event['ResourceProperties']['WorkloadEnv']
        AWSREGIONS = [event['ResourceProperties']['WorkloadRegion']]
        LENSES = event['ResourceProperties']['WorkloadLenses']
        TAGS = event['ResourceProperties']['Tags']
        SERVICETOKEN = event['ResourceProperties']['ServiceToken']
    except:
        responseData['Error'] = "ERROR LOADING RESOURCE PROPERTIES"
        cfnresponse.send(event, context, cfnresponse.FAILED, responseData, 'createWAWorkloadHelperFunction')
        exit()

    IncomingARN = SERVICETOKEN.split(":")
    REGION_NAME = IncomingARN[3]


    logger.info(f"Starting Boto {boto3.__version__} Session in {REGION_NAME}")
    # Create a new boto3 session
    SESSION = boto3.session.Session()
    # Initiate the well-architected session using the region defined above
    WACLIENT = SESSION.client(
        service_name='wellarchitected',
        region_name=REGION_NAME,
    )

    logger.info("Creating a new workload")
    CreateNewWorkload(WACLIENT,WORKLOADNAME,DESCRIPTION,REVIEWOWNER,ENVIRONMENT,AWSREGIONS,LENSES,TAGS)
    logger.info("Finding your WorkloadId")
    workloadId,workloadARN = FindWorkload(WACLIENT,WORKLOADNAME)
    logger.info(f"New workload created with id {workloadId}")
    responseData['WorkloadId'] = workloadId
    responseData['WorkloadARN'] = workloadARN
    logger.info(f"Response will be {responseData}")

    cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData)
