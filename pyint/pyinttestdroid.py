#!/usr/bin/env python

"""Python module for developing integration tests.
"""

import os
import signal
import subprocess
import threading
import sys
import re
import fdpexpect

from pexpect import ExceptionPexpect
from time import strftime, localtime, sleep, time

TOLERANCE = 0.92

_debug_level = 1

_error_occurred = False

class DeviceInitializationError(Exception):
    """Device initialization error."""
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return repr(self.msg)

class WaitForResponseTimedOutError(Exception):
    """We sent a command and had to wait too long for response."""
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return repr(self.msg)

class DeviceUnresponsiveError(Exception):
    """Device is unresponsive to command."""
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return repr(self.msg)

class AbortError(Exception):
    """Generic exception that indicates a fatal error has occurred and program
    execution should be aborted."""
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return repr(self.msg)

class DeviceUnderTest(object):
    """Class to describe the device under test using Android Debug Bridge (adb)"""
    def __init__(self, device_id, ir_remote=None, is_usb=False):
        self.device_id = device_id
        self.sub_folder_path = "SUB_ROOT_DEFAULT"
        self.image_result_path = "IMAGE_RESULT_ROOT_DEFAULT"
        self.ir_remote = ir_remote
        self.serial_device = None
        self.child = None
        self.is_usb = is_usb

    def initialize_serial_device(self, serial_device_port=None, file_log=None):
        """Initialize a serial console device with the device under test

        Args:
          serial_device_port: device file on the host computer under /dev/ that the serial
             device is attached to (i.e. ttyUSB1)
          file_log: file to log serial console messages
        Returns:
          nothing
        Raises:
          nothing
        """
        self.serial_device = os.open(serial_device_port, os.O_RDWR | os.O_NONBLOCK | os.O_NOCTTY)

        if file_log:
            self.child = fdpexpect.fdspawn(self.serial_device, logfile=file_log)
        else:
            self.child = fdpexpect.fdspawn(self.serial_device)

    def close_serial_device(self):
        """Close serial device file on host computer

        Args:
          nothing
        Returns:
          nothing
        Raises:
          nothing
        """
        if self.serial_device:
            os.close(self.serial_device)

    def press_ir_key(self, keyevent_id, repeat=0, delay=1):
        """Send IR key to device under test

        Args:
          keyevent_id: IR key event ID to send to device under test
          repeat: how many times to repeat the IR key event
          delay: how long the delay should after the IR key is pressed
        Returns:
          nothing
        Raises:
          DeviceInitializationError if IR remote has not been assigned to device under test
        """
        count = 0

        while (count <= repeat):
            count += 1

            if self.ir_remote is None:
                raise DeviceInitializationError('Device under test has no IR remote associated with it.')

            press_command = "irsend SEND_ONCE " + self.ir_remote + " " + keyevent_id

            run_command(press_command, 10, 0)

            sleep(delay)

    def get_specific_device_property(self, specific_property):
        """Get a specific device properties of the device under test

        Args:
          specific_property: Specific android property of a device
        Returns:
          details of the specific android property as string
        Raises:
          nothing
        """
        specific_prop = ""
        if self._is_device_ok():
            specific_prop = str(run_command("adb -s " + self.device_id + " shell getprop " + specific_property, 10, 0))

        return specific_prop

    def _is_device_ok(self):
        output = run_command("adb -s " + self.device_id + " shell ls", 10, 0)

        if "None" not in str(output) and "error" not in str(output):
            return True
        else:
            return self.reconnect_device()

    def root_device(self):
        """Attempts to root device under test. Required if test target build
        is userdebug type

        Args:
          nothing
        Returns:
          True if device was successfully rooted
          False if device was not successfully rooted
        Raises:
          nothing
        """
        run_command("adb -s " + self.device_id + " root", 10, 0)

        return self.reconnect_device()

    def reconnect_device(self):
        """Attempts to reconnect device under test to adb

        Args:
          nothing
        Returns:
          True if reconnected successfully
          False if did not reconnect successfully
        Raises:
          nothing
        """

        success = False

        if self.serial_device is not None:
            try:
                self.child.sendline("")
                self.child.sendline("")
                self.child.sendline("su")
                self.child.expect(".*@(?:android|mt[0-9]+).*", timeout=10)
                # Force dhcp
                self.child.sendline("")
                self.child.sendline("")
                self.child.sendline("netcfg eth0 dhcp")
                self.child.expect(".*@(?:android|mt[0-9]+).*", timeout=10)
                run_command("adb connect " + self.device_id, 10, 0)
            except ExceptionPexpect, e:
                sys.stderr.write('ERROR: %s\n' % str(e))
                raise DeviceUnresponsiveError(e)
        elif self.is_usb is True:
            run_command("adb -s " + self.device_id + " usb", 10, 0)
        else:
            run_command("adb connect " + self.device_id, 10, 0)

        output = run_command("adb -s " + self.device_id + " shell ls", 10, 0)

        if "None" not in str(output) and "error" not in str(output):
            print("Device [" + self.device_id + "] is available after re-connecting.")
            success = True
        else:
            reconnect_attempts = 0

            while reconnect_attempts <= 3:
                if self.is_usb is False:
                    run_command("adb connect " + self.device_id, 10, 0)
                else:
                    run_command("adb -s " + self.device_id + " usb", 10, 0)
                output = run_command("adb -s " + self.device_id + " shell ls", 10, 0)
                if "None" not in str(output) and "error" not in str(output):
                    print("Device [" + self.device_id + "] is available after re-connecting.")
                    success = True
                    break
                else:
                    print("Device [" + self.device_id + "] is offline.")
                    reconnect_attempts += 1

        return success

    def reboot_device(self):
        """Reboots the device under test

        Args:
          nothing
        Returns:
          nothing
        Raises:
          nothing
        """
        print("Rebooting device: " + self.device_id)
        if self.serial_device is not None:
            try:
                self.child.sendline("")
                self.child.sendline("")
                self.child.sendline("su")
                self.child.expect(".*@(?:android|mt[0-9]+).*", timeout=10)
                self.child.sendline("")
                self.child.sendline("")
                self.child.sendline("reboot")
                self.child.expect(".*Restarting system.*", timeout=10)
            except ExceptionPexpect, e:
                sys.stderr.write('ERROR: %s\n' % str(e))
                raise DeviceUnresponsiveError(e)
        else:
            run_command("adb -s " + self.device_id + " reboot", 5, 0)

        # It may take up to 60 secs for a successful reboot
        sleep(60)

    def take_screenshot(self, file_name, folder_name):
        """Takes a screenshot on the device under test

        Args:
          file_name: File name of image to be saved. Do not include the extension
          folder_name: relative folder path of where image should be saved to
        Returns:
          relative path to where image was saved to
        Raises:
          nothing
        """
        file_name = file_name + ".png"

        screencap_command = "adb -s " + self.device_id + " shell /system/bin/screencap -p | sed 's/\r$//' > " + folder_name + "/" + file_name

        if self._is_device_ok():
            screencap_out = str(run_command(screencap_command, 90, 0))

            # If screencap output is NoneType, try it once more
            if (screencap_out is "None" or "error" in screencap_out) and self._is_device_ok():
                screencap_out = run_command(screencap_command, 90, 0)

            debug("screencap result: " + screencap_out)

        return folder_name + "/" + file_name

    def create_result_folder(self, folder_path):
        """Create a result folder

        Args:
          folder_path: relative path where result folder should be created
        Returns:
          relative path to where result folder was created
        Raises:
          nothing
        """
        self.sub_folder_path = strftime(folder_path + "_%d_%b_%Y_%H%M%S", localtime())

        if not os.path.exists(str(self.sub_folder_path)):
            os.mkdir(self.sub_folder_path)

        return self.sub_folder_path

    def create_image_result_folder(self, folder_path):
        """Create a image result folder

        Args:
          folder_path: relative path where image result folder should be created
        Returns:
          relative path to where image result folder was created
        Raises:
          nothing
        """
        self.image_result_path = strftime(folder_path, localtime())

        if not os.path.exists(str(self.image_result_path)):
            os.mkdir(self.image_result_path)

        return self.image_result_path

    def log_execution(self, message, execution_log_filename='execution_log_file.txt'):
        """Append to execution log file with a message with local timestamp

        Args:
          message: message to append to execution log file
          execution_log_filename: file name of log file to append message to
        Returns:
          nothing
        Raises:
          nothing
        """
        if not os.path.exists(str(self.sub_folder_path)):
            os.mkdir(self.sub_folder_path)

        if message:
            logfile = open(str(self.sub_folder_path + "/" + execution_log_filename), "a")
            curr_time = strftime("[%d:%b:%Y:%H:%M:%S]", localtime())
            logfile.write(curr_time + " " + message + "\r\n")
            logfile.close()
            print(message)

    def press_nkey(self, keyevent_id, repeat=1, delay=0.5, message=None):
        """Send key event to device under test

        Args:
          keyevent_id: Android key event ID to send to device under test
          delay: how long (in seconds) sleep should be taken after android
                 key event is sent
          log_message: message to append to execution log file for sending
                 android key event
        Returns:
          nothing
        Raises:
          nothing
        """
        print message
        count = 0

        while (count < repeat):
            count += 1

            press_command = "adb -s " + self.device_id + " shell input keyevent " + str(keyevent_id)

            if self._is_device_ok():
                out = str(run_command(press_command, 10, 0))

                # Try again if press_command generates NoneType
                if ("None" in out or "error" in out) and self._is_device_ok():
                    out = str(run_command(press_command, 10, 0))

                debug("command: " + str(press_command))
                sleep(delay)

    def tap(self, x, y):
        """Perform a tap operation

        Args:
          x: x coordinate of point to tap
          y: y coordinate of point to tap
        Returns:
          nothing
        Raises:
          nothing
        """
        if self._is_device_ok():
            tap_command = "adb -s " + self.device_id + " shell input tap %d %d" % (x, y)
            run_command(tap_command, 5, 0)

    def drag(self, (x0, y0), (x1, y1), duration):
        """Perform a touch drag operation. A long press can be simulated by letting x0=x1 and y0=y1

        Args:
          (x0, y0): Start touch coordinate point for drag
          (x1, y1): End touch coordinate point for drag
          duration: how long the drag motion should last (ms)
        Returns:
          nothing
        Raises:
          nothing
        """
        if self._is_device_ok():
            drag_command = "adb -s " + self.device_id + " shell input touchscreen swipe %d %d %d %d %d" % (x0, y0, x1, y1, duration)
            run_command(drag_command, 5, 0)

    def tap_image(self, expected_image_path):
        """Perform a tap operation on a template image

        Args:
          expected_image_path: file path to template image to tap on
        Returns:
          nothing
        Raises:
          nothing
        """
        try:
            import cv2
            import cv2.cv as cv
        except:
            raise ImportError("cv2 library required. Type \"sudo apt-get install python-numpy python-opencv\" to install")

        img = cv2.imread(expected_image_path, 0)
        height, width = img.shape[:2]

        actual_image_path = strftime("IMAGE_%H%M%S", localtime())
        self.take_screenshot(actual_image_path, self.image_result_path)
        result = sub_image_search(self.image_result_path + "/" + actual_image_path + ".png", expected_image_path)
        assert result[1] > TOLERANCE, expected_image_path + " was not found on screen."
        self.tap(result[3][0], (result[3][1]))

    def handle_test_failure(self):
        """Handle a test failure on the device under test.

        Args:
          nothing
        Returns:
          nothing
        Raises:
          nothing
        """
        new_failure_dir = self.sub_folder_path + "/TEST_FAILURE"

        if not os.path.exists(new_failure_dir):
            os.mkdir(new_failure_dir)

        if self._is_device_ok():
            pull_command = "adb -s " + self.device_id + " pull /data/anr/ " + new_failure_dir
            out = run_command(pull_command, 60, 0)
            debug(str(out))
            self.take_screenshot(strftime("TEST_FAILURE_%H%M%S", localtime()), new_failure_dir)
            bugreport_dump = "adb -s " + self.device_id + " bugreport > " + new_failure_dir + "/bugreport.txt"
            out = run_command(bugreport_dump, 240, 0)
            debug(str(out))

    def android_command(self, command, timeout=30, retry=0):
        """Execute an android command on device under test

        Args:
          command: command to execute on device under test
          timeout: time to wait (seconds) for a response
          retry: number of attempts to retry the command if it fails
        Returns:
          output of response
        Raises:
          nothing
        """
        out = None

        if self._is_device_ok():
            out = str(run_command("adb -s " + self.device_id + " " + command, timeout, retry))

        return out

