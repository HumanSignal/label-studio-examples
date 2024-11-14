from label_studio_sdk.client import LabelStudio
from configparser import ConfigParser
from datetime import date
from Scrape_logs import scrape
import logging
from label_studio_sdk.label_interface.objects import PredictionValue
import smtplib
from email.mime.text import  MIMEText

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
logger.addHandler(handler)


class Monitor:
    def __init__(self, label_studio_url, label_studio_api, label_studio_project_id, labeling_config,
                 total_to_extract,sample_by_date,
                 logs_username, logs_password, logs_bucket,
                 email_sender, email_recipient, smtp_server, smtp_port, email_password):
        self.label_studio_url = label_studio_url
        self.ls, self.project = self.set_up_ls(label_studio_url, label_studio_api, label_studio_project_id,
                                               labeling_config)
        self.total_to_extract = total_to_extract
        self.sample_by_date = sample_by_date
        self.logs_username = logs_username
        self.logs_password = logs_password
        self.logs_bucket = logs_bucket
        self.email_sender = email_sender
        self.email_recipeint = email_recipient
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.email_password = email_password

    def set_up_ls(self, url, api_key, label_studio_project_id, labeling_config):
        """
        set up connection to LS
        :param url: url for your label studio instance
        :param api_key: api key for your label studio instance
        :param labeling_config: the labeling config for your project
        :return: Label Studio connection
        """
        ls = LabelStudio(base_url=url, api_key=api_key)
        if labeling_config:
            label_config = labeling_config
            title = f"Model Monitoring {date.today()}"
        elif label_studio_project_id:
            sample_project = ls.projects.get(id=label_studio_project_id)
            title = f"{sample_project.title} Monitoring {date.today()}"
            label_config = sample_project.label_config
        else:
            logger.info("You must provide either the id of the LS project that you'd like to use "
                        "the config from or a labeling config")
            raise Exception("Config[\"labelstudio\"] must have either the LabelStudioProjectID or the LablingConfig!")

        project = ls.projects.create(
            title=title,
            description=f"Monitoring production model on date {date.today()}",
            label_config=label_config
        )
        logger.info("Successfully created LS Project")
        return ls, project

    def send_email(self):
        logger.info("Sending email notification")
        msg = MIMEText(f"Your project, {self.project.title} has been created in your LabelStudio instance {self.label_studio_url}. Check it out now!")
        msg["Subject"] = "New LabelStudio Project Alert"
        msg["From"] = self.email_sender
        msg["To"] = self.email_recipeint
        with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
            server.login(self.email_sender, self.email_password)
            server.sendmail(self.email_sender, self.email_recipeint.split(','), msg.as_string())

        logger.info("Email notification sent! ")
    def monitor(self):
        """
        Main method of the Monitor class
        :return: a project in LS with the data scraped from your logs as preannotations for monitoring
        """
        data = scrape(logs_username=self.logs_username, logs_password=self.logs_password, logs_bucket=self.logs_bucket, total_to_extract=self.total_to_extract, sample_by_date=self.sample_by_date)
        for task in data:
            task_data = {
                "data":
                    {"question": task["question"]}
            }
            t = self.ls.tasks.create(project=self.project.id, **task_data)
            task_id = t.id
            prediction = PredictionValue(
                model_version=task["model_version"],
                result=[
                    {
                        "from_name": "answer",
                        "to_name": "question",
                        "type": "textarea",
                        "value": {
                            "text": [task["answer"]]
                        }
                    }
                ]
            )
            self.ls.predictions.create(task=task_id, **prediction.model_dump())
            logger.info("Uploaded task to LS")

        self.send_email()


if __name__ == "__main__":
    config = ConfigParser()
    config.read('config.ini')
    label_studio_url = config["labelstudio"]["LabelStudioURL"]
    label_studio_api = config["labelstudio"]["LabelStudioAPI"]
    label_studio_project_id = config["labelstudio"]["LabelStudioProjectID"]
    labeling_config = config["labelstudio"]["LabelingConfig"]
    total_to_extract = config["data"].getint("total_to_extract")
    sample_by_date = config["data"].getboolean("sample_by_date")
    logs_username = config["logs"]["username"]
    logs_password = config["logs"]["api_key"]
    logs_bucket = config["logs"]["bucket"]
    email_sender = config["notifications"]["email_sender"]
    email_recipient = config["notifications"]["email_recipient"]
    smtp_server = config["notifications"]["smtp_server"]
    smtp_port = config["notifications"]["smtp_port"]
    email_password = config["notifications"]["email_password"]

    monitor = Monitor(label_studio_url, label_studio_api, label_studio_project_id, labeling_config,
                      total_to_extract, sample_by_date,
                      logs_username, logs_password, logs_bucket,
                      email_sender, email_recipient, smtp_server, smtp_port, email_password)
    monitor.monitor()
