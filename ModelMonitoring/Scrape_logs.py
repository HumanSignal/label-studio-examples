"""
In this script, you'll scrape your production server logs from wherever they are and format them as
list of dictionaries
"""
from typing import List, Dict
from datetime import date, timedelta
from datetime import datetime
from math import floor
from random import sample
import boto3
from boto3.session import Session


def scrape(logs_username: str, logs_password: str, logs_bucket:str, total_to_extract: int, sample_by_date: bool) -> List[Dict]:
    """
    write this method to process your logs from wherever they are stored
    :return a list of dictionaries containing the output from your model along with any relevant metadata
    """
    end = date.today()
    start = end - timedelta(days=6)
    all_data = []
    # Connect to your server here.
    # In this example, we use an S3 bucket
    session = Session(aws_access_key_id=logs_username, aws_secret_access_key=logs_password)
    s3 = session.resource('s3')
    bucket = s3.Bucket(logs_bucket)

    # for our test, we assume that files have the name "qalogs_MM:DD:YY.txt"
    for s3_file in bucket.objects.all():
         key = s3_file.key
         if "qalogs" in key:
             key_date = key.split(".")[0]
             key_date = key_date.split("_")[1]
             key_date = datetime.strptime(key_date, '%m:%d:%y').date()
             if key_date <= end and key_date >= start:
                 body = s3_file.get()['Body'].read().decode("utf-8")
        #         # the scrape file method does the file processing.
                 all_data.extend(scrape_file(body))

    subset_data = get_data_subset(all_data, total_to_extract, sample_by_date)
    return subset_data


def scrape_file(body):
    # basic file processing template
    # ALL logic will need to be customized based on the format of your logs.
    all_data = []
    if body:
        curr_data = {}
        for line in body.split('\n'):
            if "Timestamp" in line:
                if curr_data:
                    all_data.append(curr_data)
                    curr_data = {}
                line = line.split(' ')
                date = line[1]
                curr_data["date"] = date
            if "User Input" in line:
                line = line.split('User Input: ')
                question = line[1]
                curr_data["question"] = question.strip("\"")
            if "Model Response" in line:
                line = line.split('Model Response: ')
                answer = line[1]
                curr_data["answer"] = answer.strip("\"")
            if "Version" in line:
                line = line.split("Version: ")
                model_version = line[1]
                curr_data["model_version"] = model_version
        if curr_data:
            all_data.append(curr_data)
        return all_data


    else:
        # FOR TESTING PURPOSES ONLY
        question = "What's my name? "
        answer = "Micaela "
        all_data = [{"model_version": 1, "date": "11/05/2024", "question": question, "answer": answer}]
    return all_data


def get_data_subset(all_data, total_to_extract, sample_by_date):
    """
    Get a sample of all your data. If the total len of data is less than the sample size, return all.
    Else, if sample_by_date, take an even sample across all date ranges as for a total as close as we can get
    to the intended sample number while keeping an even sample across all dates.
    :param all_data: a list of dictionaries containing all the data scraped from the logs
    :param total_to_extract: the goal number of samples to have in total
    :param sample_by_date: boolean, if true, sample the subset by date.
    :return:
    """
    if len(all_data) <= total_to_extract:
        return all_data

    if sample_by_date:
        by_date = {}
        for t in all_data:
            if t["date"] not in by_date.keys():
                by_date[t["date"]] = [t]
            else:
                by_date[t["date"]].append(t)

        per_date = floor(total_to_extract / len(by_date.keys()))
        new_data = []
        for date, data in by_date.items():
            random_sample = sample(data, per_date)
            new_data.extend(random_sample)
        return new_data

    #ToDo: Sample by class?

    else:
        random_sample = sample(all_data, total_to_extract)
        return random_sample