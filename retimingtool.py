import traceback
import maya.OpenMaya as om

from PySide2 import QtCore
from PySide2.QtCore import Qt
from PySide2 import QtWidgets
from PySide2.QtWidgets import *
from shiboken2 import wrapInstance

import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMayaUI as omui


class RetimingUtils(object):

    @classmethod
    def retime_keys(cls, retime_value, incremental, move_to_next, move_to_start):
        range_start_time, range_end_time = cls.get_selected_range()
        start_keyframe_time = cls.get_start_keyframe_time(range_start_time)
        last_keyframe_time = cls.get_last_keyframe_time()
        current_time = start_keyframe_time

        new_keyframe_times = [start_keyframe_time]

        while current_time != last_keyframe_time:
            next_keyframe_time = cls.find_keyframe("next", current_time)

            if incremental:
                time_diff = next_keyframe_time - current_time
                if current_time < range_end_time:
                    time_diff += retime_value
                    if time_diff < 1:
                        time_diff = 1
            else:
                if current_time < range_end_time:
                    time_diff = retime_value
                else:
                    time_diff = next_keyframe_time - current_time

            new_keyframe_times.append(new_keyframe_times[-1] + time_diff)
            current_time = next_keyframe_time

        if len(new_keyframe_times) > 1:
            cls.retime_keys_recursive(start_keyframe_time, 0, new_keyframe_times)

        first_keyframe_time = cls.find_keyframe("first")

        if move_to_next and range_start_time >= first_keyframe_time:
            next_keyframe_time = cls.find_keyframe("next", start_keyframe_time)
            cls.set_current_time(next_keyframe_time)
        elif range_end_time > first_keyframe_time:
            cls.set_current_time(start_keyframe_time)
        else:
            cls.set_current_time(range_start_time)

        if move_to_start and range_start_time >= first_keyframe_time:
            first_keyframe_time = cls.find_keyframe("first", start_keyframe_time)
            cls.set_current_time(first_keyframe_time)

    @classmethod
    def retime_keys_recursive(cls, current_time, index, new_keyframe_times):
        if index >= len(new_keyframe_times):
            return

        updated_keyframe_time = new_keyframe_times[index]
        next_keyframe_time = cls.find_keyframe("next", current_time)

        if updated_keyframe_time < next_keyframe_time:
            cls.change_keyframe_time(current_time, updated_keyframe_time)
            cls.retime_keys_recursive(next_keyframe_time, index + 1, new_keyframe_times)
        else:
            cls.retime_keys_recursive(next_keyframe_time, index + 1, new_keyframe_times)
            cls.change_keyframe_time(current_time, updated_keyframe_time)

    @classmethod
    def set_current_time(cls, time):
        cmds.currentTime(time)

    @classmethod
    def get_selected_range(cls):
        playback_slider = mel.eval("$tempVar = $gPlayBackSlider")
        selected_range = cmds.timeControl(playback_slider, q=True, rangeArray=True)

        return selected_range

    @classmethod
    def find_keyframe(cls, which, time=None):
        kwargs = {"which": which}
        if which in ["next", "previous"]:
            kwargs["time"] = (time, time)

        return cmds.findKeyframe(**kwargs)

    @classmethod
    def change_keyframe_time(cls, current_time, new_time):
        cmds.keyframe(e=True, time=(current_time, current_time), timeChange=new_time)

    @classmethod
    def get_start_keyframe_time(cls, range_start_time):
        start_times = cmds.keyframe(q=True, time=(range_start_time, range_start_time))
        if start_times:
            return start_times[0]

        start_time = cls.find_keyframe("previous", range_start_time)
        return start_time

    @classmethod
    def get_first_keyframe_time(cls):
        return cls.find_keyframe("first")

    @classmethod
    def get_last_keyframe_time(cls):
        return cls.find_keyframe("last")


