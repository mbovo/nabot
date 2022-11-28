#!/usr/bin/env python3
# encoding=utf-8

import lnetatmo
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
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
    default="http://localhost:8086",
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
@click.option(
    "--influx-token",
    "INFLUXDB_TOKEN",
    envvar="INFLUXDB_TOKEN",
    required=False,
    default=None,
    help="Influx DB token",
)
@click.option(
    "--influx-org",
    "INFLUXDB_ORG",
    envvar="INFLUXDB_ORG",
    required=False,
    default=None,
    help="Influx DB organization",
)
@click.option(
    "--influx-bucket",
    "INFLUXDB_BUCKET",
    envvar="INFLUXDB_BUCKET",
    required=False,
    default="netatmo",
    help="Influx DB bucket",
)
def start(
    CLIENT_ID,
    CLIENT_SECRET,
    USERNAME,
    PASSWORD,
    INFLUXDB_HOST,
    DRY_RUN,
    INTERVAL,
    INFLUXDB_BUCKET,
    INFLUXDB_TOKEN,
    INFLUXDB_ORG,
):
    authorization = lnetatmo.ClientAuth(
        clientId=CLIENT_ID,
        clientSecret=CLIENT_SECRET,
        username=USERNAME,
        password=PASSWORD,
        scope="read_station",
    )

    if not DRY_RUN:
        client = InfluxDBClient(
            INFLUXDB_HOST,
            org=INFLUXDB_ORG,
            token=INFLUXDB_TOKEN,
        ).write_api(write_options=SYNCHRONOUS)

    while True:

        weatherData = lnetatmo.WeatherStationData(authorization)

        points: list[Point] = []

        for station in weatherData.stations:
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
                    points.append(
                        Point(sensor.lower())
                        .field("value", value)
                        .tag("station", station_name)
                        .tag("module", "Interno")
                        .tag("type", "station")
                        .tag("sensor", sensor.lower())
                        .tag(
                            "unit",
                            "°C"
                            if sensor.lower() == "temperature"
                            else "hPa"
                            if sensor.lower() == "pressure"
                            else "%",
                        )
                        .time(time.time_ns(), write_precision="ns")
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
                    points.append(
                        Point(measurement)
                        .field("value", value)
                        .tag("station", station_name)
                        .tag("module", module["module_name"])
                        .tag("type", "module")
                        .tag("sensor", measurement)
                        .tag(
                            "unit",
                            "m"
                            if measurement.lower() == "altitude"
                            else "°"
                            if measurement.lower() in ["longitude", "latitude"]
                            else "",
                        )
                        .time(time.time_ns(), write_precision="ns")
                    )

                for sensor, value in module["dashboard_data"].items():
                    if sensor.lower() not in ["time_utc"]:
                        if type(value) == int:
                            value = float(value)
                        points.append(
                            Point(sensor.lower())
                            .field("value", value)
                            .tag("station", station_name)
                            .tag("module", module["module_name"])
                            .tag("type", "module")
                            .tag("sensor", sensor.lower())
                            .tag(
                                "unit",
                                "°C"
                                if sensor.lower() == "temperature"
                                else "hPa"
                                if sensor.lower() == "pressure"
                                else "%",
                            )
                            .time(time.time_ns(), write_precision="ns")
                        )

            if not DRY_RUN:
                client.write(INFLUXDB_BUCKET, record=points, write_precision="ns")

            print([str(x) for x in points])
        print(f"Sleep for {INTERVAL}s")
        time.sleep(INTERVAL)
