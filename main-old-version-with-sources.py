#!/usr/bin/python3
import sys
import datetime
import numpy as np
import pyqtgraph as pg
from PyQt6 import QtWidgets, uic, QtCore
from pyqtgraph.Qt import QtCore, QtGui
from PyQt6.QtCore import Qt
import pyqtgraph.opengl as gl
from logo import points
import matplotlib as mpl
from matplotlib.ticker import EngFormatter
from menumanager import MenuManager
from datasources.rtlsdr_fft import RtlSdrDataSource
from datasources.hackrf_fft import HackRFDataSource
from datasources.hackrf_sweep import HackRFSweepDataSourceOld
from datasources.rtlsdr_sweep import RtlSweepDataSource
from datasources.audio_fft import AudioDataSource
from datasources import SampleDataSource, SweepDataSource
import SignalProcessing
from PyQt6.QtWidgets import QStackedWidget
import threedimension
import twodimension

from typing import Union
from dataentry import Keypad

class MainWindow(QtWidgets.QMainWindow):
    CENTRE_FREQUENCY = 98e6 #
    #CENTRE_FREQUENCY = 1545e6
    #CENTRE_FREQUENCY = 2412e6

    GAIN = 36.4
    AMPLIFIER = True
    LNA_GAIN = 10
    VGA_GAIN = 10
    sweep_data = None
    INITIAL_SAMPLE_SIZE = 2048
    INITIAL_NUMBER_OF_LINES = 20
    dsp = SignalProcessing.process()
    # data_source: DataSourceDataSource | SweepDataSource = None    # Only newer python
    data_source: Union[SampleDataSource, SweepDataSource] = None

    inputValue: QtWidgets.QLabel

    dataButtons: list[QtWidgets.QPushButton] = []
    buttonDot: QtWidgets.QPushButton
    buttonGhz: QtWidgets.QPushButton
    buttonMhz: QtWidgets.QPushButton
    buttonKhz: QtWidgets.QPushButton
    buttonHz: QtWidgets.QPushButton
    buttonMinus: QtWidgets.QPushButton
     
    dataInput: str = ""

    def __init__(self):
        super().__init__()

        self.is_vertical = False
        uic.loadUi("mainwindowhorizontal.ui", self)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.stacked_widget = QStackedWidget(self)

        # Create and configure 2D PlotWidget
        self.two_d_widget = twodimension.TwoD()

        # Create and configure 3D GLViewWidget
        self.three_d_widget = threedimension.ThreeD(
            self.INITIAL_SAMPLE_SIZE, self.INITIAL_NUMBER_OF_LINES
        )

        # Create waterfall widget
        #self.waterfall_widget = waterfall.Waterfall()

        self.stacked_widget.addWidget(self.two_d_widget.widget)
        self.stacked_widget.addWidget(self.three_d_widget.widget)
        #self.stacked_widget.addWidget(self.waterfall_widget)
        
        layout = self.findChild(QtWidgets.QWidget, "graphical_display")
        layout.layout().addWidget(self.stacked_widget)
        self.current_display = "plot"
        self.stacked_widget.setCurrentIndex(0)  # Show 2D plot initially
        self.display_logo()

        # tried to get mouse over value but failed
        self.cursor_text = pg.TextItem('', anchor=(0, 0))
        self.two_d_widget.widget.addItem(self.cursor_text)
        self.two_d_widget.widget.plotItem.scene().sigMouseMoved.connect(self.mouse_move_event)
        self.menu_manager = MenuManager(option_callback=self.option_selected)
        self.engformat = mpl.ticker.EngFormatter(places=3)
        self.timer = QtCore.QTimer()
        self.peak_frequency1 = "Peak On"
        self.peak_power = None
        self.is_peak_on = False
        self.power_db = None
        self.data_source = None
        self.timer.timeout.connect(self.update_plot)
        self.is_paused = False
        self.bias_t = False
        self.max_hold = False
        self.max_hold_buffer = None
        self.rtl_initialised = False


        self.initialise_buttons()
        self.status_label.setText("Select data source")
        self.set_button_focus_policy(self)  # Avoids buttons being active after pressing
        self.initialise_labels()
        self.update_button_labels()
        self.connect_buttons()


        self.soft_buttons = [
            self.buttonsoft1,
            self.buttonsoft2,
            self.buttonsoft3,
            self.buttonsoft4,
            self.buttonsoft5,
            self.buttonsoft6,
            self.buttonsoft7,
            self.buttonsoft8,
        ]

    def option_selected(self, parent_menu, current_menu, option):
        if parent_menu == "Input":
            if option == "RTL FFT":
                self.use_rtl_source()  
                self.menu_manager.select_submenu("RTL FFT")
                self.menu_manager.update_button_labels()  

        if parent_menu == "Input":
            if option == "HackRF FFT":
                self.use_hackrf_source() 
                self.menu_manager.select_submenu("HackRF FFT")  
                self.menu_manager.update_button_labels()

        if parent_menu == "Input":
            if option == "HackRF Sweep":
                self.use_hackrf_sweep_source() 
                self.menu_manager.select_submenu("HackRF Sweep")  
                self.menu_manager.update_button_labels()

        if parent_menu == "Input":
            if option == "Audio FFT":
                self.use_audio_source() 
                self.menu_manager.select_submenu("Audio FFT")  
                self.menu_manager.update_button_labels()  

    def load_new_ui(self, ui_file):
        layout = self.findChild(QtWidgets.QWidget, "graphical_display").layout()
        if layout:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        uic.loadUi(ui_file, self)
        self.stacked_widget = QStackedWidget(self)
        self.two_d_widget = twodimension.TwoD()
        self.three_d_widget = threedimension.ThreeD(
            self.INITIAL_SAMPLE_SIZE, self.INITIAL_NUMBER_OF_LINES
        )
        self.stacked_widget.addWidget(self.two_d_widget.widget)
        self.stacked_widget.addWidget(self.three_d_widget.widget)
        new_layout = self.findChild(QtWidgets.QWidget, "graphical_display")
        new_layout.layout().addWidget(self.stacked_widget)

        self.current_display = "plot"
        self.stacked_widget.setCurrentIndex(0)  # Show 2D plot initially
        self.display_logo()

        self.initialise_buttons()
        self.connect_buttons()
        self.initialise_labels()
        self.update_button_labels()

    def initialise_buttons(self):
        button_names = [
            "buttonsoft1",
            "buttonsoft2",
            "buttonsoft3",
            "buttonsoft4",
            "buttonsoft5",
            "buttonsoft6",
            "buttonsoft7",
            "buttonsoft8",
            "button_hold",
            "button2d3d",
            "button_span",
            "button_frequency",
            "button_amplitude",
            "button_peak",
            "button_preset",
            "button_mode",
            "button_rtl_fft",
            "button_hackrf_fft",
            "button_rtl_sweep",
            "button_hackrf_sweep",
            "button_audio_fft",
            "button_input",
            "button_export"
        ]
        self.buttons = {
            name: self.findChild(QtWidgets.QPushButton, name) for name in button_names
        }
        self.soft_buttons = [self.buttonsoft1, self.buttonsoft2, self.buttonsoft3,
                             self.buttonsoft4, self.buttonsoft5, self.buttonsoft6,
                             self.buttonsoft7, self.buttonsoft8]

        self.dataButtons = [self.findChild(QtWidgets.QPushButton, f"buttondata{i}") for i in range(0,10)]
        self.buttonMhz = self.findChild(QtWidgets.QPushButton, "buttonmhz")
        self.buttonDot = self.findChild(QtWidgets.QPushButton, "buttondot")
        self.buttonGhz = self.findChild(QtWidgets.QPushButton, "buttonghz")
        self.buttonKhz = self.findChild(QtWidgets.QPushButton, "buttonkhz")
        self.buttonHz = self.findChild(QtWidgets.QPushButton, "buttonhz")
        self.buttonMinus = self.findChild(QtWidgets.QPushButton, "buttonminus")

        pass


    def connect_buttons(self):
        self.button_frequency.pressed.connect(lambda: self.handle_menu_button("Frequency"))
        self.button_span.pressed.connect(lambda: self.handle_menu_button("Span"))
        self.button_amplitude.pressed.connect(lambda: self.handle_menu_button("Amplitude"))
        self.button_input.pressed.connect(lambda: self.handle_menu_button("Input"))
        self.buttonsoft1.pressed.connect(lambda: self.handle_soft_button(0))
        self.buttonsoft2.pressed.connect(lambda: self.handle_soft_button(1))
        self.buttonsoft3.pressed.connect(lambda: self.handle_soft_button(2))
        self.buttonsoft4.pressed.connect(lambda: self.handle_soft_button(3))
        self.buttonsoft5.pressed.connect(lambda: self.handle_soft_button(4))
        self.buttonsoft6.pressed.connect(lambda: self.handle_soft_button(5))
        self.buttonsoft7.pressed.connect(lambda: self.handle_soft_button(6))
        self.buttonsoft8.pressed.connect(lambda: self.handle_soft_button(7))
        self.button_mode.pressed.connect(lambda: self.handle_menu_button("Mode"))
        self.button_preset.pressed.connect(lambda: self.preset())
        self.buttonmaxhold.pressed.connect(lambda: self.toggle_max_hold())
        self.button_hold.pressed.connect(lambda: self.toggle_hold())
        self.button_peak.pressed.connect(lambda: self.toggle_peak())
        self.button2d3d.pressed.connect(lambda: self.toggle_display())
        self.buttonverthoriz.pressed.connect(lambda: self.toggle_orientation())
        self.button_export.pressed.connect(lambda: self.export_image())
        self.button_waterfall.pressed.connect(lambda: self.start_waterfall())

        for i, button in enumerate(self.dataButtons):
            button.pressed.connect(self.handle_data_character(i))

        self.buttonMinus.pressed.connect(self.handle_data_character("-"))
        self.buttonDot.pressed.connect(self.handle_data_character("."))

        self.buttonGhz.pressed.connect(self.set_centre(1e9))
        self.buttonMhz.pressed.connect(self.set_centre(1e6))
        self.buttonKhz.pressed.connect(self.set_centre(1e3))
        self.buttonHz.pressed.connect(self.set_centre(1))

    def set_centre(self, multiplier):
        def set_centre_inner():
            self.CENTRE_FREQUENCY = int(float(self.dataInput) * multiplier)
            self.engformat(self.CENTRE_FREQUENCY) + "Hz"
            self.inputValue.setText("")
            self.dataInput = ""

            if isinstance(self.data_source, SampleDataSource):
                self.data_source.set_centre_freq(self.CENTRE_FREQUENCY)
                print(f"Centre frequency set to " + self.engformat(self.CENTRE_FREQUENCY) + "Hz")

        return set_centre_inner

 
    def initialise_labels(self):
        self.output_centre_freq = self.findChild(QtWidgets.QLabel, "output_centre_freq")
        self.output_sample_rate = self.findChild(QtWidgets.QLabel, "output_sample_rate")
        self.output_span = self.findChild(QtWidgets.QLabel, "output_span")
        self.output_start_freq = self.findChild(QtWidgets.QLabel, "output_start_freq")
        self.output_stop_freq = self.findChild(QtWidgets.QLabel, "output_stop_freq")
        self.output_gain = self.findChild(QtWidgets.QLabel, "output_gain")
        self.output_gain = self.findChild(QtWidgets.QLabel, "output_gain")
        self.output_res_bw = self.findChild(QtWidgets.QLabel, "output_res_bw")
        self.inputValue = self.findChild(QtWidgets.QLabel, "input_value")

    def set_button_focus_policy(self, parent):
        for widget in parent.findChildren(QtWidgets.QPushButton):
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def handle_data_character(self, button_index: str | int):
        def handle_button_inner():
            if button_index == "-":
                if len(self.dataInput) > 0:
                    self.dataInput = self.dataInput[:-1]
                    self.inputValue.setText(self.dataInput)
                    return
            
            if button_index == ".":
                if "." in self.dataInput:
                    return
                if len(self.dataInput) == 0:
                    self.dataInput += "0."
                else:
                    self.dataInput += "."
                self.inputValue.setText(self.dataInput)
                return

            self.dataInput += str(button_index)
            self.inputValue.setText(self.dataInput)

        return handle_button_inner

    def keyPressEvent(self, event):
        modifiers = event.modifiers()
        key_actions = {
            Qt.Key.Key_F1: lambda: self.handle_soft_button(0),
            Qt.Key.Key_F2: lambda: self.handle_soft_button(1),
            Qt.Key.Key_F3: lambda: self.handle_soft_button(2),
            Qt.Key.Key_F4: lambda: self.handle_soft_button(3),
            Qt.Key.Key_F5: lambda: self.handle_soft_button(4),
            Qt.Key.Key_F6: lambda: self.handle_soft_button(5),
            Qt.Key.Key_F7: lambda: self.handle_soft_button(6),
            Qt.Key.Key_F8: lambda: self.handle_soft_button(7),
            Qt.Key.Key_F: lambda: self.handle_menu_button("Frequency"),
            Qt.Key.Key_S: lambda: self.handle_menu_button("Span"),
            Qt.Key.Key_A: lambda: self.handle_menu_button("Amplitude"),
            Qt.Key.Key_I: lambda: self.handle_menu_button("Input"),
            Qt.Key.Key_Space: self.toggle_hold,
            Qt.Key.Key_P: self.toggle_peak,
            Qt.Key.Key_O: self.toggle_orientation,
            Qt.Key.Key_X: self.toggle_max_hold,
            Qt.Key.Key_M: lambda: self.print_something("fdsasdff1"),
            Qt.Key.Key_B: lambda: self.toggle_bias_t(),   
            Qt.Key.Key_R: lambda: self.preset(),   
            Qt.Key.Key_0: self.handle_data_character(0),
            Qt.Key.Key_1: self.handle_data_character(1),
            Qt.Key.Key_2: self.handle_data_character(2),
            Qt.Key.Key_3: self.handle_data_character(3),
            Qt.Key.Key_4: self.handle_data_character(4),
            Qt.Key.Key_5: self.handle_data_character(5),
            Qt.Key.Key_6: self.handle_data_character(6),
            Qt.Key.Key_7: self.handle_data_character(7),
            Qt.Key.Key_8: self.handle_data_character(8),
            Qt.Key.Key_9: self.handle_data_character(9),
            Qt.Key.Key_Minus: self.handle_data_character("-"),
            Qt.Key.Key_Period: self.handle_data_character("."),
            Qt.Key.Key_Backspace: self.handle_data_character("-"),
            Qt.Key.Key_H: self.set_centre(1),
            Qt.Key.Key_K: self.set_centre(1e3),
            Qt.Key.Key_M: self.set_centre(1e6),
            Qt.Key.Key_G: self.set_centre(1e9),
            

        }
        action = key_actions.get(event.key())
        if action:
            action()
            event.accept()

    def export_image(self):
        now = datetime.datetime.now()
        filename = now.strftime("%Y-%m-%d_%H-%M-%S") + ".png"
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        filename_prefix="tdn_"
        filename = filename_prefix + timestamp + ".jpg"
        pixmap = self.two_d_widget.grab()
        pixmap.save(filename, 'jpg')
        print(f"Plot saved as {filename}")

    def toggle_bias_t(self):
        if self.data_source is not None:
            current_state = self.data_source.bias_tee
            self.data_source.set_bias_tee(not current_state)  # Toggle state
            print(f"Bias tee is {'enabled' if self.data_source.bias_tee else 'disabled'}.")
            self.status_label.setText(f"Bias tee is {'enabled' if self.data_source.bias_tee else 'disabled'}")

    def print_something(self, something):
        print (something)

    def setup_layout(self):
        layout = self.findChild(QtWidgets.QWidget, "graphical_display").layout()
        if layout is None:
            layout = QtWidgets.QVBoxLayout(
                self.findChild(QtWidgets.QWidget, "graphical_display")
            )
        else:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

    def toggle_display(self):
        if self.current_display == "plot":
            self.stacked_widget.setCurrentIndex(1)  # Show 3D display
            self.current_display = "gldisplay"
            self.three_d_widget.start_animation()

        else:
            self.stacked_widget.setCurrentIndex(0)  # Show 2D plot
            self.three_d_widget.stop_animation()
            self.current_display = "plot"
            self.timer.timeout.connect(self.update_plot)
    
    def start_waterfall(self):
        pass

    def display_logo(self):
        x_vals, y_vals = zip(*points)
        self.two_d_widget.widget.plot(
            x_vals, y_vals, pen=None, symbol="t", symbolBrush="b"
        )
        print("display logo")

    def update_plot(self):
        if self.data_source and not self.is_paused:
            if isinstance(self.data_source, SampleDataSource):
                try:
                    self.update_output_fields()
                    samples = self.data_source.read_samples(self.INITIAL_SAMPLE_SIZE)
                    if samples is not None and len(samples) > 0:
                        self.process_samples(samples)

                except Exception as e:
                    print(f"Error reading samples: {e}")

            elif isinstance(self.data_source, SweepDataSource):
                self.plot_sweep_data()

    def update_output_fields(self):
        if isinstance(self.data_source, AudioDataSource):
            self.output_centre_freq.setText("N/A")
        else:
            self.output_centre_freq.setText(self.engformat(self.data_source.centre_freq) + "Hz")

        self.output_sample_rate.setText(f"{int(self.data_source.sample_rate):,} SPS")
        self.update_frequency_outputs()

        self.output_gain.setText(str(self.data_source.gain) + " dB")
        self.output_res_bw.setText(self.engformat(self.data_source.sample_rate / self.INITIAL_SAMPLE_SIZE) + "Hz")
        self.output_sample_size.setText(str(self.INITIAL_SAMPLE_SIZE))

    def update_frequency_outputs(self):
        if isinstance(self.data_source, AudioDataSource):
            self.output_start_freq.setText("0 Hz")
        else:
            self.output_start_freq.setText(
                self.engformat(self.data_source.centre_freq - self.data_source.sample_rate / 2) + "Hz"
            )

        self.output_stop_freq.setText(
            self.engformat(self.data_source.centre_freq + self.data_source.sample_rate / 2) + "Hz"
        )

        if isinstance(self.data_source, AudioDataSource):
            self.output_span.setText(self.engformat(self.data_source.sample_rate / 2) + "Hz")
        else:
            self.output_span.setText(self.engformat(self.data_source.sample_rate) + "Hz")

    def process_samples(self, samples):
        fft = self.dsp.do_fft(samples)
        self.frequency_bins, half_length = self.calculate_frequency_bins(fft)

        if self.max_hold:
            self.update_max_hold_buffer()

        self.clear_and_plot(self.frequency_bins)

        if self.is_peak_on:
            self.plot_peak_info(self.frequency_bins)

        self.three_d_widget.z = self.power_db / 10

    def calculate_frequency_bins(self, fft):
        if isinstance(self.data_source, AudioDataSource):
            centrefft = fft[:int(self.INITIAL_SAMPLE_SIZE // 2)]
            magnitude = self.dsp.get_magnitude(centrefft)
            self.power_db = self.dsp.get_log_magnitude(magnitude)
            frequency_bins = np.linspace(0, self.data_source.sample_rate, len(self.power_db))
            half_length = len(frequency_bins) // 2
            frequency_bins = frequency_bins[:half_length]
            self.power_db = self.power_db[:half_length]
        else:
            centrefft = self.dsp.do_centre_fft(fft)
            magnitude = self.dsp.get_magnitude(centrefft)
            self.power_db = self.dsp.get_log_magnitude(magnitude)
            frequency_bins = np.linspace(0, self.data_source.sample_rate, len(self.power_db))
            frequency_bins += (self.CENTRE_FREQUENCY - self.data_source.sample_rate / 2)

        return frequency_bins, len(frequency_bins) // 2

    def update_max_hold_buffer(self):
        if self.max_hold_buffer is None:
            self.max_hold_buffer = self.power_db.copy()
        else:
            self.max_hold_buffer = np.maximum(self.max_hold_buffer, self.power_db)

    def clear_and_plot(self, frequency_bins):
        if self.current_display == "plot":
            self.two_d_widget.widget.clear()

        if self.max_hold and self.max_hold_buffer is not None:
            self.two_d_widget.widget.plot(frequency_bins / 1e6, self.max_hold_buffer, pen="y")

        self.two_d_widget.widget.plot(frequency_bins / 1e6, self.power_db, pen="g")

    def plot_peak_info(self, frequency_bins):
        if self.power_db is not None and len(self.power_db) > 0:
            index_of_peak = np.argmax(self.power_db)
            peak_value = self.power_db[index_of_peak]
            peak_frequency = frequency_bins[index_of_peak] / 1e6
            
            self.add_peak_text(peak_frequency, peak_value)

            if self.max_hold:
                self.add_max_peak_info(frequency_bins, index_of_peak)

    def add_peak_text(self, peak_frequency, peak_value):
        text = (
            f"<span style='color: green;background-color: black;'>Live peak</span> <br>"
            f"<span style='color: white;background-color: black;'>{peak_frequency:.2f} MHz</span> <br>"
            f"<span style='color: white;background-color: black;'>{peak_value:.2f} dB</span>"
        )
        self.peak_frequency1 = pg.TextItem(text)
        self.peak_frequency1.setHtml(text)
        y_min, y_max = self.two_d_widget.widget.viewRange()[1]
        self.peak_frequency1.setPos(peak_frequency, y_min + 0.9 * (y_max - y_min))
        self.two_d_widget.widget.addItem(self.peak_frequency1)

    def add_max_peak_info(self, frequency_bins, index_of_max_peak):
        max_peak_value = self.max_hold_buffer[index_of_max_peak]
        max_peak_frequency = frequency_bins[index_of_max_peak] / 1e6

        thresholds = [max_peak_value - db_drop for db_drop in [3, 6, 9]]
        bandwidths = [self.find_bandwidth_points(thresholds[i], index_of_max_peak) for i in range(3)]

        max_peak_text = (
            f"<span style='color: yellow;background-color: black;'>Max peak</span> <br>"
            f"<span style='color: white;background-color: black;'>{max_peak_frequency:.2f} MHz</span><br>"
            f"<span style='color: white; background-color: black;'>{max_peak_value:.2f} dB</span><br>"
        )
        self.max_frequency1 = pg.TextItem(max_peak_text)
        self.max_frequency1.setHtml(max_peak_text)
        self.max_frequency1.setPos(max_peak_frequency, self.two_d_widget.widget.viewRange()[1][1])
        self.two_d_widget.widget.addItem(self.max_frequency1)

    def find_bandwidth_points(self, threshold, index_of_max_peak):
        lower_index = index_of_max_peak
        while lower_index > 0 and self.max_hold_buffer[lower_index] > threshold:
            lower_index -= 1

        upper_index = index_of_max_peak
        while upper_index < len(self.max_hold_buffer) - 1 and self.max_hold_buffer[upper_index] > threshold:
            upper_index += 1

        return (self.frequency_bins[lower_index] / 1e6, self.frequency_bins[upper_index] / 1e6)

    def plot_sweep_data(self):
        if self.sweep_data is not None:
            self.two_d_widget.plot(self.sweep_data["x"], self.sweep_data["y"], pen="g")
            index_of_peak = np.argmax(self.sweep_data["y"])
            peak_y_value = self.sweep_data["y"][index_of_peak]
            corresponding_x_value = self.sweep_data["x"][index_of_peak]
            text_item = pg.TextItem(
                str(self.engformat(corresponding_x_value)) + "Hz\n" + str(self.engformat(peak_y_value) + " dB")
            )
            text_item.setPos(corresponding_x_value / 1e6, peak_y_value)


    def update_button_labels_for_menu(self, menu_name):
        # Select the menu first to ensure the stack is correct
        self.menu_manager.select_menu(menu_name)
        
        # Get button labels from MenuManager
        labels = self.menu_manager.get_button_labels()
        buttons = self.soft_buttons  # Use the list of all soft buttons

        for i, button in enumerate(buttons):
            if i < len(labels):
                button.setText(labels[i])
            else:
                button.setText("")  # Clear any remaining buttons if needed



    
    def update_soft_button_labels(self):
        button_labels = self.menu_manager.get_button_labels()
        # Assuming you have a list or some UI elements to represent the soft buttons
        for i, label in enumerate(button_labels):
            if i < len(self.soft_buttons):
                self.soft_buttons[i].setText(label)  # Update the UI element for the button
            else:
                break  # Prevents index out of range if there are more buttons than labels


    def handle_soft_button(self, button_index):
        self.menu_manager.handle_button_press(button_index)
        self.update_button_labels()




    def handle_menu_button(self, menu_name):
        self.menu_manager.select_menu(menu_name)  # Ensure the menu is selected first
        print(f"Current menu level: {menu_name}")

        # Update status label based on selected menu
        if menu_name.lower() == "frequency":
            self.status_label.setText("Centre Frequency")
        elif menu_name.lower() == "span":
            self.status_label.setText("Span:")
        elif menu_name.lower() == "amplitude":
            self.status_label.setText("Amplitude:")
        elif menu_name.lower() == "input":
            self.status_label.setText("Input")

        # Update button labels for the selected menu
        self.update_button_labels()

    def show_submenu(self, submenu_name):
        self.menu_manager.select_submenu(submenu_name)  # Navigate to the submenu
        self.update_button_labels()  # Update button labels after changing submenu

    def update_button_labels(self):
        labels = self.menu_manager.get_button_labels()  # Get current button labels
        buttons = self.soft_buttons  # List of all soft buttons

        # Update buttons based on the available labels
        for i, button in enumerate(buttons):
            if i < len(labels):
                button.setText(labels[i])
            else:
                button.setText("")  # Clear excess buttons


    def toggle_peak(self):
        self.is_peak_on = not self.is_peak_on
        if self.is_peak_on:
            print("Peak on")
        else:
            print("Peak off")
            if hasattr(self, "peak_frequency1"):
                self.two_d_widget.widget.removeItem(self.peak_frequency1)

    def toggle_hold(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            print("Animation paused")
            self.button_hold.setStyleSheet(
                "background-color: #ff2222; color: white; font-weight: bold;"
            )
        else:
            print("Animation resumed")
            self.button_hold.setStyleSheet(
                "background-color: #222222; color: white; font-weight: bold;"
            )
    # tried to get mouse over value but failed
    def mouse_move_event(self, evt):
        if evt:
            pos = self.two_d_widget.widget.plotItem.vb.mapSceneToView(evt)
            x = pos.x()
            y = pos.y()

            # Update the cursor text
            self.cursor_text.setText(f"x: {x:.2f} MHz\n" f"y: {y:.2f} dB")
            self.cursor_text.setPos(x, y)
    
            
    def toggle_max_hold(self):
        self.max_hold = not self.max_hold
        if self.max_hold:
            print("Max hold enabled")
            self.status_label.setText("Max hold enabled")
            self.max_hold_buffer = None
        else:
            print("Max hold disabled")
            self.status_label.setText("Max hold disabled")

    def toggle_orientation(self):
        print("Toggle orientation")
        
        # Remove existing widgets if necessary
        if self.layout():
            # Clear the layout to remove all existing widgets
            for i in reversed(range(self.layout().count())):
                widget = self.layout().itemAt(i).widget()
                if widget is not None:
                    widget.deleteLater()  # Properly delete the widget
                self.layout().takeAt(i)  # Remove from layout

        self.is_vertical = not self.is_vertical
        if self.is_vertical:
            print("Changing orientation to vertical")
            self.load_new_ui("mainwindowvertical.ui")
        else:
            print("Changing orientation to horizontal")
            self.load_new_ui("mainwindowhorizontal.ui")

        self.remap_widgets()
        
    def remap_widgets(self):
        self.initialise_buttons()
        self.status_label.setText("Select data source")
        self.set_button_focus_policy(self)  # Avoids buttons being active after pressing
        self.initialise_labels()
        self.update_button_labels()
        self.connect_buttons()
     
    def set_button_style(self, button_name, active):
        color = "#a0a0a0" if active else "#ffffff"
        button = getattr(self, button_name)
        button.setStyleSheet(
            f"background-color: {color}; color: black; font-weight: {'normal' if not active else 'bold'};"
        )

    def use_data_source(self, source_class, button_name):
        self.max_hold_buffer = None
        print(f"Using {button_name} data source")
        self.data_source = source_class(self.CENTRE_FREQUENCY)
        self.set_active_button(button_name)
        self.timer.start(20)

    def set_active_button(self, active_button):
        for name in self.buttons:
            self.set_button_style(name, name == active_button)
 
    def use_rtl_source(self):
        

        self.max_hold_buffer = None
        print("Using RTL-SDR data source")
        self.status_label.setText("Starting RTL device")
        app.processEvents()
        if self.rtl_initialised:
            print("RTL-SDR data source is already initialised.")
        else:
            self.data_source = RtlSdrDataSource(self.CENTRE_FREQUENCY)
        
        #self.bias_t = self.data_source.bias_tee
        self.window = self.dsp.create_window(self.data_source.sample_rate, "hamming")
        self.status_label.setText("RTL FFT running")
        print (self.data_source)
        
        # This fails after going to audio source with:
        #  <datasources.audio_fft.AudioDataSource object at 0x7f6d85ec56d0>
        # When it should be the rtl data source

        print(self.data_source.sdr.get_device_serial_addresses())

        self.status_label.setText(
            "RTL FFT device " + str(self.data_source.sdr.get_device_serial_addresses())
        )
        self.rtl_initialised = True

        self.timer.start(20)

    def use_hackrf_source(self):
        self.max_hold_buffer = None
        print("Using HackRF data source")

        self.data_source = HackRFDataSource(self.CENTRE_FREQUENCY)
        # object.get_device_serial_addresses()
        self.status_label.setText("HackRF FFT running")
        self.timer.start(20)

    def use_rtl_sweep_source(self):
        self.max_hold_buffer = None
  
        print("Using RTL-SDR sweep data source")
        self.data_source = RtlSweepDataSource(self.CENTRE_FREQUENCY)
        self.timer.start(20)

    def use_hackrf_sweep_source(self):
        self.max_hold_buffer = None

        print("Using HackRF sweep data source")

        def my_sweep_callback(data):
            # Process the sweep data here
            print("Sweep data received:", data)

        self.data_source = HackRFSweepDataSourceOld(
            start_freq=self.CENTRE_FREQUENCY - 1e6,
            stop_freq=self.CENTRE_FREQUENCY + 1e6,
        )
        self.timer.start(20)

    def use_audio_source(self):
        self.max_hold_buffer = None
        print("Using audio data source")
        
        self.sample_rate = 44100
        self.data_source = AudioDataSource()
        self.window = self.dsp.create_window(self.data_source.sample_rate, "hamming")
        self.status_label.setText("Audio running")
        self.timer.start(20)

    def preset(self):
        self.two_d_widget.widget.getPlotItem().autoRange()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    # window.showMaximized()
    window.show()
    sys.exit(app.exec())
