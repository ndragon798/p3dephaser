from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QListWidget, QMessageBox, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtGui import QIcon, QColor
from .ScanWorker import ScanWorker
import psutil, threading

TITLE = 'Panda3D Dephaser'

class MainWidget(QWidget):

    def __init__(self, base):
        QWidget.__init__(self)

        self.base = base

        self.setWindowIcon(QIcon('icon.ico'))
        self.setWindowTitle(TITLE)
        self.set_background_color(QColor(255, 255, 255))

        self.process_header_widget = QWidget()
        self.process_header_layout = QHBoxLayout(self.process_header_widget)
        self.process_header_layout.setContentsMargins(0, 0, 0, 0)

        self.process_label = QLabel('Available processes:')
        self.github_label = QLabel('<a href="https://github.com/darktohka/p3dephaser">GitHub</a>')
        self.github_label.setOpenExternalLinks(True)

        self.refresh_button = QPushButton('Refresh')
        self.refresh_button.clicked.connect(self.refresh_processes)
        self.refresh_button.setFixedSize(100, 23)

        self.multifile_widget = QWidget()
        self.multifile_layout = QHBoxLayout(self.multifile_widget)
        self.multifile_layout.setContentsMargins(0, 0, 0, 0)
        self.multifileLabel = QLabel('Requested multifile names:')
        self.multifileBox = QLineEdit(self)
        self.multifileBox.returnPressed.connect(self.begin_scan)

        self.multifile_layout.addWidget(self.multifileLabel)
        self.multifile_layout.addWidget(self.multifileBox)

        self.scan_button = QPushButton('Scan')
        self.scan_button.clicked.connect(self.begin_scan)

        self.process_list_box = QListWidget()

        self.process_header_layout.addWidget(self.process_label)
        self.process_header_layout.addStretch(1)
        self.process_header_layout.addWidget(self.github_label)
        self.process_header_layout.addWidget(self.refresh_button)

        self.result_table = QTableWidget()
        self.result_table.setColumnCount(3)
        self.result_table.horizontalHeader().setStretchLastSection(True)
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        for i, header in enumerate(('Process', 'Multifile', 'Password')):
            self.result_table.setHorizontalHeaderItem(i, QTableWidgetItem(header))

        self.base_layout = QVBoxLayout(self)
        self.base_layout.setContentsMargins(15, 15, 15, 15)
        self.base_layout.addWidget(self.process_header_widget)
        self.base_layout.addWidget(self.process_list_box)
        self.base_layout.addWidget(self.multifile_widget)
        self.base_layout.addWidget(self.scan_button)
        self.base_layout.addWidget(self.result_table)

        self.refresh_processes()

        self.thread_pool = QThreadPool()
        self.worker = None
        self.process_name = None
        self.stop_event = threading.Event()

    def set_background_color(self, color):
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), color)
        self.setPalette(palette)

    def get_processes(self):
        processes = []

        for proc in psutil.process_iter():
            processes.append(proc.as_dict(attrs=['pid', 'name']))

        processes.sort(key=lambda process: (process['name'].lower(), process['pid']))
        return processes

    def refresh_processes(self):
        self.process_list_box.clear()
        processes = self.get_processes()

        for process in processes:
            name = process['name']
            pid = process['pid']
            self.process_list_box.addItem(f'{name} (PID {pid})')

    def begin_scan(self):
        if self.worker:
            self.stop_event.set()
            self.scan_button.setEnabled(False)
            return

        items = self.process_list_box.selectedItems()

        if not items:
            QMessageBox.warning(self, TITLE, 'Please choose a process from the list!')
            return

        process = items[0].text()[:-1].split(' ')
        self.process_name = ' '.join(process[:-2])
        pid = int(process[-1])
        multifiles = self.multifileBox.text().split()

        if not multifiles:
            QMessageBox.warning(self, TITLE, 'Please choose some multifiles to target!')
            return

        multifile_names = '\n'.join([f'- {multifile}' for multifile in multifiles])
        question = f'Do you really want to scan {self.process_name} for the following multifiles?\n\n{multifile_names}'

        if QMessageBox.question(self, TITLE, question, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return

        self.count = 0

        self.setWindowTitle(f'{TITLE} - Scanning...')
        self.scan_button.setText('Stop')

        self.worker = ScanWorker(self, pid, multifiles)
        self.worker.signals.finished.connect(self.scan_over)
        self.worker.signals.error.connect(self.error_occurred)
        self.worker.signals.progress.connect(self.report_progress)

        self.thread_pool.start(self.worker)

    def scan_over(self):
        self.worker = None
        self.stop_event.clear()

        self.scan_button.setText('Scan')
        self.scan_button.setEnabled(True)
        self.setWindowTitle(TITLE)
        QMessageBox.information(self, TITLE, f'Scan complete!\n\n{self.count} password{"s have" if self.count != 1 else " has"} been found.')

    def error_occurred(self, error):
        exc, value, message = error
        QMessageBox.critical(self, TITLE, f'An error has occurred while trying to scan this process!\n\n{exc} {value}\n\n{message}')

    def report_progress(self, multifile, password):
        self.count += 1
        index = self.result_table.rowCount()

        self.result_table.insertRow(index)

        for i, value in enumerate((self.process_name, multifile, password)):
            self.result_table.setItem(index, i, QTableWidgetItem(value))
