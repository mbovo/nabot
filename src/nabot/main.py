#!/usr/bin/env python3
# encoding=utf-8

import lnetatmo
from influxdb import InfluxDBClient
from rich import print
import click
import time


@click.group(help="nabot - Netatmo to InfluxDB/Grafana bot")
def main():
    pass


@main.command(help="Start the bot, it will scrapes NetAtmo APIs every X secs")
@click.option(
    "-i",
    "--id",
    "CLIENT_ID",
    envvar="NABOT_CLIENT_ID",
    required=True,
    default=None,
    help="Netatmo API ID",
)
@click.option(
    "-s",
    "--secret",
    "CLIENT_SECRET",
    envvar="NABOT_CLIENT_SECRET",
    required=True,
    default=None,
    help="Netatmo API Secret",
)
@click.option(
    "-u",
    "--username",
    "USERNAME",
    envvar="NABOT_USERNAME",
    required=True,
    default=None,
    help="Netatmo API username",
)
@click.option(
    "-p",
    "--password",
    "PASSWORD",
    envvar="NABOT_PASSWORD",
    required=True,
    default=None,
    help="Netatmo API password",
)
@click.option(
    "-h",
    "--influx-host",
    "INFLUXDB_HOST",
    envvar="INFLUXDB_HOST",
    required=False,
    default="localhost",
    help="Influx DB hostname",
)
@click.option(
    "-D",
    "--dry-run",
    "DRY_RUN",
    required=False,
    default=False,
    type=click.BOOL,
    is_flag=True,
    help="Dry run, do not write to InfluxDB",
)
@click.option(
    "-t",
    "--interval",
    "INTERVAL",
    required=False,
    default=30,
    help="Interval in seconds between each scrape",
)
def start(
    CLIENT_ID, CLIENT_SECRET, USERNAME, PASSWORD, INFLUXDB_HOST, DRY_RUN, INTERVAL
):
    authorization = lnetatmo.ClientAuth(
        clientId=CLIENT_ID,
        clientSecret=CLIENT_SECRET,
        username=USERNAME,
        password=PASSWORD,
        scope="read_station",
    )

    if not DRY_RUN:
        client = InfluxDBClient(INFLUXDB_HOST)
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

            if not DRY_RUN:
                client.write_points(
                    station_data, time_precision="s", database="netatmo"
                )
                client.write_points(module_data, time_precision="s", database="netatmo")

            print(module_data)
        print(f"Sleep for {INTERVAL}s")
        time.sleep(INTERVAL)