def match_text(device_under_test, text_dictionary, find=True):
    """Use OCR to match texts on a certain screen

    Args:
      device_under_test: Current device under test
      text_dictionary: dictonary values of text pattern to match and sub rect coordinates i.e. {"pattern" : [x1, y1, x2, y2], ..., ...,}
      find: flag to determine if text should or should not be found on screen
    Returns:
      nothing
    Raises:
      AssertionError
    """

    saved_image_path = device_under_test.take_screenshot(strftime("IMAGE_%H%M%S", localtime()), device_under_test.image_result_path)

    for pattern, coord in text_dictionary.iteritems():
        text = __get_text_from_image(saved_image_path, coord).strip()
        match = re.search(pattern, text)

        if find:
            assert match, pattern + " was not found in extracted text. Extracted text was: " + text.strip()
        else:
            assert not match, pattern + " was found in extracted text. Extracted text was: " + text.strip()

def extract_text(device_under_test, text_coords):
    """Use OCR to extract texts on a certain screen

    Args:
      device_under_test: Current device under test
      texts_for_extraction: 2-d array of coordinates of texts to extract
    Returns:
      texts that are extracted from given coordinates
    Raises:
      nothing
    """

    texts = []
    saved_image_path = device_under_test.take_screenshot(strftime("IMAGE_%H%M%S", localtime()), device_under_test.image_result_path)

    for coord in text_coords:
        texts.append(__get_text_from_image(saved_image_path, coord).strip())

    return texts

