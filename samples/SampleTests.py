#!/usr/bin/env python

import unittest
from pyint import pyinttestdroid
from time import sleep

class SampleTests(unittest.TestCase):

    def setUp(self):
        sub_folder_path = device_under_test.create_result_folder(root_folder_path + "/" +  self._testMethodName)
        device_under_test.create_image_result_folder(sub_folder_path + "/IMAGE_RESULTS")

    # Assume that imdb icon is present on screen before test is executed
    def test_imdb_search_avatar(self):
        device_under_test.tap_image('source_img/imdb_icon.png')
        sleep(5)
        device_under_test.tap_image('source_img/search.png')
        pyinttestdroid.run_command("adb shell input text avatar", 5, 0)
        pyinttestdroid.run_command("adb shell input keyevent KEYCODE_ENTER", 5, 0)
        sleep(3)
        pyinttestdroid.match_image(device_under_test, ['source_img/avatar_poster.png'], find=True)

if __name__ == '__main__':
    global device_under_test
    global root_folder_path

    device_under_test = pyinttestdroid.DeviceUnderTest(pyinttestdroid.select_device(), ir_remote=None, is_usb=True)
    root_folder_path = device_under_test.create_result_folder("ROOT_RESULT")
    unittest.main()
