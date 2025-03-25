import json
import boto3
import json
from prompt import bedrock_prompt
from botocore.config import Config

config = Config(connect_timeout=5, read_timeout=60, retries={
                "total_max_attempts": 20, "mode": "adaptive"})
bedrock = boto3.client(service_name='bedrock-runtime', config=config)
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')


def lambda_handler(event, _):
    # Get doc rules
    try:
        textract_results = ""
        for page in event['Pages']:
            textract_results += f"{page['OCR']}\n"

        create_bedrock_prompt = bedrock_prompt(textract_results)
        event["Result"] = json.loads(call_bedrock(create_bedrock_prompt))
        upload_to_s3(event)

        del event["Pages"]
        event["Outcome"] = "ACCEPTED"
        return event

    except Exception as e:
        return {
            "Outcome": "REJECTED",
            "Reason": "ERROR",
            "ErrorMessage": str(e)
        }


def upload_to_s3(event):
    work_bucket = event["WorkBucket"]
    work_prefix = event["OutputFolder"]
    object_key = f'{work_prefix}/result.json'

    #  upload to S3
    s3.put_object(Bucket=work_bucket, Key=object_key, Body=json.dumps(event))

    return object_key


def call_bedrock(text):
    native_request = {
        "inferenceConfig": {
            "maxTokens": 5000,
            "temperature": 0.00001
        },
        "messages": [
            {
                "role": "user",
                "content": [{"text": text}],
            },
            {
                "role": "assistant",
                "content": [
                    {
                        "text": "{"
                    }
                ],
            }
        ],
    }

    # Using Nova Lite (update as needed)
    modelID = "eu.amazon.nova-lite-v1:0"
    stop_reason = 'max_tokens'
    result = '{'

    while stop_reason == 'max_tokens':
        body = json.dumps(native_request)
        response = bedrock.invoke_model(
            body=body,
            modelId=modelID,
        )
        response = json.loads(response.get("body").read())
        doc_rules = response["output"]["message"]["content"][0]["text"]
        stop_reason = response['stopReason']
        native_request['messages'].append(
            {"role": "assistant", "content": [{"text": doc_rules}]})
        native_request['messages'].append({"role": "user", "content": [
                                          {"text": "Continue the output untill the JSON is finished."}]})
        result += doc_rules

    return result