def __get_text_from_image(saved_image_path, coord):
    try:
        import cv2
        import cv2.cv as cv
        import tesseract
    except:
        raise ImportError("tesseract library for python required")

    api = tesseract.TessBaseAPI()
    api.Init(".", "eng", tesseract.OEM_DEFAULT)
    api.SetPageSegMode(tesseract.PSM_AUTO)

    image0 = cv2.imread(saved_image_path, cv.CV_LOAD_IMAGE_GRAYSCALE)

    if image0 is None:
        raise cv2.error("Image for text matching was NoneType")
    # x1 = coord[0], y1 = coord[1], x2 = coord[2], y2 = coord[3]
    image1 = image0[coord[1]:coord[3], coord[0]:coord[2]]
    height1, width1 = image1.shape
    iplimage = cv.CreateImageHeader((width1, height1), cv.IPL_DEPTH_8U, 1)
    cv.SetData(iplimage, image1.tostring(), image1.dtype.itemsize * (width1))
    tesseract.SetCvImage(iplimage, api)
    return api.GetUTF8Text()

def match_image(device_under_test, expected_image_paths, find=True):
    """Test verification checkpoint after a test step has been executed

    Args:
      device_under_test: Current device under test
      expected_image_path: relative path to expected image to be found in template image.
      find: flag to determine if image should or should not be found on screen
    Returns:
      nothing
    Raises:
      AssertionError
    """

    actual_image_path = strftime("IMAGE_%H%M%S", localtime())
    device_under_test.take_screenshot(actual_image_path, device_under_test.image_result_path)

    for expected_image_path in expected_image_paths:
        result = sub_image_search(device_under_test.image_result_path + "/" + actual_image_path + ".png", expected_image_path)
        if find:
            assert result[1] > TOLERANCE, expected_image_path + " was not found on screen."
        else:
            assert result[1] < TOLERANCE, expected_image_path + " was found on screen."

