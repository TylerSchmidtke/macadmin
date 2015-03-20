#!/usr/bin/python

# PrefPaneUtil.py
# Author: Tyler Schmidtke
# Version: 1.0
# Date: 3/20/2015
# Description: Tool for locking/unlocking OS X System Preferences Panes. Hides any locked panes from view.
# Tested: OS X 10.10

from Foundation import NSMutableArray
import CoreFoundation
import glob
import os
import subprocess
import sys

# Retrieve list of currently locked panes
locked_panes = CoreFoundation.CFPreferencesCopyValue("DisabledPreferencePanes", "com.apple.systempreferences",
                                                     "kCFPreferencesAnyUser", "kCFPreferencesCurrentHost")

# Set dictionaries for available preference panes
system_panes = {}
other_panes = {}


def print_help():
    print("""
This tool is designed to lock/unlock OS X System Preference Panes. In addition to
locking the pane, it also hides the pane from view. Preference panes are specified
by their Bundle Identifier, found in the Info.plist file found in each .prefPane directory.
Available arguments are as follows:

 -h, --help  : Print this help page
 --list      : List available preference panes
 --locked    : List currently locked preference panes
 --unlock    : Unlock a list of preference pane bundle identifiers. Example:
               ./PrefPaneUtil.py --unlock "com.apple.preference.sound, com.apple.prefs.backup"

 --lock      : Lock a list of preference pane bundle identifiers. Example:
               ./PrefPaneUtil.py --lock "com.apple.preference.sound, com.apple.prefs.backup"

 --restore   : Restore the list of preference panes locked before running --unlockall
 --unlockall : Unlock all preference panes
    """)


# Retrieve available panes for listing and verifying lock/unlock bundle identifiers.
def get_bundle_identifiers():
    # Get the available system level preference panes
    os.chdir("/System/Library/PreferencePanes/")
    for directory in glob.glob("*.prefPane"):
        system_path = "/System/Library/PreferencePanes/" + directory.strip() + "/Contents/Info.plist"
        system_panes[directory.split('.')[0]] = subprocess.check_output(["/usr/bin/defaults", "read", system_path,
                                                                         "CFBundleIdentifier"]).rstrip()

    # Get the available 3rd party preference panes
    os.chdir("/Library/PreferencePanes/")
    for directory in glob.glob("*.prefPane"):
        other_path = "/Library/PreferencePanes/" + directory.strip() + "/Contents/Info.plist"
        other_panes[directory.split('.')[0]] = subprocess.check_output(["/usr/bin/defaults", "read", other_path,
                                                                        "CFBundleIdentifier"]).rstrip()

# Print a list of system and 3rd party preference
def list_bundle_identifiers():
    template = "{0:25}{1:45}"

    # List available system level preference panes
    print(template.format("-" * 25, "-" * 45))
    print(template.format("System Panes", "Bundle Identifiers"))
    print(template.format("-" * 25, "-" * 45))
    for key, value in system_panes.iteritems():
        print(template.format(key, value))
    print(template.format("-" * 25, "-" * 45))

    # List available 3rd party preference panes an
    print(template.format("3rd Party Panes", "Bundle Identifiers"))
    print(template.format("-" * 25, "-" * 45))
    for key, value in other_panes.iteritems():
        print(template.format(key, value))
    print(template.format("-" * 25, "-" * 45))


# List currently locked preference panes
def list_current_locked():
    if locked_panes == None:
        print("No preference panes are currently locked")
        sys.exit(1)
    else:
        print("-" * 45)
        print("Locked Preference Panes")
        print("-" * 45)
        for pane in locked_panes:
            print(pane)
        print("-" * 45)

"""
Verify the current user's com.apple.systempreferences.plist does not contain DisabledPreferencePanes
or HiddenPreferencePane keys. These will override the settings in
/Library/Preferences/com.apple.systempreferences.plist. I don't know of a way to modify another user's
preferences (other than the one running the script) via CFPrefs, so we'll run defaults as the current user.
"""


def sanity_check():
    # Get the current console user, if not root, check the plists and delete the conflicting
    # keys if they exist
    current_user = subprocess.check_output(['stat', '-f', '"%Su"', '/dev/console']).rstrip().strip('"')
    if current_user != "root":
        disabled_hidden = subprocess.check_output(["sudo", "-u", current_user, "/usr/bin/defaults", "read",
                                                   "com.apple.systempreferences"])
        if "DisabledPreferencePanes" in disabled_hidden:
            subprocess.call(["sudo", "-u", current_user, "/usr/bin/defaults", "delete",
                             "com.apple.systempreferences", "DisabledPreferencePanes"])
        if "HiddenPreferencePanes" in disabled_hidden:
            subprocess.call(["sudo", "-u", current_user, "/usr/bin/defaults", "delete",
                             "com.apple.systempreferences", "HiddenPreferencePanes"])


