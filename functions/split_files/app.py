from aws_lambda_powertools import Tracer, Logger
from collections import defaultdict
import tarfile
import boto3
import json
from urllib.parse import urlparse

MIN_CONFIDENCE_SCORE = 0.99
s3 = boto3.resource('s3')
tracer = Tracer()
logger = Logger(serialize_stacktrace=True)

@tracer.capture_lambda_handler
@logger.inject_lambda_context
def lambda_handler(event, _):
    """
    Parses the results from comprehend into a structured list of documents for further processing

    Accept response:
    {
        "Outcome: "ACCEPTED",
        "Documents": [
            ...
            {
                "Classification": {
                    "File": "file-name.pdf",
                    "DocumentType": "ScannedPDF",
                    "DocumentMetadata": {
                        "PageNumber": 1,
                        "Pages": 10
                    },
                    "Version": "2023-03-20",
                    "Classes": [
                    {
                        "Name": "FIRST_PAGE",
                        "Score": 1
                    },
                    {
                        "Name": "BLANK",
                        "Score": 0
                    },
                    {
                        "Name": "PAGE",
                        "Score": 0
                    }
                    ]
            },
            "OCR": "Text extracted from the document.",
            }
        ]
    }

    Reject reasons:
        UNCLASSIFIED_PAGES: some pages could not be classified due to low confidence by Amazon Comprehend. The unprocessed pages can be found in the UnprocessedPages field.
        ERROR: something went wrong during processing. More details can be found in the ErrorMessage field.
    """

    try:
        logger.info(f"Initializing splitting.")
        pages, unprocessed_pages = process_comprehend_data(event)
        documents = classify_pages(event, pages, unprocessed_pages)
        result = {
            "Outcome": "ACCEPTED",
            "Documents": documents
        }

        if len(unprocessed_pages) > 0:
            result["Outcome"] = "REJECTED"
            result["Reason"] = "UNCLASSIFIED_PAGES"
            result["ErrorMessage"] = "Some pages were not classified"
            result["UnprocessedPages"] = list(map(str, unprocessed_pages))

        logger.info(f"Split completed (outcome = {result['Outcome']}).")
        return result
    except Exception as e:
        logger.error(f"Error during splitting: {e}")
        logger.exception(e)
        return {
            "Outcome": "REJECTED",
            "Reason": "ERROR",
            "ErrorMessage": str(e)
        }


def process_comprehend_data(event):
    """
    Download the results from comprehend, unpackage and load into a reference list
    """

    pages = defaultdict(lambda: {'Classification': {}, 'OCR': {}})
    unprocessed_pages = []

    with tarfile.open(download_file(event), "r:gz") as tar:
        for tar_item in tar.getmembers():
            file = tar.extractfile(tar_item)

            if file is None:
                continue
            elif tar_item.name.endswith(".out"):
                parse_manifest(pages, unprocessed_pages, file)
            else:
                parse_page(pages, tar_item, file)

    logger.info(f"Processed {len(pages.keys())} pages ({len(unprocessed_pages)} unprocessed).")
    return pages, unprocessed_pages


def parse_page(pages, item, file):
    """
    Extract the OCR results from textract and add it to the page dict
    """

    page = int(item.name.split("/")[-1].strip())
    pages[page]["OCR"] = extract_text_from_textract_results(
        json.loads(file.read()))


def parse_manifest(pages: dict, unprocessed_pages: list, file):
    """
    Parse the comprehend manifest file
    """

    total_pages = -1

    for line in file.readlines():
        item = json.loads(line)
        page = int(item["DocumentMetadata"]["PageNumber"])

        if total_pages < 0:
            total_pages = int(item["DocumentMetadata"]["Pages"])
            unprocessed_pages.extend(list(range(1, total_pages + 1)))

        unprocessed_pages.remove(page)
        pages[page]['Classification'] = item


def classify_pages(event, pages: dict, unprocessed_pages: list):
    """
    Classify the pages into documents by selecting the class of the highest confidence. If confidence is lower than MIN_CONFIDENCE_SCORE, refuse classification.
    """

    execution_id = event["ExecutionId"]
    source_file = event["DocumentClassificationJobProperties"]["InputDataConfig"]["S3Uri"]
    documents = []
    current_document = None

    for pageNumber in sorted(pages.keys()):
        page = pages[pageNumber]
        score, identified_class = max_scored_class(page)

        if score < MIN_CONFIDENCE_SCORE:
            unprocessed_pages.append(
                int(page['Classification']['DocumentMetadata']['PageNumber']))
        elif identified_class == 'FIRST_PAGE':
            if current_document:
                documents.append(current_document)

            current_document = {
                "ExecutionId": execution_id,
                "Source": source_file,
                "Pages": [page]
            }
        elif identified_class == 'PAGE':
            current_document["Pages"].append(page)

    documents.append(current_document)

    return documents


def download_file(event):
    """
    Download the Comprehend results file from Amazon S3 to the temp folder
    """

    output_data = event["DocumentClassificationJobProperties"]["OutputDataConfig"]["S3Uri"]
    temp_file = "/tmp/output.tar.gz"

    s3_path = urlparse(output_data)
    bucket = s3_path.netloc
    key = s3_path.path.lstrip('/')
    s3.Object(bucket, key).download_file(temp_file)

    return temp_file


def max_scored_class(page):
    """
    Extract the class with the highest confidence
    """

    classes = page['Classification']['Classes']
    max_scored = max(classes, key=lambda x: x['Score'])

    return max_scored['Score'], max_scored['Name']


def extract_text_from_textract_results(item):
    """
    Extract the text from the textract results
    """

    text = ''
    for block in item["Blocks"]:
        if block['BlockType'] == 'LINE':
            text += block['Text'] + "\n"

    return text.strip()