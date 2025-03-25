import boto3
from urllib.parse import urlparse
from pypdf import PdfReader, PdfWriter

s3 = boto3.resource('s3')


def lambda_handler(event, _):
    """
    Review the splitted pages from the previous steps and create a new pdf file with the selected range.
    """

    source_file = event["Source"]
    work_bucket = event["WorkBucket"]
    work_prefix = event["WorkPrefix"]

    try:
        o = urlparse(source_file)
        bucket = o.netloc
        key = o.path.lstrip('/')

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

            outfile = f"{work_prefix}/{firstpage}-{lastpage}/out.pdf"
            with open("/tmp/out.pdf", "wb") as outputStream:
                output.write(outputStream)

            s3.Object(work_bucket, outfile).upload_file("/tmp/out.pdf")

            event["OutputFolder"] = f"{work_prefix}/{firstpage}-{lastpage}/"
            event["Output"] = f"{work_bucket}/{outfile}"
            event["Outcome"] = "ACCEPTED"

            return event
    except Exception as e:
        return {
            "Outcome": "REJECTED",
            "Reason": "ERROR",
            "ErrorMessage": str(e)
        }
