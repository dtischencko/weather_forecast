#  upload from database --> doing prediction --> load to database
from airflow.decorators import dag, task
from airflow.models import Connection
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.http.hooks.http import HttpHook
from airflow.datasets.manager import Dataset

from pandas import DataFrame

from datetime import datetime
import json
from weather_update_dag import COUNT_DATA_THRESHOLD


pg_table = Dataset(Connection.get_connection_from_secrets("postgres_weather").get_uri() + "?table=public.keys")


@dag(
    dag_id="weather_predict_dag",
    description="Every time when database updates then prediction triggers",
    start_date=datetime(2023, 1, 1),
    schedule=[pg_table],
    catchup=False,
    tags=["WEATHER_FORECAST"]
)
def weather_predict_dag():

    @task(task_id="extract_prepared_data")
    def extract_prepared_data(**kwargs):
        ti = kwargs["ti"]
        conn = PostgresHook(postgres_conn_id="postgres_weather").get_conn()
        pg_cursor = conn.cursor()
        pg_cursor.execute("""SELECT * FROM public.keys WHERE id = (SELECT id FROM public.keys ORDER BY date_saved DESC LIMIT 1);""")
        data = [d for d in pg_cursor.fetchall()[0]]
        columns = [d[0] for d in pg_cursor.description]
        date_saved = data[1]
        data = [data[2:]]
        columns = columns[2:]
        print(data, '\n', columns)
        pg_cursor.close()
        conn.close()
        ti.xcom_push("date_saved", date_saved)
        ti.xcom_push("data", data)
        ti.xcom_push("columns", columns)

    @task(task_id="do_prediction")
    def do_prediction(**kwargs):
        ti = kwargs["ti"]
        data = ti.xcom_pull(task_ids='extract_prepared_data', key='data')
        columns = ti.xcom_pull(task_ids='extract_prepared_data', key='columns')
        raw_json = DataFrame(data=data, columns=columns).to_json(orient='split')
        pred_json = {"dataframe_split": json.loads(raw_json)}
        one_line_json = json.dumps(pred_json, indent=None)
        print(one_line_json)
        http_conn = HttpHook(http_conn_id="http_weather", method='POST')
        response = http_conn.run(
            endpoint='/invocations',
            data=one_line_json,
            headers={
                'Content-Type': 'application/json'
            }
        )
        prediction = dict(eval(response.text))["predictions"][0]
        print(prediction)
        ti.xcom_push("prediction", prediction)

    load_to_pg = PostgresOperator(
        task_id="load_to_postgres",
        trigger_rule='none_failed_or_skipped',
        postgres_conn_id="postgres_weather",
        sql="""INSERT INTO public.predictions (date_saved, prediction) VALUES ('{{ ti.xcom_pull(task_ids='extract_prepared_data', key='date_saved') }}', '{{ ti.xcom_pull(task_ids='do_prediction', key='prediction') }}');"""
    )

    @task.branch(task_id="check_data_threshold")
    def check_data_threshold():
        conn = PostgresHook(postgres_conn_id="postgres_weather").get_conn()
        cur = conn.cursor()
        cur.execute("""SELECT COUNT(*) FROM public.predictions""")
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
        sql="""DELETE FROM public.predictions WHERE id != (SELECT id FROM public.predictions ORDER BY date_saved DESC LIMIT 1);"""
    )

    extract_prepared_data() >> do_prediction() >> check_data_threshold() >> [clear_excess_data, load_to_pg]
    clear_excess_data >> load_to_pg


weather_predict_dag()