def debug(msg):
    """Print debug messages to stderr. Set _debug_level to > 0 to enable

    Args:
      msg: message to print to std err
    Returns:
      nothing
    Raises:
      nothing
    """
    if _debug_level > 0:
        sys.stderr.write(
            "%s: %s\n" % (os.path.basename(sys.argv[0]), str(msg)))

def run_command(cmd, timeout_time=None, retry_count=3, return_output=True,
               stdin_input=None):
    """Spawn and retry a subprocess to run the given shell command.

    Args:
      cmd: shell command to run
      timeout_time: time in seconds to wait for command to run before aborting.
      retry_count: number of times to retry command
      return_output: if True return output of command as string. Otherwise,
        direct output of command to stdout.
      stdin_input: data to feed to stdin
    Returns:
      output of command
    Raises:
      nothing
    """
    debug("cmd = " + cmd)
    result = None
    stop = True
    while stop:
        try:
            result = _run_once(cmd, timeout_time=timeout_time,
                           return_output=return_output, stdin_input=stdin_input)
        except WaitForResponseTimedOutError:
            retry_count -= 1
            debug("No response for %s, retrying" % cmd)
            result = None
            if retry_count <= 0:
                stop = False

        return result

def _run_once(cmd, timeout_time=None, return_output=True, stdin_input=None):
    """Spawns a subprocess to run the given shell command.

    Args:
      cmd: shell command to run
      timeout_time: time in seconds to wait for command to run before aborting.
      return_output: if True return output of command as string. Otherwise,
        direct output of command to stdout.
      stdin_input: data to feed to stdin
    Returns:
      output of command
    Raises:
      errors.WaitForResponseTimedOutError if command did not complete within
        timeout_time seconds.
      errors.AbortError is command returned error code and SetAbortOnError is on.
    """
    cmd_start_time = time()
    so = []
    pid = []
    global _error_occurred
    _error_occurred = False

    def Run():
        global _error_occurred
        if return_output:
            output_dest = subprocess.PIPE
        else:
            output_dest = None
        if stdin_input:
            stdin_dest = subprocess.PIPE
        else:
            stdin_dest = None
        pipe = subprocess.Popen(
            cmd,
            executable="/bin/bash",
            stdin=stdin_dest,
            stdout=output_dest,
            stderr=subprocess.STDOUT,
            shell=True)
        pid.append(pipe.pid)
        try:
            output = pipe.communicate(input=stdin_input)[0]
            if output is not None and len(output) > 0:
                so.append(output)
        except OSError, e:
            debug("failed to retrieve stdout from: %s" % cmd)
            debug(e)
            so.append("ERROR")
            _error_occurred = True
        if pipe.returncode:
            debug("error: %s returned %d error code" % (cmd,
              pipe.returncode))

    t = threading.Thread(target=Run)
    t.start()

    break_loop = False
    while not break_loop:
        if not t.isAlive():
            break_loop = True

        # Check the timeout
        if (not break_loop and timeout_time is not None
            and time() > cmd_start_time + timeout_time):
            try:
                os.kill(pid[0], signal.SIGKILL)
            except OSError:
                pass

            raise WaitForResponseTimedOutError("about to raise a timeout for: %s" % cmd)
        if not break_loop:
            sleep(0.1)

    t.join()
    output = "".join(so)
    if _error_occurred:
        raise AbortError(output)

    return "".join(so)

