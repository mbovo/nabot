#!/usr/bin/env python3
# encoding=utf-8

import lnetatmo
from influxdb import InfluxDBClient
from rich import print
import time
import os

CLIENT_ID = os.getenv("NABOT_CLIENT_ID")
CLIENT_SECRET = os.getenv("NABOT_CLIENT_SECRET")
USERNAME = os.getenv("NABOT_USERNAME")
PASSWORD = os.getenv("NABOT_PASSWORD")


def main():
    authorization = lnetatmo.ClientAuth(
        clientId=CLIENT_ID,
        clientSecret=CLIENT_SECRET,
        username=USERNAME,
        password=PASSWORD,
        scope="read_station",
    )

    client = InfluxDBClient(host=os.getenv("NABOT_INFLUXDB_HOST"))
    if {"name": "netatmo"} not in client.get_list_database():
        client.create_database("netatmo")

    while True:

        weatherData = lnetatmo.WeatherStationData(authorization)

        for station in weatherData.stations:
            station_data = []
            module_data = []
            station = weatherData.stationById(station)
            station_name = station["station_name"]
            raw_data = {
                "altitude": station["place"]["altitude"],
                "country": station["place"]["country"],
                "timezone": station["place"]["timezone"],
                "longitude": station["place"]["location"][0],
                "latitude": station["place"]["location"][1],
            }
            for sensor, value in station["dashboard_data"].items():
                if sensor.lower() not in ["time_utc"]:
                    if type(value) == int:
                        value = float(value)
                    module_data.append(
                        {
                            "measurement": sensor.lower(),
                            "tags": {
                                "station": station_name,
                                "module": "Interno",
                            },
                            "time": station["dashboard_data"]["time_utc"],
                            "fields": {"value": value},
                        }
                    )

            modules = station["modules"]
            for module in modules:
                for measurement in [
                    "altitude",
                    "country",
                    "longitude",
                    "latitude",
                    "timezone",
                ]:
                    value = raw_data[measurement]
                    if type(value) == int:
                        value = float(value)
                    station_data.append(
                        {
                            "measurement": measurement,
                            "tags": {
                                "station": station_name,
                                "module": module["module_name"],
                            },
                            "time": module["last_message"],
                            "fields": {"value": value},
                        }
                    )

                for sensor, value in module["dashboard_data"].items():
                    if sensor.lower() not in ["time_utc"]:
                        if type(value) == int:
                            value = float(value)
                        module_data.append(
                            {
                                "measurement": sensor.lower(),
                                "tags": {
                                    "station": station_name,
                                    "module": module["module_name"],
                                },
                                "time": module["dashboard_data"]["time_utc"],
                                "fields": {"value": value},
                            }
                        )

            client.write_points(station_data, time_precision="s", database="netatmo")
            client.write_points(module_data, time_precision="s", database="netatmo")

            print(station)
        print("Sleep for 5s")
        time.sleep(5)
