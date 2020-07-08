import sys

from PyQt5 import QtWidgets as Qtw
from PyQt5.QtCore import Qt, QThread,  pyqtSignal, pyqtSlot
from PyQt5.Qt import QThreadPool

from Simulator import SimulationThread
from Util import printHeadLine
from VideoAnalysis import VideoCaptureThread, VideoAnalysisThread, VideoViewer

class MainWidget(Qtw.QWidget):
    def __init__(self):
        super().__init__()

        self.layout=Qtw.QHBoxLayout(self)
        self.setLayout(self.layout)
        #self.layout.addWidget(Qtw.QPushButton('Simu test', self, clicked=lambda: print('yo'), objectName='simuButton'))
        #self.layout.addWidget(Qtw.QPushButton('Printing test', self, clicked=lambda: print('Hey'), objectName='printButton'))

        self.videoViewer = VideoViewer()
        self.layout.addWidget(self.videoViewer)

class MainWindow(Qtw.QMainWindow):

    def __init__(self, parentApp=None):
        super(MainWindow, self).__init__()
        printHeadLine('INITIALISATION')

        self.parentApp = parentApp
        self.setWindowTitle("Interface")
        self.centralWidget = MainWidget()
        self.setCentralWidget(self.centralWidget)

        self.threadsInit()
        printHeadLine('Application ready')
        self.SimThread.pepperGoTo('n')
    
    def closeEvent(self, event):
        print('Close simulation window or stop console execution.')
        event.ignore()

    
    def threadsInit(self):
        maxThread = QThreadPool().maxThreadCount()
        nbrThread = 2
        print("%d threads needed." % nbrThread)
        print("%d threads available." % maxThread)

        self.SimThread = SimulationThread()
        self.SimThread.start()

        self.VideoThread = VideoCaptureThread('http://S9:S9@192.168.1.38:8080/video')
        self.VideoThread.start()

        self.AnalysisThread = VideoAnalysisThread(self.VideoThread)
        self.AnalysisThread.start()

        self.AnalysisThread.newPixmap.connect(self.centralWidget.videoViewer.setImage)


if __name__ == "__main__":
    app = Qtw.QApplication(sys.argv)

    appGui = MainWindow(app)
    appGui.show()

    sys.exit(app.exec_())