def select_device():
    """Prompt user to select a device to act as a device under test

    Args:
      nothing
    Returns:
      device id of first online device on adb
    Raises:
      DeviceUnResponsiveError if no online devices are found on adb
    """

    devices = []
    device_id = ""
    outdevices = run_command("adb devices", 10, 0)
    mylist = outdevices.split("\n")

    for i, item in enumerate(mylist):
        # Ignore the first line
        if i > 0 and item is not "" and "????" not in item and "*" not in item and "List" not in item:
            devices.append(item.split()[0])

    if len(devices) < 1:
        raise DeviceUnresponsiveError("No devices found! Please check 'adb devices' output.")
    elif len(devices) == 1:
        device_id = str(devices[0])
        print("Selected device: " + device_id)
    else:
        for i, device in enumerate(devices):
            print(str(i) + "\t" + device)

        while True:
            input_variable = input("Enter index of device that you want to select as device under test [0, 1, 2, ...]:")
            if 0 <= input_variable and input_variable < len(devices):
                device_id = str(devices[input_variable])
                print("Selected device: " + device_id)
                break
            else:
                print("Please select a valid device.")

    return device_id

def sub_image_search(source_img_path, template_img_path):
    """Attempts to search for a sub image within a given template image

    Args:
      source_img_path: relative path of image to be found in template image
      template_img_path: relative path of template image used to find subimage within it
    Returns:
      normalized cross correlation value of the match of the image within the template image
    Raises:
      nothing
    """

    try:
        import cv2
    except:
        raise ImportError("cv2 library required. Type \"sudo apt-get install python-numpy python-opencv\" to install")

    img = cv2.imread(source_img_path)
    template = cv2.imread(template_img_path)
    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    (min_x, max_y, minloc, maxloc) = cv2.minMaxLoc(result)
    debug("min_x: %s max_y: %s minloc: %s maxloc: %s" % (str(min_x), str(max_y), str(minloc), str(maxloc)))
    return (min_x, max_y, minloc, maxloc)
