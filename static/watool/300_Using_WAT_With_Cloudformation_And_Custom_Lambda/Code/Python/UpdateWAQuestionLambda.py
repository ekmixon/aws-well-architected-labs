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

def findQuestionId(
    waclient,
    workloadId,
    lensAlias,
    pillarId,
    questionTitle
    ):

    # Find a questionID using the questionTitle
    try:
        response=waclient.list_answers(
        WorkloadId=workloadId,
        LensAlias=lensAlias,
        PillarId=pillarId
        )
    except botocore.exceptions.ParamValidationError as e:
        logger.error(f"ERROR - Parameter validation error: {e}")
    except botocore.exceptions.ClientError as e:
        logger.error(f"ERROR - Unexpected error: {e}")

    answers = response['AnswerSummaries']
    while "NextToken" in response:
        response = waclient.list_answers(WorkloadId=workloadId,LensAlias=lensAlias,PillarId=pillarId,NextToken=response["NextToken"])
        answers.extend(response["AnswerSummaries"])

    jmesquery = f"[?starts_with(QuestionTitle, `{questionTitle}`) == `true`].QuestionId"

    questionId = jmespath.search(jmesquery, answers)

    return questionId[0]

def findChoiceId(
    waclient,
    workloadId,
    lensAlias,
    questionId,
    choiceTitle,
    ):

    # Find a choiceId using the choiceTitle
    try:
        response=waclient.get_answer(
        WorkloadId=workloadId,
        LensAlias=lensAlias,
        QuestionId=questionId
        )
    except botocore.exceptions.ParamValidationError as e:
        logger.error(f"ERROR - Parameter validation error: {e}")
    except botocore.exceptions.ClientError as e:
        logger.error(f"ERROR - Unexpected error: {e}")

    jmesquery = f"Answer.Choices[?starts_with(Title, `{choiceTitle}`) == `true`].ChoiceId"

    choiceId = jmespath.search(jmesquery, response)

    return choiceId[0]

def updateAnswersForQuestion(
    waclient,
    workloadId,
    lensAlias,
    questionId,
    selectedChoices,
    notes
    ):

    # Update a answer to a question
    try:
        response=waclient.update_answer(
        WorkloadId=workloadId,
        LensAlias=lensAlias,
        QuestionId=questionId,
        SelectedChoices=selectedChoices,
        Notes=notes
        )
    except botocore.exceptions.ParamValidationError as e:
        logger.error(f"ERROR - Parameter validation error: {e}")
    except botocore.exceptions.ClientError as e:
        logger.error(f"ERROR - Unexpected error: {e}")

    # print(json.dumps(response))
    jmesquery = "Answer.SelectedChoices"
    return jmespath.search(jmesquery, response)

def lambda_handler(event, context):
    boto3_min_version = "1.16.38"
    # Verify if the version of Boto3 we are running has the wellarchitected APIs included
    if (packaging.version.parse(boto3.__version__) < packaging.version.parse(boto3_min_version)):
        logger.error(
            f"Your Boto3 version ({boto3.__version__}) is less than {boto3_min_version}. You must ugprade to run this script (pip3 upgrade boto3)"
        )

        exit()
    responseData = {}
    print(json.dumps(event))
    try:
        WORKLOADID = event['ResourceProperties']['WorkloadId']
        PILLAR = event['ResourceProperties']['Pillar']
        LENS = event['ResourceProperties']['Lens']
        QUESTIONANSWERS = event['ResourceProperties']['QuestionAnswers']
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

    for qaList in QUESTIONANSWERS:
        for question, answerList in qaList.items():
            print(question, answerList)
            # First we must find the questionID
            questionId = findQuestionId(WACLIENT,WORKLOADID,LENS,PILLAR,question)
            logger.info("Found QuestionID of '%s' for the question text of '%s'" % (questionId, question))
            choiceSet = [
                findChoiceId(WACLIENT, WORKLOADID, LENS, questionId, answers)
                for answers in answerList
            ]

            logger.info(
                f"All choices we will select for questionId of {questionId} is {choiceSet}"
            )

            # Update the answer for the question
            updateAnswersForQuestion(WACLIENT,WORKLOADID,LENS,questionId,choiceSet,'Added by Python')
    # exit()
    cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData, 'createWAWorkloadHelperFunction')
