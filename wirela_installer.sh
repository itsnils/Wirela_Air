sudo yes | apt install python3-pip
sudo yes | apt-get install python-pigpio python3-pigpio
sudo yes | apt-get install libopenjp2-7
sudo yes | apt-get install python3-pymysql
sudo yes | pip3 install smbus
sudo yes | pip3 install scd30_i2c
sudo yes | pip3 install adafruit-blinka
sudo yes | pip3 install adafruit-circuitpython-dotstar
sudo yes | apt-get install libtiff5
sudo yes | pip3 install luma.oled
sudo yes | pip3 install getmac
sudo pigpiod
sudo rm -r /home/pi/Wirela_Air/Images/
sudo mkdir /home/pi/Wirela_Air_Settings
sudo mv /home/pi/Wirela_Air/wirela_air_settings.txt /home/pi/Wirela_Air_Settings/wirela_air_settings.txt
