#!/usr/bin/python3
import sys
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
    #CENTRE_FREQUENCY = 1552e6 #2412e6
    #CENTRE_FREQUENCY = 2412e6
    #CENTRE_FREQUENCY = 125e6
    #CENTRE_FREQUENCY = 434e6

    GAIN = 36.4  # where is this value used?
    AMPLIFIER = True
    LNA_GAIN = 10
    VGA_GAIN = 10
    sweep_data = None
    INITIAL_SAMPLE_SIZE = 2048
    INITIAL_NUMBER_OF_LINES = 20
    dsp = SignalProcessing.process()
    # data_source: DataSourceDataSource | SweepDataSource = None    # Only newer python
    data_source: Union[SampleDataSource, SweepDataSource] = None

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

        self.stacked_widget.addWidget(self.two_d_widget.widget)
        self.stacked_widget.addWidget(self.three_d_widget.widget)
        layout = self.findChild(QtWidgets.QWidget, "graphical_display")
        layout.layout().addWidget(self.stacked_widget)
        self.current_display = "plot"
        self.stacked_widget.setCurrentIndex(0)  # Show 2D plot initially
        self.display_logo()

        # tried to get mouse over value but failed
        self.cursor_text = pg.TextItem('', anchor=(0, 1))
        self.two_d_widget.widget.addItem(self.cursor_text)
        self.two_d_widget.widget.plotItem.scene().sigMouseMoved.connect(self.mouse_move_event)



        self.peak_frequency1 = "Peak On"
        self.peak_power = None
        self.is_peak_on = False
        self.power_db = None
        self.data_source = None
        self.engformat = mpl.ticker.EngFormatter(places=3)
        self.timer = QtCore.QTimer()  # timer for updating plot
        self.timer.timeout.connect(self.update_plot)
        self.is_paused = False
        self.menu_manager = MenuManager(option_callback=self.option_selected)  #MenuManager()
        self.bias_t = False
        self.max_hold = False
        self.max_hold_buffer = None

        self.initialise_buttons()
        self.status_label.setText("Select data source")
        self.set_button_focus_policy(self)  # Avoids buttons being active after pressing

        self.initialise_labels()
        self.update_button_labels()
        self.connect_buttons()

        # Simulate user actions
        #menu_manager.show_submenu("rtlfft1")
        #menu_manager.handle_button_press(2)  # Example button press for "Remove DC"

        if self.button_hold:
            self.button_hold.pressed.connect(self.toggle_hold)
        if self.button_peak:
            self.button_peak.pressed.connect(self.toggle_peak)
        if self.button2d3d:
            self.button2d3d.pressed.connect(self.toggle_display)
        if self.buttonverthoriz:
            self.buttonverthoriz.pressed.connect(self.toggle_orientation)
        if self.buttonmaxhold:
            self.buttonmaxhold.pressed.connect(self.toggle_max_hold)

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
        if parent_menu is None:
            print("Parent menu is not defined.")
            return

        print(f"Parent menu is: {parent_menu}")
        print(f"Current menu is: {current_menu}")
        print(f"Selected option is: {option}")

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
            if option == "Audio":
                self.use_audio_source() 
                self.menu_manager.select_submenu("Audio FFT")  
                self.menu_manager.update_button_labels()  




    def load_new_ui(self, ui_file):
        # Clear the existing layout
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
        ]
        self.buttons = {
            name: self.findChild(QtWidgets.QPushButton, name) for name in button_names
        }

    def connect_buttons(self):
        self.button_frequency.pressed.connect(lambda: self.handle_menu_button("Frequency"))
        self.button_span.pressed.connect(lambda: self.handle_menu_button("Span"))
        self.button_amplitude.pressed.connect(lambda: self.handle_menu_button("Amplitude"))
        self.button_input.pressed.connect(lambda: self.handle_menu_button("Input"))
        self.buttonsoft1.pressed.connect(lambda: self.handle_soft_button(0))
        self.buttonsoft2.pressed.connect(lambda: self.handle_soft_button(1))
        self.buttonsoft3.pressed.connect(lambda: self.handle_soft_button(2))
        self.button_mode.pressed.connect(lambda: self.handle_menu_button("mode1"))
        self.button_rtl_fft.pressed.connect(lambda: self.handle_menu_button("rtlfft1"))
        self.button_hackrf_fft.pressed.connect(lambda: self.handle_menu_button("hackrffft1"))
        self.button_audio_fft.pressed.connect(lambda: self.handle_menu_button("audio1"))
    

    def initialise_labels(self):
        self.output_centre_freq = self.findChild(QtWidgets.QLabel, "output_centre_freq")
        self.output_sample_rate = self.findChild(QtWidgets.QLabel, "output_sample_rate")
        self.output_span = self.findChild(QtWidgets.QLabel, "output_span")
        self.output_start_freq = self.findChild(QtWidgets.QLabel, "output_start_freq")
        self.output_stop_freq = self.findChild(QtWidgets.QLabel, "output_stop_freq")
        self.output_gain = self.findChild(QtWidgets.QLabel, "output_gain")
        self.output_gain = self.findChild(QtWidgets.QLabel, "output_gain")
        self.output_res_bw = self.findChild(QtWidgets.QLabel, "output_res_bw")
        self.input_value = self.findChild(QtWidgets.QLabel, "input_value")
        self.output_centre_freq = self.findChild(QtWidgets.QLabel, "output_centre_freq")
        self.output_sample_rate = self.findChild(QtWidgets.QLabel, "output_sample_rate")

        if self.button_rtl_fft:
            self.button_rtl_fft.pressed.connect(self.use_rtl_source)
        if self.button_hackrf_fft:
            self.button_hackrf_fft.pressed.connect(self.use_hackrf_source)
        if self.button_rtl_sweep:
            self.button_rtl_sweep.pressed.connect(self.use_rtl_sweep_source)
        if self.button_hackrf_sweep:
            self.button_hackrf_sweep.pressed.connect(self.use_hackrf_sweep_source)
        if self.button_audio_fft:
            self.button_audio_fft.pressed.connect(self.use_audio_source)
        if self.button_preset:
            self.button_preset.pressed.connect(self.preset)

    def set_button_focus_policy(self, parent):
        for widget in parent.findChildren(QtWidgets.QPushButton):
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def keyPressEvent(self, event):
        key_actions = {
            Qt.Key.Key_F: lambda: self.show_submenu("frequency"),
            Qt.Key.Key_S: lambda: self.show_submenu("span"),
            Qt.Key.Key_A: lambda: self.show_submenu("amplitude"),
            Qt.Key.Key_I: lambda: self.show_submenu("input"),
            Qt.Key.Key_Space: self.toggle_hold,
            Qt.Key.Key_P: self.toggle_peak,
            Qt.Key.Key_O: self.toggle_orientation,
            Qt.Key.Key_X: self.toggle_max_hold,
            Qt.Key.Key_M: lambda: self.print_something("fdsasdff1"),
            Qt.Key.Key_B: lambda: self.toggle_bias_t(),           
#            (Qt.Key.Key_F, Qt.KeyboardModifier.Control): self.toggle_fullscreen # CTRL + F for fullscreen later
        }
        action = key_actions.get(event.key())
        if action:
            action()
            event.accept()


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
                    self.output_centre_freq.setText(
                        self.engformat(self.data_source.centre_freq) + "Hz"
                    )
                    self.output_sample_rate.setText(
                        f"{int(self.data_source.sample_rate):,} SPS"
                    )
                    self.output_start_freq.setText(
                        self.engformat(
                            self.data_source.centre_freq
                            - self.data_source.sample_rate / 2
                        )
                        + "Hz"
                    )
                    self.output_stop_freq.setText(
                        self.engformat(
                            self.data_source.centre_freq
                            + self.data_source.sample_rate / 2
                        )
                        + "Hz"
                    )
                    self.output_span.setText(
                        self.engformat(self.data_source.sample_rate) + "Hz"
                    )
                    self.output_gain.setText(str(self.data_source.gain) + " dB")
                    self.output_res_bw.setText(
                        self.engformat(
                            self.data_source.sample_rate / self.INITIAL_SAMPLE_SIZE
                        )
                        + "Hz"
                    )
                    self.output_sample_size.setText(str(self.INITIAL_SAMPLE_SIZE))
                    samples = self.data_source.read_samples(self.INITIAL_SAMPLE_SIZE)

                    if samples is not None and len(samples) > 0:
                        fft = self.dsp.do_fft(samples)
                        if isinstance(self.data_source, AudioDataSource):
                            centrefft = fft[: int(self.INITIAL_SAMPLE_SIZE // 2)]
                            magnitude = self.dsp.get_magnitude(centrefft)
                            self.power_db = self.dsp.get_log_magnitude(magnitude)
                            frequency_bins = np.linspace(
                                0, self.data_source.sample_rate, len(self.power_db)
                            )
                            half_length = (
                                len(frequency_bins) // 2
                            )  # Calculate half length
                            frequency_bins = frequency_bins[:half_length]
                            self.power_db = self.power_db[:half_length]
                        else:
                            centrefft = self.dsp.do_centre_fft(fft)
                            magnitude = self.dsp.get_magnitude(centrefft)
                            self.power_db = self.dsp.get_log_magnitude(magnitude)
                            frequency_bins = np.linspace(
                                0, self.data_source.sample_rate, len(self.power_db)
                            )
                            frequency_bins += (
                                self.CENTRE_FREQUENCY - self.data_source.sample_rate / 2
                            )

                        if self.max_hold:
                            if self.max_hold_buffer is None:
                                self.max_hold_buffer = self.power_db.copy()
                            else:
                                self.max_hold_buffer = np.maximum(
                                    self.max_hold_buffer, self.power_db
                                )

                        # Plot max first if enabled
                        if self.current_display == "plot":
                            self.two_d_widget.widget.clear()
                        if self.max_hold is True and self.max_hold_buffer is not None:
                            self.two_d_widget.widget.plot(
                                frequency_bins / 1e6, self.max_hold_buffer, pen="y"
                            )

                        # Plot live value
                        self.two_d_widget.widget.plot(
                            frequency_bins / 1e6, self.power_db, pen="g"
                        )


                        
                        if self.is_peak_on:

                            if self.power_db is not None and len(self.power_db) > 0:
                                index_of_peak = np.argmax(self.power_db)
                                peak_value = self.power_db[index_of_peak]
                                peak_frequency = (
                                    frequency_bins[index_of_peak] / 1e6
                                )  # for y value, but undecided

                                text = (
                                    f"<span style='color: green;background-color: black;'>Live peak</span> <br>"
                                    f" <span style='color: white;background-color: black;'>{peak_frequency:.2f} MHz</span> <br>"
                                    f" <span style='color: white;background-color: black;'>{peak_value:.2f} dB</span>"
                                )

                                self.peak_frequency1 = pg.TextItem(text)
                                self.peak_frequency1.setHtml(
                                    text
                                )  # Use setHtml instead of setText
                                y_range = self.two_d_widget.widget.viewRange()[
                                    1
                                ]  # Get the Y range
                                y_min, y_max = y_range
                                nine_tenths_height = y_min + 0.9 * (y_max - y_min)
                                self.peak_frequency1.setPos(
                                    peak_frequency, nine_tenths_height
                                )

                                if self.max_hold == True:

                                    index_of_max_peak = np.argmax(self.max_hold_buffer)
                                    max_peak_value = self.max_hold_buffer[
                                        index_of_max_peak
                                    ]
                                    max_peak_frequency = (
                                        frequency_bins[index_of_max_peak] / 1e6
                                    )

                                    db_drops = [3, 6, 9]
                                    thresholds = [
                                        max_peak_value - db_drop for db_drop in db_drops
                                    ]

                                    def find_bandwidth_points(threshold):
                                        lower_index = index_of_max_peak
                                        while (
                                            lower_index > 0
                                            and self.max_hold_buffer[lower_index]
                                            > threshold
                                        ):
                                            lower_index -= 1

                                        upper_index = index_of_max_peak
                                        while (
                                            upper_index < len(self.max_hold_buffer) - 1
                                            and self.max_hold_buffer[upper_index]
                                            > threshold
                                        ):
                                            upper_index += 1

                                        return (
                                            frequency_bins[lower_index] / 1e6,
                                            frequency_bins[upper_index] / 1e6,
                                        )

                                    (
                                        lower_freq_3db,
                                        upper_freq_3db,
                                    ) = find_bandwidth_points(thresholds[0])
                                    (
                                        lower_freq_6db,
                                        upper_freq_6db,
                                    ) = find_bandwidth_points(thresholds[1])
                                    (
                                        lower_freq_9db,
                                        upper_freq_9db,
                                    ) = find_bandwidth_points(thresholds[2])

                                    # Get the Y range
                                    y_range = self.two_d_widget.widget.viewRange()[1]
                                    y_min, y_max = y_range

                                    # Calculate the y-values (10% of the y-range centered around -3 dB value)
                                    db_drop = 3
                                    threshold_value = max_peak_value - db_drop
                                    y_centre = (max_peak_value - db_drop) + (
                                        y_max - y_min
                                    ) * 0.1
                                    y_value_lower = y_centre - 20
                                    y_value_upper = y_centre + 20

                                    # 3dB max peak bandwidth markers
                                    # x1 = lower_freq_3db
                                    # x2 = upper_freq_3db
                                    # y1 = y_value_lower
                                    # y2 = y_value_upper
                                    # self.two_d_widget.widget.plot([x1, x1], [y1, y2], pen='c')  #
                                    # self.two_d_widget.widget.plot([x2, x2], [y1, y2], pen='c')  #

                                    # Calculate bandwidths
                                    bandwidth_3db = upper_freq_3db - lower_freq_3db
                                    bandwidth_6db = upper_freq_6db - lower_freq_6db
                                    bandwidth_9db = upper_freq_9db - lower_freq_9db

                                    # Prepare the max peak text
                                    max_peak_text = (
                                        f"<span style='color: yellow;background-color: black;'>Max peak</span> <br>"
                                        f"<span style='color: white;background-color: black;'>{max_peak_frequency:.2f} MHz</span><br>"
                                        f"<span style='color: white; background-color: black;'>{max_peak_value:.2f} dB</span><br>"
                                    )

                                    self.max_frequency1 = pg.TextItem(max_peak_text)
                                    self.max_frequency1.setHtml(max_peak_text)

                                    y_range = self.two_d_widget.widget.viewRange()[
                                        1
                                    ]  # Get the Y range
                                    y_min, y_max = y_range
                                    six_tenths_height = y_max
                                    self.max_frequency1.setPos(
                                        max_peak_frequency, six_tenths_height
                                    )
                                    self.two_d_widget.widget.addItem(
                                        self.max_frequency1
                                    )

                                self.two_d_widget.widget.addItem(self.peak_frequency1)


                        self.three_d_widget.z = self.power_db / 10

                except Exception as e:
                    print(f"Error reading samples: {e}")

            elif isinstance(self.data_source, SweepDataSource):
                if self.sweep_data is not None:
                    self.two_d_widget.plot(
                        self.sweep_data["x"], self.sweep_data["y"], pen="g"
                    )
                    index_of_peak = np.argmax(self.sweep_data["y"])
                    peak_y_value = self.sweep_data["y"][index_of_peak]
                    corresponding_x_value = self.sweep_data["x"][index_of_peak]
                    # print("Peak value is " + str(peak_y_value))
                    # print("At frequency  " + str(corresponding_x_value))
                    text_item = pg.TextItem(
                        str(self.engformat(corresponding_x_value))
                        + "Hz\n"
                        + str(self.engformat(peak_y_value) + " dB")
                    )
                    text_item.setPos(corresponding_x_value / 1e6, peak_y_value)

    def show_submenu(self, menu_name):
        self.menu_manager.show_submenu(menu_name)
        self.update_button_labels()

    def handle_menu_button(self, menu_name):
        self.show_submenu(menu_name)
        print (f"Current menu level: {menu_name}")

        if menu_name.lower() == "frequency":
            self.status_label.setText("Centre Frequency")
        elif menu_name.lower() == "span":
            self.status_label.setText("Span:")
        elif menu_name.lower() == "amplitude":
            self.status_label.setText("Amplitude:")
        elif menu_name.lower() == "input":
            self.status_label.setText("Input")

        self.update_button_labels_for_menu(menu_name)

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


    def update_button_labels(self):
        labels = self.menu_manager.get_button_labels()
        buttons = [
            self.buttonsoft1,
            self.buttonsoft2,
            self.buttonsoft3,
            self.buttonsoft4,
            self.buttonsoft5,
            self.buttonsoft6,
            self.buttonsoft7,
            self.buttonsoft8,
        ]

        for i, button in enumerate(buttons):
            if i < len(labels):
                button.setText(labels[i])
            else:
                button.setText("")
    
    def show_submenu(self, menu_name):
        self.menu_manager.select_submenu(menu_name)
        self.update_soft_button_labels()  

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

    def toggle_peak(self):
        self.is_peak_on = not self.is_peak_on
        if self.is_peak_on:
            print("Peak on")
            """
            # Get the current maximum value and its corresponding frequency
            if self.power_db is not None and len(self.power_db) > 0:
                index_of_peak = np.argmax(self.power_db)
                peak_value = self.power_db[index_of_peak]
                frequency_bins = np.linspace(0, self.data_source.sample_rate, len(self.power_db))
                peak_frequency = frequency_bins[index_of_peak] / 1e6  # Convert to MHz for display
                print (peak_frequency)

                self.peak_frequency1 = pg.TextItem(f"Peak: {peak_value:.2f} dB\nFreq: {peak_frequency:.2f} MHz")
                self.peak_frequency1.setPos(peak_frequency, peak_value)  # Set position based on peak frequency and value
                
                self.two_d_widget.widget.addItem(self.peak_frequency1)
            """
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

        # Optionally, remap widgets here if needed
        self.remap_widgets()
        
    def remap_widgets(self):
        self.initialise_buttons()
        self.status_label.setText("Select data source")
        self.set_button_focus_policy(self)  # Avoids buttons being active after pressing

        self.initialise_labels()
        self.update_button_labels()
        self.connect_buttons()
    
        pass

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
        self.button_rtl_fft.setStyleSheet(
            "background-color: #a0a0a0; color: black; font-weight: normal;"
        )
        self.button_hackrf_fft.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        self.button_rtl_sweep.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        self.button_hackrf_sweep.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        self.button_audio_fft.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        app.processEvents()
        self.data_source = RtlSdrDataSource(self.CENTRE_FREQUENCY)
        
        #self.bias_t = self.data_source.bias_tee
        self.window = self.dsp.create_window(self.data_source.sample_rate, "hamming")
        self.status_label.setText("RTL FFT running")
        # print (self.data_source.sdr.get_device_serial_addresses())
        print(self.data_source.sdr.get_device_serial_addresses())
        self.status_label.setText(
            "RTL FFT device " + str(self.data_source.sdr.get_device_serial_addresses())
        )

        self.timer.start(20)

    def use_hackrf_source(self):
        self.max_hold_buffer = None
        print("Using HackRF data source")
        self.button_rtl_fft.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        self.button_hackrf_fft.setStyleSheet(
            "background-color: #a0a0a0; color: black; font-weight: normal;"
        )
        self.button_rtl_sweep.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        self.button_hackrf_sweep.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        self.button_audio_fft.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        self.data_source = HackRFDataSource(self.CENTRE_FREQUENCY)
        # object.get_device_serial_addresses()
        self.status_label.setText("HackRF FFT running")
        self.timer.start(20)

    def use_rtl_sweep_source(self):
        self.max_hold_buffer = None
        self.button_rtl_fft.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        self.button_hackrf_fft.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        self.button_rtl_sweep.setStyleSheet(
            "background-color: #a0a0a0; color: black; font-weight: normal;"
        )
        self.button_hackrf_sweep.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        self.button_audio_fft.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        print("Using RTL-SDR sweep data source")
        self.data_source = RtlSweepDataSource(self.CENTRE_FREQUENCY)
        self.timer.start(20)

    def use_hackrf_sweep_source(self):
        self.max_hold_buffer = None
        self.button_rtl_fft.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        self.button_hackrf_fft.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        self.button_rtl_sweep.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        self.button_hackrf_sweep.setStyleSheet(
            "background-color: #a0a0a0; color: black; font-weight: normal;"
        )
        self.button_audio_fft.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
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
        self.button_rtl_fft.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        self.button_hackrf_fft.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        self.button_rtl_sweep.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        self.button_hackrf_sweep.setStyleSheet(
            "background-color: #ffffff; color: black; font-weight: normal;"
        )
        self.button_audio_fft.setStyleSheet(
            "background-color: #a0a0a0; color: black; font-weight: normal;"
        )
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
