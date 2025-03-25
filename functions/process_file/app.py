from aws_lambda_powertools import Logger, Tracer
import boto3
from urllib.parse import urlparse
from pypdf import PdfReader, PdfWriter

s3 = boto3.resource('s3')
tracer = Tracer()
logger = Logger(serialize_stacktrace=True)

@tracer.capture_lambda_handler
@logger.inject_lambda_context
def lambda_handler(event, _):
    """
    Review the splitted pages from the previous steps and create a new pdf file with the selected range.
    """

    source_file = event["Source"]
    work_bucket = event["WorkBucket"]
    work_prefix = event["WorkPrefix"]
    
    tracer.put_annotation(key="MapIndex", value=event["MapIndex"])
    logger.append_context_keys(MapIndex=event["MapIndex"])
    logger.info(f"Initializing processing.")

    try:
        o = urlparse(source_file)
        bucket = o.netloc
        key = o.path.lstrip('/')

        logger.info(f"Downloading source file.")
        temp_file = f"/tmp/in.pdf"
        s3.Object(bucket, key).download_file(temp_file)
        pages = event["Pages"]

        with open(temp_file, "rb") as inputStream:
            inputpdf = PdfReader(inputStream)
            output = PdfWriter()
            firstpage = -1
            lastpage = 0

            for page in pages:
                pagenum = page["Classification"]["DocumentMetadata"]["PageNumber"] - 1
                if firstpage == -1:
                    firstpage = pagenum + 1
                lastpage = pagenum + 1

                output.add_page(inputpdf.pages[pagenum])

            logger.info(f"Adding pages {firstpage}-{lastpage} to the output file.")
            outfile = f"{work_prefix}/{firstpage}-{lastpage}/out.pdf"
            with open("/tmp/out.pdf", "wb") as outputStream:
                output.write(outputStream)

            logger.info(f"Uploading output file.")
            s3.Object(work_bucket, outfile).upload_file("/tmp/out.pdf")

            event["Outcome"] = "ACCEPTED"
            event["OutputBucket"] = work_bucket
            event["OutputKey"] = outfile
            event["OutputFolder"] = f"{work_prefix}/{firstpage}-{lastpage}/"
 
            logger.info(f"Processing completed (outcome = {event["Outcome"]}).")
            return event
    except Exception as e:
        logger.error(f"Error during processing: {e}")
        logger.exception(e)
        return {
            "Outcome": "REJECTED",
            "Reason": "ERROR",
            "ErrorMessage": str(e)
        }
