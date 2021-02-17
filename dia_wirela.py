from getmac import get_mac_address
import time
import pymysql
import datetime


class Wirela_Diagnosis():
    """
    This module is a diagnostic solution. a connection to a SQL server is established and then messages can be
    passed to help the developer improve the system. the formatting of a message is as follows:
    - The Mac address of the Raspberry Pi
    - The current date with time
    - The runtime of the program/Raspberry Pi
    """
    def __init__(self):
        self.host = None
        self.port = None
        self.user = None
        self.password = None
        self.db = None
        try:
            data = open('/home/pi/Wirela_Air_Settings/mysql_logging.txt', 'r')
            for i in data:
                x = re.split('=|"|\n', i)
                if x[0] == "host":
                    self.host = str(x[2])
                if x[0] == "port":
                    self.port = int(x[2])
                if x[0] == "user":
                    self.user= str(x[2])
                if x[0] == "passwd":
                    self.password = str(x[2])
                if x[0] == "db":
                    self.db = str(x[2])
            print(self.host)
            print(self.port)
            print(self.user)
            print(self.password)
            self.my_db = pymysql.connect(host=self.host, port=self.port, user=self.user, passwd=self.password, db=self.db)
            self.sql_cursor = self.my_db.cursor()
            self.eth_mac = get_mac_address()
        except:
            print("No access from the mySQL server. The access data to the server are not stored in the settings or there is no internet connection. ")
            print("If you do not have access data in the folder /home/pi/Wirela_Air_Settings/database_login.txt, please contact my administrator.")

        self.timestamp_start = None
        self.timestamp_now = None

    def remember_time_now(self):
        """
        The system start time is recorded here.
        :return:
        """
        self.timestamp_start = datetime.datetime.timestamp(datetime.datetime.now())

    def writes_to_database(self, message):
        """
        Here the data is formatted and transferred to the SQL server.
        :param message:
        :return:
        """
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
    diagnosis.remember_time_now()
    diagnosis.writes_to_database("test message")
