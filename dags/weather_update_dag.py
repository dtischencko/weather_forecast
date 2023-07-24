#  api_upload --> load to database
from airflow.decorators import dag, task
from airflow.models import Variable, Connection
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.datasets import Dataset

import pandas as pd
from pandas import DataFrame
import numpy as np

from datetime import datetime
import urllib.error
import urllib.request
import sys


COUNT_DATA_THRESHOLD = 10
pg_table = Dataset(Connection.get_connection_from_secrets("postgres_weather").get_uri() + "?table=public.keys")


@dag(
    dag_id="weather_update_dag",
    description="Every hour dag update actually data from weather api",
    start_date=datetime(2023, 1, 1),
    schedule="@hourly",
    catchup=False,
    tags=["WEATHER_FORECAST"]
)
def weather_update_dag():

    @task(task_id="extract_from_api")
    def extract_weather_metrics(**kwargs):
        ti = kwargs["ti"]
        weather_api = Variable.get("weather_api")
        date_saved = datetime.now()
        try:
            response = urllib.request.urlopen(
                f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/Russia%2C%20Krasnodar/today?unitGroup=metric&include=days&key={weather_api}&contentType=csv")
            data = pd.read_csv(response)
            ti.xcom_push("date_saved", date_saved)
            ti.xcom_push("data", data.values.tolist())
            ti.xcom_push("columns", data.columns.tolist())
        except urllib.error.HTTPError as e:
            error_info = e.read().decode()
            print('Error code: ', e.code, error_info)
            sys.exit()
        except urllib.error.URLError as e:
            error_info = e.read().decode()
            print('Error code: ', e.code, error_info)
            sys.exit()

    @task(task_id="data_transform")
    def data_transform(**kwargs):
        ti = kwargs["ti"]
        df = DataFrame(data=ti.xcom_pull(task_ids='extract_from_api', key='data'),
                       columns=ti.xcom_pull(task_ids='extract_from_api', key='columns'))
        df_for_pred = df.drop(
            ['name', 'conditions', 'datetime', 'description', 'moonphase', 'precipprob', 'preciptype', 'snow',
             'snowdepth', 'stations', 'sunrise', 'sunset', 'severerisk'], axis=1)
        df_for_pred['windgust'] = df_for_pred['windgust'].fillna(0.0)
        df_for_pred = df_for_pred.drop(['icon'], axis=1)
        df_for_pred = df_for_pred.astype(np.float64)
        df_for_pred['uvindex'] = df_for_pred['uvindex'].astype(np.int64)
        ti.xcom_push("data", df_for_pred.values.tolist())
        ti.xcom_push("columns", df_for_pred.columns.tolist())

    @task.branch(task_id="check_data_threshold")
    def check_data_threshold():
        conn = PostgresHook(postgres_conn_id="postgres_weather").get_conn()
        cur = conn.cursor()
        cur.execute("""SELECT COUNT(*) FROM public.keys""")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        if count > COUNT_DATA_THRESHOLD:
            print(f"more than {COUNT_DATA_THRESHOLD}: {count}")
            return 'clear_excess_data'
        print(f"less than {COUNT_DATA_THRESHOLD}: {count}")
        return 'load_to_postgres'

    clear_excess_data = PostgresOperator(
        task_id="clear_excess_data",
        postgres_conn_id="postgres_weather",
        sql="""DELETE FROM public.keys WHERE id != (SELECT id FROM public.keys ORDER BY date_saved DESC LIMIT 1);"""
    )

    @task(task_id="load_to_postgres", trigger_rule='none_failed_or_skipped', outlets=[pg_table])
    def load_to_postgres(**kwargs):
        ti = kwargs["ti"]
        date_saved = ti.xcom_pull(task_ids='extract_from_api', key='date_saved')
        df = DataFrame(data=ti.xcom_pull(task_ids='data_transform', key='data'),
                       columns=ti.xcom_pull(task_ids='data_transform', key='columns'))
        df['uvindex'] = df['uvindex'].astype(np.int64)
        conn = PostgresHook(postgres_conn_id="postgres_weather").get_conn()
        pg_cursor = conn.cursor()
        pg_cursor.execute(f"INSERT INTO public.keys (date_saved, tempmax, tempmin, temp, feelslikemax, feelslikemin, feelslike, dew, humidity, precip, precipcover, windgust, windspeed, winddir, sealevelpressure, cloudcover, visibility, solarradiation, solarenergy, uvindex) VALUES ('{date_saved}', '{df['tempmax'].item()}', '{df['tempmin'].item()}', '{df['temp'].item()}', '{ df['feelslikemax'].item() }', '{ df['feelslikemin'].item() }', '{ df['feelslike'].item() }', '{ df['dew'].item() }', '{ df['humidity'].item()}', '{ df['precip'].item() }', '{ df['precipcover'].item() }', '{ df['windgust'].item() }', '{ df['windspeed'].item() }', '{ df['winddir'].item() }', '{ df['sealevelpressure'].item() }', '{ df['cloudcover'].item() }', '{ df['visibility'].item() }', '{ df['solarradiation'].item() }', '{ df['solarenergy'].item() }', '{df['uvindex'].item()}')")
        conn.commit()
        pg_cursor.close()
        conn.close()

    branching = check_data_threshold()
    load = load_to_postgres()
    extract = extract_weather_metrics()
    transform = data_transform()
    extract >> transform >> branching >> [load, clear_excess_data]
    clear_excess_data >> load


weather_update_dag()
