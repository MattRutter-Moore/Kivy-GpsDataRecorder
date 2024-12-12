from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from plyer import gps, uniqueid
from kivy.network.urlrequest import UrlRequest

import json
import datetime
import logging
import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

LOG_FILE = "debug.log"
SQLITE = "db.sqlite"
AZURE_FUNCTIONS_HTTP_ENDPOINT = os.getenv("AZURE_FUNCTIONS_HTTP_ENDPOINT")
AZURE_FUNCTIONS_KEY = os.getenv("AZURE_FUNCTIONS_KEY")

class GpsRecorder(App):

    def build(self):

        # Initiate required attributes
        self.imei = ""
        self.lat = ""
        self.lon = ""
        self.accuracy = ""
        self.speed = ""
        self.speed_unit = ""

        logging.info("build: Attributes initiated")

        # Create SQLite3 database to hold failed uploads and upload current records
        self.create_database()
        self.upload_synchronised_data()

        # Create app layout
        self.layout = BoxLayout(orientation='vertical')

        self.imei_label = Label(text="Fetching IMEI...")
        self.gps_label = Label(text="Fetching GPS...")
        self.http_label = Label(text="HTTP request status...")

        self.layout.add_widget(self.imei_label)
        self.layout.add_widget(self.gps_label)
        self.layout.add_widget(self.http_label)

        # Get Device IMEI
        try:
            imei = uniqueid.id
            self.imei = imei.decode("utf-8")
            self.imei_label.text = f"Device IMEI: {self.imei}"
        except Exception as e:
            self.imei_label.text = f"Error fetching IMEI: {str(e)}"

        # Start GPS service
        try:
            gps.configure(on_location=self.on_location, on_status=self.on_status)
            gps.start(minTime=1000, minDistance=1)  # Minimum time (ms) and distance (meters)
        except Exception as e:
            self.gps_label.text = f"Error starting GPS: {e}"


        # Schedule real-time and synchronised HTTP requests
        Clock.schedule_interval(self.upload_realtime_data, 15)
        Clock.schedule_interval(self.upload_synchronised_data, 600)

        return self.layout

    # GPS functions
    def on_location(self, **kwargs):
        """Callback for GPS location updates."""
        lat = kwargs.get('lat', 'N/A')
        lon = kwargs.get('lon', 'N/A')
        accuracy = kwargs.get('accuracy', 'N/A')
        speed = kwargs.get('speed', 'N/A')

        if speed != 'N/A' and speed is not None:
            speed_unit = "mps"
        else:
            speed_unit = "N/A"

        self.lat = lat
        self.lon = lon
        self.accuracy = accuracy
        self.speed = speed
        self.speed_unit = speed_unit

        logging.info(f"Location: {self.lat}, {self.lon} ({self.accuracy}% accuracy)")
        logging.info(f"Speed: {self.speed} {self.speed_unit}")

        self.gps_label.text = f"GPS: Lat={self.lat}, Lon={self.lon}, Acc={self.accuracy}, Spd={self.speed}"

    def on_status(self, stype, status):
        """Callback for GPS status updates."""
        self.gps_label.text = f"GPS status: {stype} - {status}"


    # Handle data upload
    def upload_realtime_data(self, dt):

        timestamp = datetime.datetime.now().isoformat()

        req_body = {
            # "latitude": self.lat,
            # "longitude": self.lon,
            # "reading_datetime": timestamp,
            # "device_type": "mobile",
            # "device_uuid": self.imei,
            # "upload_type": "real-time",
            # "accuracy": self.accuracy,
            # "speed": self.speed,
            # "speed_unit": self.speed_unit,
            # "upload_datetime": timestamp
            "latitude": 37.7749,
            "longitude": -122.4194,
            "reading_datetime": timestamp,
            "device_type": "mobile",
            "device_uuid": self.imei,
            "upload_type": "real-time",
            "accuracy": 0.95,
            "speed": 25.5,
            "speed_unit": "mps",
            "upload_datetime": timestamp
        }

        logging.info("upload_realtime_data: http request body prepared")
        self.send_http_request(req_body)
        

    def upload_synchronised_data(self):

        try: 
            connection = sqlite3.connect(SQLITE)
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM location_data")
            rows = cursor.fetchall()
            logging.info(f"upload_synchronised_data: {len(rows)} records retrieved from database for upload")
        except sqlite3.Error as e:
            logging.error(f"upload_synchronised_data: {e}")
        finally:
            connection.close()

        if rows is not None:
            for row in rows:
                req_body = {
                    "latitude": row['latitude'],
                    "longitude": row['longitude'],
                    "reading_datetime": row['reading_datetime'],
                    "device_type": row['device_type'],
                    "device_uuid": row['device_uuid'],
                    "upload_type": row['upload_type'],
                    "accuracy": row['accuracy'],
                    "speed": row['speed'],
                    "speed_unit": row['speed_unit'],
                    "upload_datetime": datetime.datetime.now().isoformat()
                }

                self.send_http_request(request_body=req_body)

    def send_http_request(self,request_body):
                
        url = AZURE_FUNCTIONS_HTTP_ENDPOINT
        req_headers = {
            "Content-Type": "application/json",
            "X-Functions-Key": AZURE_FUNCTIONS_KEY
        }

        timeout = 5
        method = "POST"
        
        UrlRequest(
            url=url, 
            on_success=self.http_success,
            on_failure=self.http_failure,
            on_redirect=self.http_redirect,
            on_error=self.http_error,
            req_body=json.dumps(request_body),
            req_headers=req_headers,
            timeout=timeout,
            method=method
        )


 
    # HTTP Response handlers
    def http_success(self, request, result):

        logging.info("http_success: http request successful")

        try:
            self.http_label.text = "Request status {} - Success - {}".format(
                request.resp_status, 
                request.resp_headers["Date"]
            )
        except Exception as e:
            logging.error(f"http_success: {e} ({type(e)})")
        finally:
            request_body = json.loads(request.req_body)
            if request_body["upload_type"] == "synchronised":
                logging.info(f"DELETE {request_body['reading_datetime']}")
                self.delete_from_database(request_body["reading_datetime"])

    def http_failure(self, request, result):

        logging.info(f"http_failure: {result}")

        try:
            self.http_label.text = "Request status {} - Failure - {}".format(
                request.resp_status, 
                request.resp_headers["Date"]
            )
        except Exception as e:
            logging.error(f"http_failure: {e} ({type(e)})")
        finally:
            request_body = json.loads(request.req_body)
            if request_body["upload_type"] == "real-time":
                self.add_to_database(request_body)

    def http_redirect(self, request, result):

        logging.info(f"http_redirect: {result}")

        try:
            self.http_label.text = "Request status {} - Redirect - {}".format(
                request.resp_status, 
                request.resp_headers["Date"]
            )   
        except Exception as e:
            logging.error(f"http_redirect: {e} ({type(e)})")
        finally:
            request_body = json.loads(request.req_body)
            if request_body["upload_type"] == "real-time":
                self.add_to_database(request_body)

    def http_error(self, request, error):
        try:
            logging.info(f"http_error: {error}")

            self.http_label.text = "Request status {} - Error - {}".format(
                request.resp_status, 
                request.resp_headers["Date"]
            )

        except Exception as e:
            logging.error(f"http_error: {e} ({type(e)})")
            self.http_label.text = f"({datetime.datetime.now().isoformat()}) Error identified. Please contact IT Service Desk if error persists."
        finally:
            request_body = json.loads(request.req_body)
            if request_body["upload_type"] == "real-time":
                self.add_to_database(request_body)

    
    



    # Database setup
    def create_database(self):
        try:
            connection = sqlite3.connect(SQLITE)
            cursor = connection.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS location_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,               -- Unique ID for each entry
                    latitude REAL NOT NULL,                             -- Latitude (floating-point number)
                    longitude REAL NOT NULL,                            -- Longitude (floating-point number)
                    reading_datetime TEXT NOT NULL,                     -- Date and time in ISO 8601 format
                    device_type TEXT NOT NULL DEFAULT "mobile",         -- Device type (e.g., "mobile", "tablet")
                    device_uuid TEXT NOT NULL,                          -- Unique identifier for the device
                    upload_type TEXT NOT NULL DEFAULT "synchronised",   -- Type of upload (e.g., "real-time")
                    accuracy REAL,                                      -- Accuracy of the data (e.g., 0.95)
                    speed REAL,                                         -- Speed of the device
                    speed_unit TEXT NOT NULL DEFAULT "mps"              -- Unit of speed (default "kph")
                );
            """)

            connection.commit()
            logging.info("create_database: database initiated")
        except sqlite3.Error as e:
            logging.error(f"create_datebase: {e}")
        finally:
            connection.close()

    def add_to_database(self, request):
        try:
            connection = sqlite3.connect(SQLITE)
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO location_data (
                    latitude,
                    longitude,
                    reading_datetime,
                    device_uuid,
                    accuracy,
                    speed
                ) 
                VALUES (
                    ?, ?, ?, ?, ?, ?
                )
                """, 
                (
                    request['latitude'],
                    request['longitude'],
                    request['reading_datetime'],
                    request['device_uuid'],
                    request['accuracy'],
                    request['speed']
                )
            )
            
            connection.commit()
            logging.info(f"add_to_database: failed request ({request['reading_datetime']}) inserted into database")
        except sqlite3.Error as e:
            logging.error(f"add_to_database: {e}")
        finally:
            connection.close()

    def delete_from_database(self, reading_datetime):

        try:
            connection = sqlite3.connect(SQLITE)
            cursor = connection.cursor()
            cursor.execute("DELETE FROM location_data WHERE reading_datetime = ?", (reading_datetime,))
            connection.commit()
            logging.info(f"delete_from_database: failed request ({reading_datetime}) successfully deleted from database")
        except sqlite3.Error as e:
            logging.error(f"delete_from_database: {e}")
        finally:
            connection.close()



if __name__ == "__main__":
    GpsRecorder().run()
