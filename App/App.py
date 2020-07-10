import sys
import numpy as np

from PyQt5 import QtWidgets as Qtw
from PyQt5 import QtGui
from PyQt5.QtCore import Qt, QThread, QRect, pyqtSignal, pyqtSlot
from PyQt5.Qt import QThreadPool

from Simulator import SimulationThread, SimulationControler, GraphPlotWidget
from Util import printHeadLine
from VideoAnalysis import VideoCaptureThread, VideoAnalysisThread, VideoViewer
from SpatialGraph import MyGraph
from CameraInput import CameraInput
        
class MainWidget(Qtw.QWidget):
    def __init__(self):
        super().__init__()

        self.layout=Qtw.QVBoxLayout(self)
        self.setLayout(self.layout)
        #self.layout.addWidget(Qtw.QPushButton('Simu test', self, clicked=lambda: print('yo'), objectName='simuButton'))
        #self.layout.addWidget(Qtw.QPushButton('Printing test', self, clicked=lambda: print('Hey'), objectName='printButton'))

        self.videoViewer = VideoViewer()
        self.simulationControler = SimulationControler(MyGraph())
        self.layout.addWidget(self.videoViewer, stretch = 1)
        self.layout.addWidget(self.simulationControler, stretch = 1)


class MainWindow(Qtw.QMainWindow):

    def __init__(self, parentApp=None):
        super(MainWindow, self).__init__()
        printHeadLine('INITIALISATION')

        self.parentApp = parentApp
        self.setWindowTitle("RVS - Robotics Vision Simulator")
        self.centralWidget = MainWidget()
        self.setCentralWidget(self.centralWidget)
        self.threadsInit()
        self.signalsInit()

        printHeadLine('Application ready')
        self.simThread.pepperGoTo('n')
    
    '''
    def closeEvent(self, event):
        print('Close simulation window or stop console execution.')
        event.ignore()
    '''
    
    def threadsInit(self):
        maxThread = QThreadPool().maxThreadCount()
        nbrThread = 3
        print("%d threads needed." % nbrThread)
        print("%d threads available." % maxThread)

        #self.videoThread = VideoCaptureThread('http://S9:S9@192.168.1.38:8080/video')
        #self.videoThread.start()

        self.cameraInput = CameraInput()

        self.analysisThread = VideoAnalysisThread(self.cameraInput)
        self.analysisThread.start()

        self.simThread = SimulationThread(MyGraph())
        self.simThread.start()


    def signalsInit(self):
        self.analysisThread.newPixmap.connect(self.centralWidget.videoViewer.setImage)
        self.simThread.newPixmapPepper.connect(self.centralWidget.videoViewer.setPepperImage)
        
        self.centralWidget.simulationControler.newOrderPepper_Position.connect(self.simThread.pepperGoTo)
        self.centralWidget.simulationControler.newOrderPepper_HeadPitch.connect(lambda p: self.simThread.pepper.setHeadPosition(pitch=p))
        self.centralWidget.simulationControler.simButton.clickedChecked.connect(self.simThread.setState)
        self.centralWidget.simulationControler.simButton.clickedChecked.connect(self.analysisThread.setState)


if __name__ == "__main__":
    app = Qtw.QApplication(sys.argv)

    appGui = MainWindow(app)
    appGui.show()

    sys.exit(app.exec_())

