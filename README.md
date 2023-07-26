# Weather Forecast

---
In this project, a machine learning model for weather prediction in the city of Krasnodar was developed and introduced into the prod.

## Technology Stack

---
* **Pandas, Scikit-learn, MLFlow**
* **Apache Airflow, Docker, REST**
* **PostgreSQL**

## System Architecture

---
The main calculations take place on a deployed local cloud. In Apache Airflow,
the first DAG implements the ETL process, loading up-to-date data from several weather stations in Krasnodar every hour, 
processes them and uploads them to the database. 
The second DAG is triggered from this database and performs precipitation prediction using the model deployed in the Docker container.
<p></p>
<img src="/home/dity/PycharmProjects/weather_forecast/weather_forecast.drawio.png"/>
<p></p>

*Weather update DAG`s architecture:*
<img src="/home/dity/PycharmProjects/weather_forecast/update_dag.png" title='DAG "weather_update"'>

*Weather precipitation prediction DAG`s architecture:*
<img src="/home/dity/PycharmProjects/weather_forecast/pred_dag.png" title="DAG &quot;weather prediction&quot;"/>

## Machine Learning Model

---
A number of experiments were carried out and an ensemble model 
was chosen to solve the problem, namely GradientBoostingClassifier. 
After training on the data for the last 5 years, 
the following results were obtained:
<img src="/home/dity/PycharmProjects/weather_forecast/training_confusion_matrix.png"/>
