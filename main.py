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
import Sensirion_SGP40
import os
import re


class wirela_air():

    def __init__(self):
        """
        This is a module that runs on a Raspberry Pi Zero. It will read various sensors
        (carbon dioxide, temperature, humidity and the VOC (in process) to average the values and display on an
        OLED display. to the help come two LED displays and two buttons.
        Also a buzzer is built so that is alarmed at a horchen CO2 value.
        """
        # current software version
        self.software_version = "v2.0.22|01.04.21"

        # Watchdog
        self.software_watchdog = None
        self.hardware_watchdog = None
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

        # Sensirion SGP40
        self.voc = None
        self.voc_median = None
        self.voc_average_list = []
        self.sgp40_warm_up = False
        self.sgp40 = Sensirion_SGP40.Sensirion_SGP40(bus=1, relative_humidity=50, temperature_c=25)

        # Sensirion SHT30
        self.temp = None
        self.temp_median = None
        self.temp_average_list = []
        self.humidity = None
        self.humidity_average_list = []
        self.humidity_median = None
        self.sht30_bus = smbus.SMBus(1)

        # Summer
        self.summer_active = True
        self.alarm_triggered = None
        self.summer_reset = False
        self.summer_alarm_from = 5000
        self.summer_inerval = 0.5  # sek
        self.pi_gpio = pigpio.pi()

        # Dotstar LED todo Adjust brightness. possibly with timer (darker at night)
        # LED 1 top
        self.leds_alarm_active = True
        self.leds_night_mode = None
        self.leds_night_mode_off_time = None
        self.leds_night_mode_on_time = None
        self.leds_night_mode_brightness = None
        self.leds_brightness = 100 # %
        self.led_1_color = None
        self.led_1_alarm_0 = 550    # optimal   - alarm 0 = Blue
        self.led_1_alarm_1 = 800    # good      - alarm 1 = Green
        self.led_1_alarm_2 = 1000   # attention - alarm 2 = Orange
        self.led_1_alarm_3 = 1200   # alarm     - alarm 3 = Red
        # LED 2 bottom
        self.led_2_color = None
        self.led_2_alarm_0 = 50     # alarm 0 = Blue
        self.led_2_alarm_1 = 150    # alarm 1 = Green
        self.led_2_alarm_2 = 200    # alarm 2 = Orange
        self.led_2_alarm_3 = 300    # alarm 3 = Red
        self.dots = dotstar.DotStar(board.SCK, board.MOSI, 2, brightness=0.2)

        # OLED Dysplay
        self.display_notification_active = True
        self.display_night_mode = None
        self.display_off_time = None
        self.display_on_time = None
        self.serial = i2c(port=1, address=0x3C)
        self.oled = ssd1306(self.serial)
        self.font_1 = ImageFont.truetype("/home/pi/Wirela_Air/font.otf", 48, encoding="unic")
        self.font_2 = ImageFont.truetype("/home/pi/Wirela_Air/font.otf", 12, encoding="unic")
        self.display_unit_behind_measured_value = None
        self.max_settings_pages = 1 # value + 1 = settings pages

        # Button
        self.button = 0
        self.button_1_for_3_sec = None
        self.button_2_for_3_sec = None

        #Network
        self.wlan0_ip = None

        #Update
        self.automatic_software_update = None

        #Diagnosis
        self.diagnosis_active = True
        self.connect_to_internet = False
        if self.diagnosis_active == True:
            self.diagnosis = dia_wirela.Wirela_Diagnosis()

    def read_settings_data(self):
        """
        The settings from the wirela_air_settings.txt file are read and transferred here.
        """
        try:
            data = open('/home/pi/Wirela_Air_Settings/wirela_air_settings.txt', 'r')
            for i in data:
                wirela_air_settings_data = re.split('=|"|\n', i)
                # todo not finish
                if wirela_air_settings_data[0] == "hardware_watchdog":
                    if wirela_air_settings_data[2] == "True":
                        self.hardware_watchdog = True
                        print("WG on")
                    if wirela_air_settings_data[2] == "Fasle":
                        self.hardware_watchdog = False
                        print("WG off")

                if wirela_air_settings_data[0] == "summer_active":
                    if wirela_air_settings_data[2] == "True":
                        self.summer_active = True
                    if wirela_air_settings_data[2] == "Fasle":
                        self.summer_active = False

                if wirela_air_settings_data[0] == "summer_alarm_from":
                    self.summer_alarm_from = int(wirela_air_settings_data[2])

                if wirela_air_settings_data[0] == "leds_alarm_active":
                    if wirela_air_settings_data[2] == "True":
                        self.leds_alarm_active = True
                    if wirela_air_settings_data[2] == "Fasle":
                        self.leds_alarm_active = False

                if wirela_air_settings_data[0] == "display_notification_active":
                    if wirela_air_settings_data[2] == "True":
                        self.display_notification_active = True
                    if wirela_air_settings_data[2] == "Fasle":
                        self.display_notification_active = False

                if wirela_air_settings_data[0] == "diagnosis_active":
                    if wirela_air_settings_data[2] == "True":
                        self.diagnosis_active = True
                    if wirela_air_settings_data[2] == "Fasle":
                        self.diagnosis_active= False

                if wirela_air_settings_data[0] == "leds_brightness":
                    self.leds_brightness = int(wirela_air_settings_data[2])

                if wirela_air_settings_data[0] == "co2_LED_value_optimal":
                    self.led_1_alarm_0 = int(wirela_air_settings_data[2])

                if wirela_air_settings_data[0] == "co2_LED_value_good":
                    self.led_1_alarm_1 = int(wirela_air_settings_data[2])

                if wirela_air_settings_data[0] == "co2_LED_value_attention":
                    self.led_1_alarm_2 = int(wirela_air_settings_data[2])

                if wirela_air_settings_data[0] == "co2_LED_value_alarm":
                    self.led_1_alarm_3 = int(wirela_air_settings_data[2])

                if wirela_air_settings_data[0] == "voc_LED_value_optimal":
                    self.led_2_alarm_0 = int(wirela_air_settings_data[2])

                if wirela_air_settings_data[0] == "voc_LED_value_good":
                    self.led_2_alarm_1 = int(wirela_air_settings_data[2])

                if wirela_air_settings_data[0] == "voc_LED_value_attention":
                    self.led_2_alarm_2 = int(wirela_air_settings_data[2])

                if wirela_air_settings_data[0] == "voc_LED_value_alarm":
                    self.led_2_alarm_3 = int(wirela_air_settings_data[2])

                if wirela_air_settings_data[0] == "display_unit_behind_measured_value":
                    if wirela_air_settings_data[2] == "True":
                        self.display_unit_behind_measured_value = True
                    if wirela_air_settings_data[2] == "Fasle":
                        self.display_unit_behind_measured_value = False

                if wirela_air_settings_data[0] == "display_night_mode":
                    if wirela_air_settings_data[2] == "True":
                        self.display_night_mode = True
                    if wirela_air_settings_data[2] == "Fasle":
                        self.display_night_mode = False

                if wirela_air_settings_data[0] == "leds_night_mode":
                    if wirela_air_settings_data[2] == "True":
                        self.leds_night_mode = True
                    if wirela_air_settings_data[2] == "Fasle":
                        self.leds_night_mode = False

                if wirela_air_settings_data[0] == "display_off_time":
                    self.display_off_time = str(wirela_air_settings_data[2])

                if wirela_air_settings_data[0] == "display_on_time":
                    self.display_on_time = str(wirela_air_settings_data[2])

                if wirela_air_settings_data[0] == "leds_night_mode_off_time":
                    self.leds_night_mode_off_time = str(wirela_air_settings_data[2])

                if wirela_air_settings_data[0] == "leds_night_mode_on_time":
                    self.leds_night_mode_on_time = str(wirela_air_settings_data[2])

                if wirela_air_settings_data[0] == "leds_night_mode_brightness":
                    self.leds_night_mode_brightness = int(wirela_air_settings_data[2])

                if wirela_air_settings_data[0] == "automatic_software_update":
                    if wirela_air_settings_data[2] == "True":
                        self.automatic_update = True
                    if wirela_air_settings_data[2] == "Fasle":
                        self.automatic_update = False

        except:
            print("Error no wirela_air_settings.txt")

    def ping(self):
        """
        checks whether there is an internet connection to GitHub.
        """
        hostname = "github.com"
        response = os.system("ping -c 1 " + hostname)
        if response == 0:
            self.connect_to_internet = True
            self.diagnosis_active = True
        else:
            self.connect_to_internet = False
            self.diagnosis_active = False

    def update(self):
        """
        Here the Wirela_Air directory is deleted and the new version is downloaded from Github.
        """
        print(os.system("cd /home/pi/"))
        print(os.system("sudo rm -r /home/pi/Wirela_Air"))
        print(os.system("sudo git clone https://github.com/itsnils/Wirela_Air.git"))
        print("reboot now")
        os.system("sudo reboot")

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

    def sensor_sgp40(self):
        try:
            if self.sgp40_warm_up == False:
                self.sgp40.begin(10)
                self.sgp40_warm_up = True

            if self.sgp40_warm_up == True:
                if not self.temp_median is None or self.humidity_median is None:
                    self.sgp40.set_envparams(self.humidity_median, self.temp_median)
                    self.voc = self.sgp40.get_voc_index()
                    self.voc_median = int(self.running_average(self.voc_average_list, self.voc, 30))
                    self.watchdog_spg40 = "active"
        except:
            self.watchdog_spg40 = "inactive"


    def running_average(self, value_list, input_value, number_of_values):
        """
        here the running median is calculated and returned
        :param value_list:
        :param input_value:
        :param number_of_values:
        """
        value_list.append(input_value)
        if len(value_list) <= 1:
            output_average = None
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
                    if self.summer_active == True and self.co2_median > self.summer_alarm_from:
                        if self.summer_reset == False:
                            self.alarm_triggered = True
                            self.pi_gpio.write(21, 1)
                            time.sleep(self.summer_inerval)
                            self.pi_gpio.write(21, 0)
                            time.sleep(self.summer_inerval)
                        else:
                            time.sleep(60*15)
                            self.summer_reset = False
                        if self.summer_active == False and self.co2_median > self.summer_alarm_from:
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

    def led_brightness(self, color):
        if not color == 0 or self.leds_brightness == 0:
            brightness = int((color/100) * self.leds_brightness)
        return brightness



    def light_notification(self):
        """
        Here you define how the LEDs behave. Depending on the CO2 content and VOC content, the color of the LEDs is changed.
        """
        try:
            if self.leds_alarm_active == True:
                if not self.co2_median == None:
                    if self.co2_median < self.led_1_alarm_0:
                        self.dots[0] = (0, 0, self.led_brightness(255))
                        self.led_1_color = "blue"

                    if self.co2_median > self.led_1_alarm_0 and self.co2_median < self.led_1_alarm_1:
                        self.dots[0] = (0, self.led_brightness(255), 0)
                        self.led_1_color = "green"

                    if self.co2_median > self.led_1_alarm_1 and self.co2_median < self.led_1_alarm_3:
                        self.dots[0] = (self.led_brightness(255), self.led_brightness(128), 0)
                        self.led_1_color = "orange"

                    if self.co2_median > self.led_1_alarm_3:
                        self.dots[0] = (self.led_brightness(255), 0, 0)
                        self.led_1_color = "reed"
                else:
                    self.dots[0] = (0, 0, 0)

                if not self.voc_median == None:
                    if self.voc_median < self.led_2_alarm_0:
                        self.dots[1] = (0, 0, self.led_brightness(255))
                        self.led_1_color = "blue"
                    if self.voc_median > self.led_2_alarm_1:
                        self.dots[1] = (0, self.led_brightness(255), 0)
                        self.led_1_color = "green"
                    if self.voc_median > self.led_2_alarm_2:
                        self.dots[1] = (self.led_brightness(255), self.led_brightness(128), 0)
                        self.led_1_color = "orange"
                    if self.voc_median > self.led_2_alarm_3:
                        self.dots[1] = (self.led_brightness(255), 0, 0)
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
                            self.display_notification_active= False
                            self.button_1_for_3_sec = True
                            time.sleep(0.5)
                    else:
                        print("Button S1 (+) press <0.1s")
                        if not self.max_settings_pages >= self.button:
                            self.button = self.button + 1
                        else:
                            self.button = self.max_settings_pages
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
                            self.display_notification_active = True
                            self.button_2_for_3_sec = True
                            time.sleep(0.5)
                    else:
                        print("Button S2 (-) press <0.1s")
                        if not 0 <= self.button:
                            self.button = self.button - 1
                        else:
                            self.button = 0
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
                if self.display_notification_active == True:
                    with canvas(self.oled) as draw:
                        if not self.co2_median == None:
                            show_co2 = int(self.co2_median)
                        else:
                            show_co2 = "None"
                        draw.text((0, 0), "Co2 [ ppm ] ", fill="white", font=self.font_2)
                        draw.text((5, 8), str(show_co2), fill="white", font=self.font_1)
                        self.watchdog_oled_display = "active"
                    for i in range(0,50):
                        if self.display_notification_active == True:
                            time.sleep(0.1)
                        else:
                            break
                    with canvas(self.oled) as draw:
                        draw.text((0, 0), "VOC Index", fill="white", font=self.font_2)
                        draw.text((5, 8), str(self.voc_median), fill="white", font=self.font_1)
                        self.watchdog_oled_display = "active"
                    for i in range(0,50):
                        if self.display_notification_active == True:
                            time.sleep(0.1)
                        else:
                            break
                    with canvas(self.oled) as draw:
                        draw.text((0, 0), "Temprature [ °C ] ", fill="white", font=self.font_2)
                        draw.text((5, 8), str(self.temp_median), fill="white", font=self.font_1)
                        self.watchdog_oled_display = "active"
                    for i in range(0,50):
                        if self.display_notification_active == True:
                            time.sleep(0.1)
                        else:
                            break
                    with canvas(self.oled) as draw:
                        draw.text((0, 0), "Humidity [ r% ] ", fill="white", font=self.font_2)
                        draw.text((5, 8), str(self.humidity_median), fill="white", font=self.font_1)
                        self.watchdog_oled_display = "active"
                    for i in range(0,50):
                        if self.display_notification_active == True:
                            time.sleep(0.1)
                        else:
                            break
                else:
                    time.sleep(0.1)
                """
                Settings
                """
                if self.display_notification_active == False:
                    time.sleep(0.5)
                    print('{}{}'.format("Button pos.", self.button))
                    if self.button == 0:
                        with canvas(self.oled) as draw:
                            draw.text((0, 0), "Settings >  Nettwork", fill="white", font=self.font_2)
                            draw.text((0, 15), str(self.wlan0_ip), fill="white", font=self.font_2)
                    if self.button == 1:
                        with canvas(self.oled) as draw:
                            self.button_1_for_3_sec = False
                            draw.text((0, 0), "Settings >  Version", fill="white", font=self.font_2)
                            draw.text((0, 15), str(self.software_version), fill="white", font=self.font_2)
                            draw.text((0, 28), str("Update your software?"), fill="white", font=self.font_2)
                            draw.text((0, 40), str("+ Button for >3 seconds."), fill="white", font=self.font_2)
                        if self.button_1_for_3_sec == True:
                            self.button_1_for_3_sec = False
                            with canvas(self.oled) as draw:
                                draw.text((0, 0), "Settings >  Version", fill="white", font=self.font_2)
                                draw.text((0, 15), str("Internet? please wait..."), fill="white", font=self.font_2)
                                self.connect_to_internet = None
                                self.ping()
                                time.sleep(5)
                            if self.connect_to_internet == True: #todo Something not right.
                                self.software_watchdog = False
                                with canvas(self.oled) as draw:
                                    draw.text((0, 0), "Settings >  Version", fill="white", font=self.font_2)
                                    draw.text((0, 15), str("Software is being updated."), fill="white",font=self.font_2)
                                    draw.text((0, 28), str("Please wait 2-4 minutes."), fill="white",font=self.font_2)
                                    self.update()
                                    time.sleep(2)
                            else:
                                with canvas(self.oled) as draw:
                                    draw.text((0, 0), "Settings >  Version", fill="white", font=self.font_2)
                                    draw.text((0, 15), str("No internet available"), fill="white", font=self.font_2)
                                    time.sleep(2)




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
            self.sensor_sgp40()
            self.light_notification()
            if not self.co2_median == None:
                print('| {}ppm CO2 | VOC index {} |{}°C Temp. | {}% rh |'.format(self.co2_median, self.voc_median, self.temp_median, self.humidity_median))

    def hardware_watchdog_petting(self):
        """
        Here the Software watchdog is stroked. if /dev/watchdog is not written for 15 sec. the system will reboot.
        """
        f = open('/dev/watchdog', 'w')
        f.write("S")
        f.close()
        print("Watchdog petting")

    def stop_watchdog(self):
        f = open('/dev/watchdog', 'w')
        f.write("V")
        f.close()
        print("Watchdog stopped")

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
                if self.diagnosis_active == True:
                    self.diagnosis.writes_to_database("Watchdog Display")
                self.error_counter = self.error_counter + 1
            if self.watchdog_button == "reset":
                if self.diagnosis_active == True:
                    self.diagnosis.writes_to_database("Watchdog Button")
                self.error_counter = self.error_counter + 1
            if self.watchdog_scd30 == "reset":
                if self.diagnosis_active == True:
                    self.diagnosis.writes_to_database("Watchdog SCD30")
                self.error_counter = self.error_counter + 1
            if self.watchdog_piezo_buzzers == "reset":
                pass
            if self.watchdog_code == "reset":
                pass
            if self.watchdog_spg40 == "reset":
                if self.diagnosis_active == True:
                    self.diagnosis.writes_to_database("Watchdog SGP40")
                self.error_counter = self.error_counter + 1
            if self.watchdog_sht30 == "reset":
                if self.diagnosis_active == True:
                    self.diagnosis.writes_to_database("Watchdog SHT30")
            # reset hardware watchdog
            if self.hardware_watchdog == True:
                if not self.error_counter >6:
                    self.hardware_watchdog_petting()
                else:
                    self.stop_watchdog()
                    if diagnosis_message_sent == False:
                        if self.diagnosis_active == True:
                            self.diagnosis.writes_to_database("Watchdog not petted")
                        diagnosis_message_sent = True

    def main(self):
        """
        Everything necessary is started here
        """
        self.ping()
        self.read_settings_data()
        self.diagnosis.remember_time_now()
        if self.diagnosis_active == True:
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