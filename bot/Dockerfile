FROM python:3.9
LABEL authors="dity"

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt

CMD ["python", "weather_forecast_bot.py"]