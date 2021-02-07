import smbus
from scd30_i2c import SCD30
import time
import board
import adafruit_dotstar as dotstar
import statistics
import threading
import pigpio
from luma.core.interface.serial import i2c, spi
from luma.core.render import canvas
from luma.oled.device import ssd1306, ssd1325, ssd1331, sh1106
from PIL import ImageFont
from subprocess import *
import dia_wirela
import os


class wirela_air():

    def __init__(self):
        """
        This is a module that runs on a Raspberry Pi Zero. It will read various sensors
        (carbon dioxide, temperature, humidity and the VOC (in process) to average the values and display on an
        OLED display. to the help come two LED displays and two buttons.
        Also a buzzer is built so that is alarmed at a horchen CO2 value.
        """
        # Watchdog
        self.software_watchdog = True
        self.hardware_watchdog = True # todo not yet implemented - under development
        self.watchdog_scd30 = None
        self.watchdog_sht30 = None
        self.watchdog_spg40 = None
        self.watchdog_piezo_buzzers = None
        self.watchdog_oled_display = None
        self.watchdog_led = None
        self.watchdog_button = None
        self.watchdog_code = None
        self.error_counter = 0

        # Sesnors
        # Sensirion SCD30
        self.co2 = None
        self.co2_average_list = []
        self.co2_median = None
        self.scd30 = SCD30()
        self.scd30.set_measurement_interval(2)
        self.scd30.start_periodic_measurement()
        # Sensirion SGP40 todo sensor is not in operation. VOC algorithm must be programmed first.
        self.tvoc = None
        self.tvoc_median = None
        # Sensirion SHT30
        self.temp = None
        self.temp_median = None
        self.temp_average_list = []
        self.humidity = None
        self.humidity_average_list = []
        self.humidity_median = None
        self.sht30_bus = smbus.SMBus(1)

        # Summer
        self.summer_ative = True
        self.alarm_triggered = None
        self.summer_reset = False
        self.summer_alarm_from = 5000
        self.summer_inerval = 0.5  # sek
        self.pi_gpio = pigpio.pi()

        # Dotstar LED todo Adjust brightness. possibly with timer (darker at night)
        # LED 1 top
        self.leds_alarm_ative = True
        self.led_1_color = None
        self.led_1_alarm_0 = 550  # alarm 0 = Blue    < 500 ppm co2
        self.led_1_alarm_1 = 800  # alarm 1 = Green   > 800 ppm co2
        self.led_1_alarm_2 = 1000  # alarm 2 = Orange > 1000 ppm co2
        self.led_1_alarm_3 = 1200  # alarm 3 = Red    > 1200 ppm co2
        # LED 2 bottom
        self.led_2_color = None
        self.led_2_alarm_0 = 10  # alarm 0 = Blue    < 10 ppm tvoc
        self.led_2_alarm_1 = 40  # alarm 1 = Green   > 40 ppm tvoc
        self.led_2_alarm_2 = 100  # alarm 2 = Orange > 100 ppm tvoc
        self.led_2_alarm_3 = 150  # alarm 3 = Red    > 150 ppm tvoc
        self.dots = dotstar.DotStar(board.SCK, board.MOSI, 2, brightness=0.2)

        # OLED Dysplay
        self.dysplay_notification_ativ = True
        self.serial = i2c(port=1, address=0x3C)
        self.oled = ssd1306(self.serial)
        self.font_1 = ImageFont.truetype("./font.otf", 48, encoding="unic")
        self.font_2 = ImageFont.truetype("./font.otf", 12, encoding="unic")

        # Button
        self.button_1 = 0
        self.button_2 = 0

        #Network
        self.wlan0_ip = None

        #Diagnosis
        self.diagnosis_ative = True
        self.connect_to_internet = False
        if self.diagnosis_ative == True:
            self.diagnosis = dia_wirela.Wirela_Diagnosis()

    def read_ini_data(self):
        data = open('./wirela_init.txt', 'r')
        value = data.read().split(",")
        self.diagnosis_ative = str((value[0]))
        self.summer_alarm_from = int(value[1])


    def ping(self):
        hostname = "raspberrypi.org"
        response = os.system("ping -c 1 " + hostname)
        if response == 0:
            self.connect_to_internet = True
            self.diagnosis_ative = True
        else:
            self.connect_to_internet = False
            self.diagnosis_ative = False

    def sensor_sht30(self):
        """
        Here the Sensirion SHT30 sensor is read out and the raw data is converted into humidity and temperature.
        """
        try:
            self.sht30_bus.write_i2c_block_data(0x44, 0x2C, [0x06])
            time.sleep(0.5)
            data = self.sht30_bus.read_i2c_block_data(0x44, 0x00, 6)
            self.temp = ((((data[0] * 256.0) + data[1]) * 175) / 65535.0) - 45
            self.humidity = 100 * (data[3] * 256 + data[4]) / 65535.0
            self.temp_median = self.running_average(self.temp_average_list, self.temp, 30)
            self.humidity_median = self.running_average(self.humidity_average_list, self.humidity, 30)
            self.watchdog_sht30 = "active"
        except:
            self.watchdog_sht30 = "inactive"



    def sensor_scd30(self):
        """
        Here the Sensirion SCD30 sensor is read out and the carbon dioxide value is returned.
        """
        try:
            for i in range(0, 3):
                if self.scd30.get_data_ready():
                    m = self.scd30.read_measurement()
                    self.co2 = m[0]
                    break
                else:
                    time.sleep(0.2)
                    m = None
            self.co2_median = self.running_average(self.co2_average_list, self.co2, 30)
            self.watchdog_scd30 = "active"
        except:
            self.watchdog_scd30 = "inactive"


    def running_average(self, value_list, input_value, number_of_values):
        """
        here the running median is calculated and returned
        :param value_list:
        :param input_value:
        :param number_of_values:
        """
        value_list.append(input_value)
        if len(value_list) > 1:
            output_average = round(statistics.median(value_list), 1)
        if len(value_list) > 60:
            del value_list[0]
        return output_average

    def summer(self):
        """
        Here you define how the buzzer should behave at a defined CO2 limit.
        """
        while True:
            try:
                if not self.co2_median == None:
                    if self.summer_ative == True and self.co2_median > self.summer_alarm_from:
                        if self.summer_reset == False:
                            self.alarm_triggered = True
                            self.pi_gpio.write(21, 1)
                            time.sleep(self.summer_inerval)
                            self.pi_gpio.write(21, 0)
                            time.sleep(self.summer_inerval)
                        else:
                            time.sleep(60*15)
                            self.summer_reset = False
                        if self.summer_ative == False and self.co2_median > self.summer_alarm_from:
                            break
                    else:
                        self.pi_gpio.write(21, 0)
                        self.alarm_triggered = False
                        time.sleep(self.summer_inerval)
                else:
                    time.sleep(self.summer_inerval)
                self.watchdog_piezo_buzzers = "active"
            except:
                self.watchdog_piezo_buzzers = "inactive"


    def light_notification(self):
        """
        Here you define how the LEDs behave. Depending on the CO2 content and VOC content, the color of the LEDs is changed.
        """
        try:
            if self.leds_alarm_ative == True:
                if not self.co2_median == None:
                    if self.co2_median < self.led_1_alarm_0:
                        self.dots[0] = (0, 0, 255)
                        self.led_1_color = "blue"

                    if self.co2_median > self.led_1_alarm_0 and self.co2_median < self.led_1_alarm_1:
                        self.dots[0] = (0, 255, 0)
                        self.led_1_color = "green"

                    if self.co2_median > self.led_1_alarm_1 and self.co2_median < self.led_1_alarm_3:
                        self.dots[0] = (255, 128, 0)
                        self.led_1_color = "orange"

                    if self.co2_median > self.led_1_alarm_3:
                        self.dots[0] = (255, 0, 0)
                        self.led_1_color = "reed"
                else:
                    self.dots[0] = (0, 0, 0)

                if not self.tvoc_median == None:
                    if self.tvoc_median < self.led_2_alarm_0:
                        self.dots[1] = (0, 0, 255)
                        self.led_1_color = "blue"
                    if self.tvoc_median > self.led_2_alarm_1:
                        self.dots[1] = (0, 255, 0)
                        self.led_1_color = "green"
                    if self.tvoc_median > self.led_2_alarm_2:
                        self.dots[1] = (255, 128, 0)
                        self.led_1_color = "orange"
                    if self.tvoc_median > self.led_2_alarm_3:
                        self.dots[1] = (255, 0, 0)
                        self.led_1_color = "reed"
                else:
                    self.dots[1] = (0, 0, 0)
            self.watchdog_led = "active"
        except:
            self.watchdog_led = "inactive"

    def button_S1(self, gpio_button=19): # Button +
        """
        Here you define how button S1 (+ button) should behave.
        :param gpio_button:
        """
        try:
            if (self.pi_gpio.read(gpio_button)) == 0:
                for i in range(0, 16):
                    time.sleep(0.1)
                    if self.alarm_triggered == True:
                        self.summer_reset = True
                    if (self.pi_gpio.read(gpio_button)) == 0:
                        if i == 15:
                            print("Button S1 (+) press >3s")
                            self.dysplay_notification_ativ = False
                            time.sleep(0.5)
                    else:
                        print("Button S1 (+) press <0.1s")
                        self.button_1 = self.button_1 + 1
                        break
            time.sleep(0.05)
            self.watchdog_button = "active"
        except:
            self.watchdog_button = "inactive"
            time.sleep(0.05)

    def button_S2(self, gpio_button=26): # Button -
        """
        Here you define how button S2 (- button) should behave.
        :param gpio_button:
        """
        try:
            if (self.pi_gpio.read(gpio_button)) == 0:
                for i in range(0, 16):
                    time.sleep(0.1)
                    if self.alarm_triggered == True:
                        self.summer_reset = True
                    if (self.pi_gpio.read(gpio_button)) == 0:
                        if i == 15:
                            print("Button S2 (-) press >3s")
                            self.dysplay_notification_ativ = True
                            time.sleep(0.5)
                    else:
                        print("Button S2 (-) press <0.1s")
                        self.button_2 = self.button_2 + 1
                        break
            time.sleep(0.05)
            self.watchdog_button = "active"
        except:
            self.watchdog_button = "inactive"
            time.sleep(0.05)

    def button_S1_S2(self, gpio_button_S1=26, gpio_button_S2=19): # Button + and -
        """
        Here you define how button S1 and button 2 should behave. todo is still under development and not implemented.
        :param gpio_button_S1:
        :param gpio_button_S2:
        """
        try:
            if (self.pi_gpio.read(gpio_button_S1)) == 0 and (self.pi_gpio.read(gpio_button_S2)) == 0:
                for i in range(0, 16):
                    time.sleep(0.1)
                    if (self.pi_gpio.read(gpio_button_S1)) == 0 and (self.pi_gpio.read(gpio_button_S2)) == 0:
                        if i == 15:
                            print("Button S1 + S2 press >3s")
                            time.sleep(0.5)
                    else:
                        break
            time.sleep(0.05)
            self.watchdog_button = "active"
        except:
            self.watchdog_button = "inactive"
            time.sleep(0.05)

    def button_loop(self):
        """
        Here the buttons are queried in a loop
        """
        while True:
            self.button_S1_S2()
            self.button_S1()
            self.button_S2()
            time.sleep(0.05)

    def read_ip_adr(self):
        """
        Here the IP address is queried by the operating system and temporarily stored.
        then serves for the display of the IP address in the setting.
        """
        try:
            p = Popen("ip addr show wlan0 | grep inet | awk '{print $2}' | cut -d/ -f1", shell=True, stdout=PIPE)
            output = p.communicate()[0]
            output = output.decode(encoding='UTF-8', errors='strict')
            self.wlan0_ip = str(output[0:14])
        except:
            pass

    def dysplay_notification(self):
        """
        Here the representation for the display is prepared and passed on to the display.
        the display shows a different measured value every 5 seconds. if the + key is pressed for >3 seconds,
        the settings are displayed. if the minus key is then pressed for >3 seconds,
        the measured values are displayed again.
        todo the settings need to be improved. add display for MAC address.
        more settings like alarm value and at which value the LEDs should change color.
        the acute alarm should also be displayed and can be switched on and off.
        Translated with www.DeepL.com/Translator (free version)
        """
        while True:
            try:
                if self.dysplay_notification_ativ == True:
                    with canvas(self.oled) as draw:
                        if not self.co2_median == None:
                            show_co2 = int(self.co2_median)
                        else:
                            show_co2 = "None"
                        draw.text((0, 0), "Co2 [ ppm ] ", fill="white", font=self.font_2)
                        draw.text((5, 8), str(show_co2), fill="white", font=self.font_1)
                        self.watchdog_oled_display = "active"
                    for i in range(0,50):
                        if self.dysplay_notification_ativ == True:
                            time.sleep(0.1)
                        else:
                            break
                    with canvas(self.oled) as draw:
                        draw.text((0, 0), "Temprature [ °C ] ", fill="white", font=self.font_2)
                        draw.text((5, 8), str(self.temp_median), fill="white", font=self.font_1)
                        self.watchdog_oled_display = "active"
                    for i in range(0,50):
                        if self.dysplay_notification_ativ == True:
                            time.sleep(0.1)
                        else:
                            break
                    with canvas(self.oled) as draw:
                        draw.text((0, 0), "Humidity [ r% ] ", fill="white", font=self.font_2)
                        draw.text((5, 8), str(self.humidity_median), fill="white", font=self.font_1)
                        self.watchdog_oled_display = "active"
                    for i in range(0,50):
                        if self.dysplay_notification_ativ == True:
                            time.sleep(0.1)
                        else:
                            break
                else:
                    time.sleep(0.1)

                if self.dysplay_notification_ativ == False:
                    with canvas(self.oled) as draw:
                        draw.text((0, 0), "Settings >  Nettwork", fill="white", font=self.font_2)
                        draw.text((0, 15), str(self.wlan0_ip), fill="white", font=self.font_2)
                self.watchdog_oled_display = "active"
            except:
                self.watchdog_oled_display = "inactive"

    def loop(self):
        """
        Here the sensors are requested, the values analyzed to determine the LED color and then updated.
        """
        time.sleep(2)
        while True:
            self.sensor_sht30()
            self.sensor_scd30()
            # self.sensor_spg40()
            self.light_notification()
            if not self.co2_median == None:
                print(self.co2_median, self.temp_median, self.humidity_median)

    def hardware_watchdog_petting(self):
        """
        Here the Software watchdog is stroked. if /dev/watchdog is not written for 15 sec. the system will reboot.
        """
        f = open('/dev/watchdog', 'w')
        f.write("S")
        f.close()
        print("Watchdog Reset")

    def software_watchdog_loop(self):
        """
        Here the loops are monitored.
        If an error is reported inert 10 sec.
        this is noted and should more than 5 errors arise the hardware watchdog is not rewritten and the system restarts.
        toto are for example 4 errors arose but they are long ago the value is reset to 0.
        """
        diagnosis_message_sent = False
        while True:
            self.watchdog_button = "reset"
            self.watchdog_code = "reset"
            self.watchdog_spg40 = "reset"
            self.watchdog_scd30 = "reset"
            self.watchdog_oled_display = "reset"
            self.watchdog_piezo_buzzers = "reset"
            time.sleep(10)
            if self.watchdog_oled_display == "reset":
                if self.diagnosis_ative == True:
                    self.diagnosis.writes_to_database("Watchdog Display")
                self.error_counter = self.error_counter + 1
            if self.watchdog_button == "reset":
                if self.diagnosis_ative == True:
                    self.diagnosis.writes_to_database("Watchdog Button")
                self.error_counter = self.error_counter + 1
            if self.watchdog_scd30 == "reset":
                if self.diagnosis_ative == True:
                    self.diagnosis.writes_to_database("Watchdog SCD30")
                self.error_counter = self.error_counter + 1
            if self.watchdog_piezo_buzzers == "reset":
                pass
            if self.watchdog_code == "reset":
                pass
            if self.watchdog_spg40 == "reset":
                pass
            if self.watchdog_sht30 == "reset":
                if self.diagnosis_ative == True:
                    self.diagnosis.writes_to_database("Watchdog SHT30")
            # reset hardware watchdog
            if self.hardware_watchdog == True:
                if not self.error_counter >5:
                    self.hardware_watchdog_petting()
                else:
                    if diagnosis_message_sent == False:
                        if self.diagnosis_ative == True:
                            self.diagnosis.writes_to_database("Watchdog not petted")
                        diagnosis_message_sent = True

    def main(self):
        """
        Everything necessary is started here
        """
        self.diagnosis.remember_time_now()
        if self.diagnosis_ative == True:
            self.diagnosis.writes_to_database("Start")
        self.read_ip_adr()
        t1 = threading.Thread(target=self.loop)
        t1.start()
        t2 = threading.Thread(target=self.dysplay_notification)
        t2.start()
        t3 = threading.Thread(target=self.summer)
        t3.start()
        t4 = threading.Thread(target=self.button_loop)
        t4.start()
        print("Start")
        self.software_watchdog_loop()


run = wirela_air()

run.main()

