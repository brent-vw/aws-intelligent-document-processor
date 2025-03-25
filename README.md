# aws-intelligent-document-processor
This repository allows you to leverage intelligent document processing to split up a stack of similar files and leverage Generative AI to extract key properties from each file. By default the application will delete processed files after 7 days. Training data is not automatically deleted.

## Training data
The training data contains 2 parts. The training file in `manifest.csv` and corresponding training data in `train_data`. 
To train the model both have to be stored in the `TrainBucket` (which can be found in the stack outputs) Amazon S3 bucket. An example has been provided in this repository under the `train` folder.

### Training file
The training file is a csv named `manifest.csv` with the following format and without header:

### Training data
```
PageType,FileName,PageNumber
```

* `PageType` - one of:
    * `FIRST_PAGE` for the first page of current document
    * `PAGE` part of the current document
    * `BLANK` blank page to be discarded
* `FileName` - the name of the file in the `train_data` folder
* `PageNumber` - the page of the document that this row refers to (note: the index starts at 1 _not 0_)


## Bedrock
Make sure to enable model access for `Amazon Nova Lite` and to fill in the prompt in `functions/bedrockProcessor/prompt.py` (see `prompt.example.py`). `prompt.py` is .gitignored by default, make sure to remove it from `.gitignore` if you want to keep it.

## Deploying
Deployment can be done through the aws sam cli.
First build the application with `sam build`.

Then you can deploy by calling `sam deploy`. If its your first time deploying you can call `sam deploy --guided --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM` to set the initial parameters

## Acting on Processing results
Processing results are stored in 2 Amazon SQS queues a Processed Queue where the successfully processed items are stored an a FailedQueue that notifies you of failed activities.

### Processed Queue Format
```json
{
    "Output":"<Amazon S3 location of result pdf>",
    "Result": {
        "": "<JSON object with attributes extracted by bedrock>"
    },
    "Source":"s3://aws-intelligent-document-processor-resultbucket-roofajl2zngm/20a27e05-e591-a5b2-971f-f4d3115c3876_dea4a484-9600-02df-33dc-3cbdccad2aee/source.pdf",
    "WorkBucket":"<Amazon S3 bucket name>",
    "WorkPrefix":"<Amazon S3 folder with all processing results>",
    "OutputFolder":"<Amazon S3 folder with processing results for this step>",
    "ExecutionId":"<Id of the step function execution>",
    "MapIndex": "<number: Number of the subfile that has been processed>",
}
```

### Failed Queue Format
```json
{
    "Reason":"<Reason Code>",
    "Payload":{
        "Outcome":"REJECTED",
        "Reason":"<Reason Detail>",
        "ErrorMessage":"<Error Message>"
        }
    }
```

## Integrating with the solution
The relevant parameters to integrate with the solution are published as cloudformation outputs:
* `TrainBucket`: The name of the Amazon S3 bucket used to store the training data and manifest
* `TrainClassifierStateMachine`: The Amazon Step Functions state machine to run when you want to create a new classification model
* `ProcessBucket`: The name of the Amazon S3 bucket where the files to be processed can be dropped
* `ResultBucket`: The name of the Amazon S3 bucket where the results are stored
* `ProcessedQueue`: The Amazon SQS queue where the succesfully processed results are stored
* `FailedQueue`: The Amazon SQS queue where the failed results are stored
* `ProcessingPolicy`: A managed IAM policy that will give your application the minimum set of premissions required to integrate with the solution
