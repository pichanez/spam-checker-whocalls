#!/usr/bin/env python3
"""Utility for capturing a screenshot and locating UI element coordinates."""

import subprocess
import time
import argparse
import shlex

def run_adb_command(device_id, command):
    """Run an ADB command on the device.

    Args:
        device_id (str): Device ID
        command (str): Command without the 'adb -s device_id' prefix

    Returns:
        str: Command output or None on error
    """
    parts = ["adb", "-s", device_id, *shlex.split(command)]
    full_command = " ".join(parts)
    print(f"Running command: {full_command}")
    
    try:
        result = subprocess.run(
            parts,
            shell=False,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"ADB command failed: {e}")
        print(f"STDERR: {e.stderr}")
        return None

def capture_screenshot(device_id, output_path="screen.png"):
    """Take a screenshot on the device and save it locally.

    Args:
        device_id (str): Device ID
        output_path (str): Path to save the screenshot

    Returns:
        bool: True on success, otherwise False
    """
    # Check which directories are writable
    print("Checking writable directories...")
    directories = ["/data/local/tmp", "/data", "/tmp", "/storage/emulated/0"]
    
    for directory in directories:
        check_cmd = f"shell '[ -w \"{directory}\" ] && echo \"writable\" || echo \"not writable\"'"
        result = run_adb_command(device_id, check_cmd)
        print(f"Directory {directory}: {result.strip() if result else 'check failed'}")
    
    # Use /data/local/tmp instead of /sdcard
    remote_path = "/data/local/tmp/screen.png"
    
    # Take screenshot and store on the device
    screenshot_cmd = f"shell screencap -p {remote_path}"
    if run_adb_command(device_id, screenshot_cmd) is None:
        return False
    
    # Pull screenshot from the device
    pull_cmd = f"pull {remote_path} {output_path}"
    if run_adb_command(device_id, pull_cmd) is None:
        return False
    
    print(f"Screenshot saved to {output_path}")
    return True

def get_ui_dump(device_id, output_path="ui_dump.xml"):
    """Get the device UI dump and save it locally.

    Args:
        device_id (str): Device ID
        output_path (str): Path to save the XML dump

    Returns:
        bool: True on success, otherwise False
    """
    # Use /data/local/tmp instead of /sdcard
    remote_path = "/data/local/tmp/ui_dump.xml"
    
    # Run uiautomator dump on the device
    dump_cmd = f"shell uiautomator dump {remote_path}"
    if run_adb_command(device_id, dump_cmd) is None:
        return False
    
    # Pull XML dump from the device
    pull_cmd = f"pull {remote_path} {output_path}"
    if run_adb_command(device_id, pull_cmd) is None:
        return False
    
    print(f"UI dump saved to {output_path}")
    return True

def launch_app(device_id, package_name, activity_name):
    """Launch an application on the device.

    Args:
        device_id (str): Device ID
        package_name (str): Application package name
        activity_name (str): Activity name

    Returns:
        bool: True if the app was started successfully, otherwise False
    """
    launch_cmd = f"shell am start -n {package_name}/{activity_name}"
    result = run_adb_command(device_id, launch_cmd)
    
    if result and "Error" not in result:
        print("Application started successfully")
        time.sleep(2)  # Give the app time to load
        return True
    else:
        print("Failed to start application")
        return False

def main():
    """Main function of the script."""
    parser = argparse.ArgumentParser(
        description='Capture screenshot and UI dump to determine coordinates'
    )
    parser.add_argument(
        '--device',
        '-d',
        default='127.0.0.1:5555',
        help='Device ID in IP:port format',
    )
    parser.add_argument(
        '--launch',
        '-l',
        action='store_true',
        help='Launch the app before capturing data',
    )
    
    args = parser.parse_args()
    
    if args.launch:
        package_name = "com.kaspersky.who_calls"
        activity_name = ".LauncherActivityAlias"
        launch_app(args.device, package_name, activity_name)
    
    # Take screenshot
    timestamp = int(time.time())
    screenshot_path = f"screen_{timestamp}.png"
    if not capture_screenshot(args.device, screenshot_path):
        print("Failed to capture screenshot")
    
    # Get UI dump
    ui_dump_path = f"ui_dump_{timestamp}.xml"
    if not get_ui_dump(args.device, ui_dump_path):
        print("Failed to get UI dump")
    
    print("\nTo determine element coordinates:")
    print(f"1. Open screenshot {screenshot_path} in an image editor")
    print("2. Hover over the desired element to see its coordinates")
    print(f"3. Open UI dump {ui_dump_path} in a text editor for additional element info")
    
    return 0

if __name__ == "__main__":
    exit(main())