# Modify locked preferences and sync
def modify_panes(value):
    CoreFoundation.CFPreferencesSetValue("DisabledPreferencePanes", value, "com.apple.systempreferences",
                                         "kCFPreferencesAnyUser", "kCFPreferencesCurrentHost")
    CoreFoundation.CFPreferencesSetValue("HiddenPreferencePanes", value, "com.apple.systempreferences",
                                         "kCFPreferencesAnyUser", "kCFPreferencesCurrentHost")
    CoreFoundation.CFPreferencesSynchronize("com.apple.systempreferences",
                                            "kCFPreferencesAnyUser", "kCFPreferencesCurrentHost")

# Lock a comma separated list of preference panes
def lock_unlock_panes():

    # Check that bundle identifier argument was supplied
    if len(sys.argv) != 3:
        print("""Syntax:
    ./PrefPaneUtil.py --lock "com.apple.preference.spotlight, com.apple.prefs.backup"
    ./PrefPaneUtil.py --unlock "com.apple.preference.spotlight, com.apple.prefs.backup"
        """)
        sys.exit(1)

    # Get the panes to be locked or unlocked, stripping the whitespace
    panes_to_modify = [pane.strip() for pane in sys.argv[2].split(',')]

    # Verify that bundle identifiers provided are valid
    all_panes = system_panes.copy()
    all_panes.update(other_panes)
    valid_id = {}
    for pane in panes_to_modify:
        valid_id[pane] = False
        if pane in all_panes.values():
            valid_id[pane] = True
    for key, value in valid_id.iteritems():
        if not value:
            print(key + " is not a valid bundle identifier, removing")
            panes_to_modify.remove(key)

     # Create a mutable copy of the currently locked panes
    new_locked_panes = NSMutableArray.alloc().initWithArray_(locked_panes)

    # Add panes to list of locked panes
    if sys.argv[1] == "--lock":
        # If none are currently locked, proceed to lock the requested panes
        if locked_panes == None:
            # Set the value in the plist
            modify_panes(panes_to_modify)
        # If there are locked panes, determine if the pane is already locked
        else:
            for to_lock in panes_to_modify:
                exist = {to_lock: False}
                # Ensure that the bundle identifier is valid

                for current_lock in new_locked_panes:
                    if current_lock == to_lock:
                        print(to_lock + " is already locked, skipping.")
                        exist[to_lock] = True
                        break
                # If the pane did not already exist, add it.
                if not exist[to_lock]:
                    new_locked_panes.append(to_lock)
                    print(to_lock + " is current unlocked, locking.")
            modify_panes(new_locked_panes)

    # Remove panes from list of locked panes
    elif sys.argv[1] == "--unlock":
        # If no Panes locked, exit
        if locked_panes == None:
            print("No panes are currently locked, exiting!")
            sys.exit(1)

        # Unlock the requested panes
        else:
            for to_unlock in panes_to_modify:
                exist = {to_unlock: False}
                for current_lock in new_locked_panes:
                    if current_lock == to_unlock:
                        print(to_unlock + " is currently locked, unlocking.")
                        exist[to_unlock] = True
                        break
                if exist[to_unlock]:
                    new_locked_panes.remove(to_unlock)
            modify_panes(new_locked_panes)

# Unlock all panes, create the file /tmp/prefpanes.restore for use with the restore_all function
def unlock_all():
    if locked_panes == None:
        print("No panes are currently locked, exiting!")
        sys.exit(1)

    # Create the restore file based on the currently locked panes
    if os.path.isfile('/tmp/prefpanes.restore'):
        os.remove('/tmp/prefpanes.restore')
    restore_file = open('/tmp/prefpanes.restore', 'a')
    for pane in locked_panes:
       restore_file.write(pane + "\n")

    # Unlock all panes
    modify_panes(None)

    # Notify
    print("All preference panes unlocked! Restore file is saved at '/tmp/prefpanes.restore'. Use --restore to "
          "restore all previous locks.")

# Restore panes saved in /tmp/prefpanes.restore
def restore_all():
    # Try to open the restore file, notify if it doesn't exist
    try:
        restore_file = open('/tmp/prefpanes.restore', 'r')
    except IOError:
        print("/tmp/prefpanes.restore doesn't exist, sorry!")
        sys.exit(1)

    # Create an array of all values to restore
    restore_locks = []
    for line in restore_file:
         restore_locks.append(line.rstrip())

    # Restore the locks
    modify_panes(restore_locks)

    # Remove the restore file
    os.remove('/tmp/prefpanes.restore')

    # Notify
    print("Preference pane locks restored from '/tmp/prefpanes.restore'. Restore file has been deleted.")

# Process arguments and execute necessary functions
if __name__ == '__main__':

    user = os.getuid()
    if user != 0:
        print("You must run this tool with sudo or as root!")
        sys.exit(1)

    elif len(sys.argv) ==  1:
        print_help()
        sys.exit(0)

    elif sys.argv[1] == "--list":
        get_bundle_identifiers()
        list_bundle_identifiers()

    elif sys.argv[1] == "--locked":
        list_current_locked()

    elif sys.argv[1] == "--unlock" or sys.argv[1] == "--lock":
        get_bundle_identifiers()
        sanity_check()
        lock_unlock_panes()

    elif sys.argv[1] == "--restore":
        sanity_check()
        restore_all()

    elif sys.argv[1] == "--unlockall":
        sanity_check()
        unlock_all()

    else:
        print_help()