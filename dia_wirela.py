from getmac import get_mac_address
import time
import pymysql
import datetime


class Wirela_Diagnosis():
    def __init__(self):
        self.host = None
        self.port = None
        self.user = None
        self.password = None
        self.db = None
        try:
            datei = open('access_data.txt', 'r')
            value = datei.read().split(",")
            self.host = str((value[0]))
            self.port = int(value[1])
            self.user = str(value[2])
            self.password = str(value[3])
            self.db = str(value[4])
            self.my_db = pymysql.connect(host="twisy.i234.me", port=3306, user="diagnosis", passwd="wirela_air", db="Wirela_Air")
            self.sql_cursor = self.my_db.cursor()
            self.eth_mac = get_mac_address()
        except:
            pass
        self.timestamp_start = None
        self.timestamp_now = None

    def remember_time_now(self):
        self.timestamp_start = datetime.datetime.timestamp(datetime.datetime.now())

    def writes_to_database(self, message):
        try:
            now = datetime.datetime.now()
            self.timestamp_now = datetime.datetime.timestamp(now)

            run_time = (self.timestamp_now- self.timestamp_start) / 86400 # sek to day

            sql = """INSERT INTO diagnosis(
            mac_adr,
            timestamp,
            runtime,
            message
            )
            VALUES (%s, %s, %s, %s )
            """
            ts = time.time()
            time_now = datetime.datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
            recordTuple = (self.eth_mac, time_now, run_time, str(message))
            try:
                self.sql_cursor.execute(sql, recordTuple)
                self.my_db.commit()
                print("Sent to the database")
            except:
                self.my_db.rollback()
                print("Error - message not received")
        except:
            pass


if __name__ == '__main__':
    diagnosis = Wirela_Diagnosis()
    diagnosis.
    diagnosis.writes_to_database("test")
