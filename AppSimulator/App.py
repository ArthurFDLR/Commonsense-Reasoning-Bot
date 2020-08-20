import sys
import numpy as np
import time

from PyQt5 import QtWidgets as Qtw
from PyQt5 import QtGui
from PyQt5.QtCore import Qt, QThread, QRect, pyqtSignal, pyqtSlot
from PyQt5.Qt import QThreadPool

from Simulator import SimulationThread, SimulationControler, GraphPlotWidget
from Util import printHeadLine
#from VideoAnalysis import VideoAnalysisThread, VideoViewer
from SpatialGraph import MyScene, SpatialGraph, ObjectSet
from CameraInput import CameraInput
from ProgramASP.CommunicationASP import CommunicationAspThread
        
class MainWidget(Qtw.QWidget):
    def __init__(self, graph:SpatialGraph, objects:ObjectSet, parent=None):
        super().__init__()

        self.layout=Qtw.QVBoxLayout(self)
        self.setLayout(self.layout)
        self.parent = parent
        #self.layout.addWidget(Qtw.QPushButton('Simu test', self, clicked=lambda: print('yo'), objectName='simuButton'))
        #self.layout.addWidget(Qtw.QPushButton('Printing test', self, clicked=lambda: print('Hey'), objectName='printButton'))

        #self.videoViewer = VideoViewer()
        #self.videoViewer.setVideoSize(int(360 * (16.0/9.0)), 360)
        self.simulationControler = SimulationControler(graph, objects)
        #self.layout.addWidget(self.videoViewer, stretch = 1)
        self.layout.addWidget(self.simulationControler, stretch = 1)
    '''
    def resizeEvent(self, event):
        self.videoHeight = int(self.height()/3.5)
        self.parent.analysisThread.setResolutionStream(int(self.videoHeight * (16.0/9.0)), self.videoHeight)
        self.videoViewer.setVideoSize(int(self.videoHeight * (16.0/9.0)), self.videoHeight)
    '''

class MainWindow(Qtw.QMainWindow):

    def __init__(self, parentApp=None):
        super(MainWindow, self).__init__()
        printHeadLine('INITIALISATION')

        self.restaurantGraph, self.restaurantObjects = MyScene()
        self.parentApp = parentApp
        self.setWindowTitle("RVS - Robotics Vision Simulator")
        self.centralWidget = MainWidget(self.restaurantGraph, self.restaurantObjects, self)
        self.setCentralWidget(self.centralWidget)
        self.threadsInit()
        self.signalsInit()

        printHeadLine('Application ready')
        #self.centralWidget.simulationControler.newOrderPepper_Position.emit('d', 3.0*(np.pi/4.0))
    
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

        #self.cameraInput = CameraInput()

        #self.analysisThread = VideoAnalysisThread(self.cameraInput)
        #self.analysisThread.start()

        self.aspThread = CommunicationAspThread()
        self.aspThread.setState(False)
        self.aspThread.start()

        self.simThread = SimulationThread(self.aspThread, self.restaurantGraph, self.restaurantObjects)
        self.simThread.setState(True)
        self.simThread.start()

    def signalsInit(self):
        #self.analysisThread.newPixmap.connect(self.centralWidget.videoViewer.setImage)
        #self.simThread.newPixmapPepper.connect(self.centralWidget.videoViewer.setPepperImage)
        #self.simThread.newPositionPepper_signal.connect(self.centralWidget.simulationControler.graphPlotWidget.updatePepperPosition)

        self.centralWidget.simulationControler.newOrderPepper_Position.connect(self.simThread.pepperGoTo)
        self.centralWidget.simulationControler.newOrderPepper_HeadPitch.connect(lambda p: self.simThread.pepper.setHeadPosition(pitch=p))
        self.centralWidget.simulationControler.simButton.clickedChecked.connect(self.aspThread.setState)
        #self.centralWidget.simulationControler.simButton.clickedChecked.connect(self.analysisThread.setState)

        self.centralWidget.simulationControler.addClient_signal.connect(self.addClient)
        self.centralWidget.simulationControler.removeClient_signal.connect(self.removeClient)
    
    @pyqtSlot(str)
    def addClient(self, name):
        if self.restaurantObjects.isChair(name):
            self.simThread.addSeatedClient('.\\alfred\\seated\\alfred.obj',name)
        elif self.restaurantGraph.isPosition(name):
            self.simThread.addStandingClient('.\\alfred\\stand\\alfred.obj',name, self.centralWidget.simulationControler.getDialOrientation())
    
    @pyqtSlot(str)
    def removeClient(self, name):
        if self.restaurantObjects.isChair(name):
            self.simThread.removeSeatedClient(name)
        elif self.restaurantGraph.isPosition(name):
            self.simThread.removeStandingClient(name)

if __name__ == "__main__":
    app = Qtw.QApplication(sys.argv)

    appGui = MainWindow(app)
    appGui.show()

    sys.exit(app.exec_())