class RetimingUi(QtWidgets.QDialog):

    WINDOW_TITLE = "Retiming Tool"

    ABSOLUTE_BUTTON_WIDTH = 50
    RELATIVE_BUTTON_WIDTH = 64

    RETIMING_PROPERTY_NAME = "retiming_data"

    dlg_instance = None


    @classmethod
    def display(cls):
        if not cls.dlg_instance:
            cls.dlg_instance = RetimingUi()

        if cls.dlg_instance.isHidden():
            cls.dlg_instance.show()
        else:
            cls.dlg_instance.raise_()
            cls.dlg_instance.activateWindow()

    @classmethod
    def maya_main_window(cls):
        main_window_ptr = omui.MQtUtil.mainWindow()
        return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)

    def __init__(self):
        super(RetimingUi, self).__init__(self.maya_main_window())

        self.setWindowTitle("Retiming Tool")
        if cmds.about(ntOS=True):
            self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        elif cmds.about(macOS=True):
            self.setWindowFlags(QtCore.Qt.Tool)

        self.create_widgets()
        self.create_layouts()
        self.create_connections()

    def create_widgets(self):
        self.title_lbl = QtWidgets.QLabel("Retiming Tool")
        self.title_lbl.setStyleSheet("font: bold 50px")
        self.absolute_buttons = []
        for i in range(1, 11):
            btn = QtWidgets.QPushButton("{0}f".format(i))
            btn.setFixedWidth(self.ABSOLUTE_BUTTON_WIDTH)
            btn.setProperty(self.RETIMING_PROPERTY_NAME, [i, False])
            self.absolute_buttons.append(btn)
        self.relative_buttons = []
        for i in [-2, -1, 1, 2]:
            btn = QtWidgets.QPushButton("{0}f".format(i))
            btn.setFixedWidth(self.RELATIVE_BUTTON_WIDTH)
            btn.setProperty(self.RETIMING_PROPERTY_NAME, [i, True])
            self.relative_buttons.append(btn)
        self.move_to_next_cb = QtWidgets.QCheckBox("Move to Next Frame")
        self.move_to_start_cb = QtWidgets.QCheckBox("Move to Start")
        self.ripple_delete_btn = QtWidgets.QPushButton("Ripple Delete")
        self.cleanup_keys_btn = QtWidgets.QPushButton("Clean-Up Keys")

    def create_layouts(self):
        absolute_retime_layout = QtWidgets.QHBoxLayout()
        absolute_retime_layout.setSpacing(2)
        for btn in self.absolute_buttons:
            absolute_retime_layout.addWidget(btn)

        relative_retime_layout = QtWidgets.QHBoxLayout()
        relative_retime_layout.setSpacing(2)
        for btn in self.relative_buttons:
            relative_retime_layout.addWidget(btn)
            if relative_retime_layout.count() == 2:
                relative_retime_layout.addStretch()

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)
        main_layout.addLayout(absolute_retime_layout)
        main_layout.addLayout(relative_retime_layout)
        main_layout.addWidget(self.move_to_next_cb)
        main_layout.addWidget(self.move_to_start_cb)
        main_layout.addWidget(self.ripple_delete_btn)
        main_layout.addWidget(self.cleanup_keys_btn)


    def create_connections(self):
        for btn in self.absolute_buttons:
            btn.clicked.connect(self.retime)

        for btn in self.relative_buttons:
            btn.clicked.connect(self.retime)

        self.ripple_delete_btn.clicked.connect(self.ripple_delete)
        self.cleanup_keys_btn.clicked.connect(self.cleanup_keys)

    def retime(self):
        btn = self.sender()
        if btn:
            retiming_data = btn.property(self.RETIMING_PROPERTY_NAME)
            move_to_next = self.move_to_next_cb.isChecked()
            move_to_start = self.move_to_start_cb.isChecked()

            cmds.undoInfo(openChunk=True)
            try:
                RetimingUtils.retime_keys(retiming_data[0], retiming_data[1], move_to_next, move_to_start)
            except:
                traceback.print_exc()
                om.MGlobal.displayError("Retime error occurred. See script for details.")

            cmds.undoInfo(closeChunk=True)

    def ripple_delete(self):
        start_time, end_time = RetimingUtils.get_selected_range()
        cmds.cutKey(self, time=(start_time, end_time), clear=True)

    def cleanup_keys(self):
        start_time, end_time = RetimingUtils.get_selected_range()
        cmds.snapKey(self, time=(start_time, end_time))
