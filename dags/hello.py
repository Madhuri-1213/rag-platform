from datetime import datetime
from airflow.decorators import dag, task

@dag(start_date=datetime(2026, 1, 1), schedule=None, catchup=False)
def hello():
    @task
    def say_hi():
        import arxiv, fitz, boto3  # fails if the image is missing libraries
        print("libraries ok")
    say_hi()
hello()