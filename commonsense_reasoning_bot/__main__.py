import sys
import numpy as np
import time

from PyQt5 import QtWidgets as Qtw
from PyQt5 import QtGui
from PyQt5.QtCore import Qt, QThread, QRect, pyqtSignal, pyqtSlot
from PyQt5.Qt import QThreadPool

from Simulator import SimulationThread, SimulationControler, GraphPlotWidget
from SpatialGraph import MyScene, SpatialGraph, ObjectSet
from ASP.CommunicationASP import CommunicationAspThread


class MainWidget(Qtw.QWidget):
    newLog_signal = pyqtSignal(str, str)

    def __init__(
        self,
        graph: SpatialGraph,
        objects: ObjectSet,
        newObservation_signal=pyqtSignal,
        parent=None,
    ):
        super().__init__()

        self.layout = Qtw.QVBoxLayout(self)
        self.setLayout(self.layout)
        self.parent = parent

        self.simulationControler = SimulationControler(
            graph, objects, newObservation_signal
        )
        self.layout.addWidget(self.simulationControler)  # , stretch = 1)

        self.logWidget = Qtw.QListWidget()
        self.layout.addWidget(self.logWidget)
        self.newLog_signal.connect(self.addLog)
        self.logs_colors = {'info':'#dbdbdb', 'update_asp':'#cfd7ff', 'error':'#ffcfcf', 'order':'#d7ffcf'}

    @pyqtSlot(str, str)
    def addLog(self, message: str, log_type:str='info'):
        # print(message)
        i = Qtw.QListWidgetItem(message)
        i.setBackground( QtGui.QColor(self.logs_colors[log_type]))
        self.logWidget.addItem(i)
        self.logWidget.scrollToBottom()


class MainWindow(Qtw.QMainWindow):
    newObservation_signal = pyqtSignal(str)

    def __init__(self, parentApp=None):
        super(MainWindow, self).__init__()

        self.restaurantGraph, self.restaurantObjects = MyScene()
        self.parentApp = parentApp
        self.setWindowTitle("RVS - Robotics Vision Simulator")
        self.centralWidget = MainWidget(
            self.restaurantGraph,
            self.restaurantObjects,
            self.newObservation_signal,
            self,
        )
        self.setCentralWidget(self.centralWidget)
        self.threadsInit()
        self.signalsInit()

    def threadsInit(self):
        maxThread = QThreadPool().maxThreadCount()
        nbrThread = 3
        print("%d threads needed." % nbrThread)
        print("%d threads available." % maxThread)

        self.aspThread = CommunicationAspThread(self.centralWidget.newLog_signal)
        self.aspThread.setState(False)
        self.aspThread.start()

        self.simThread = SimulationThread(
            self.aspThread,
            self.restaurantGraph,
            self.restaurantObjects,
            self.centralWidget.newLog_signal,
        )
        self.simThread.setState(True)
        self.simThread.start()

    def signalsInit(self):
        # self.analysisThread.newPixmap.connect(self.centralWidget.videoViewer.setImage)
        # self.simThread.newPixmapPepper.connect(self.centralWidget.videoViewer.setPepperImage)
        # self.simThread.newPositionPepper_signal.connect(self.centralWidget.simulationControler.graphPlotWidget.updatePepperPosition)
        self.centralWidget.simulationControler.newOrderPepper_Position.connect(
            self.simThread.pepperGoTo
        )
        self.centralWidget.simulationControler.newOrderPepper_HeadPitch.connect(
            lambda p: self.simThread.pepper.setHeadPosition(pitch=p)
        )
        self.centralWidget.simulationControler.simButton.clickedChecked.connect(
            self.setASPstate
        )

        # self.centralWidget.simulationControler.simButton.clickedChecked.connect(self.analysisThread.setState)

        self.centralWidget.simulationControler.addClient_signal.connect(self.addClient)
        self.centralWidget.simulationControler.removeClient_signal.connect(
            self.removeClient
        )
        self.centralWidget.simulationControler.newCustomerButton.clicked.connect(
            self.clientEnter
        )
        self.centralWidget.simulationControler.tableCallBill_signal.connect(
            self.tableCallBill
        )

        self.newObservation_signal.connect(
            lambda obs: self.aspThread.newObservation_signal.emit(obs, True)
        )
        self.newObservation_signal.connect(lambda obs: print("Call bill: " + obs))

    @pyqtSlot(bool)
    def setASPstate(self, state: bool):
        if state:
            initPepperPosition = "currentlocation(agent, {})".format(
                self.restaurantGraph.getStartingPosition()
            )
            initWaiterPosition = "currentlocation(w1, n7)"
            initialisation = [initPepperPosition, initWaiterPosition]

            dictClients = self.simThread.getAllClients()
            for chairName, clientID in dictClients.items():
                if self.restaurantObjects.isChair(chairName):
                    tableNumber = int(chairName.split("t")[-1])
                    initialisation.append(
                        "isattable(c{}, table{})".format(clientID, tableNumber)
                    )

            self.aspThread.writeInitSituation(initialisation)
        else:
            self.aspThread.resetAll()
        self.aspThread.setState(state)

    @pyqtSlot(int)
    def tableCallBill(self, tableNumber: int):
        self.centralWidget.newLog_signal.emit(
            "Table " + str(tableNumber) + " call for the bill.",
            'info'
        )

        clientsAtTable = self.simThread.getClientsAtTable(tableNumber)
        self.aspThread.newObservation_signal.emit(
            "bill_wave(table{})".format(tableNumber), True
        )
        for clientID in clientsAtTable:
            self.aspThread.newGoal_signal.emit("haspaid(c{})".format(clientID))

    def clientEnter(self):
        self.centralWidget.newLog_signal.emit("Client entered restaurant.", 'info')
        client_IDs = []
        for i in range(self.centralWidget.simulationControler.getNbrNewClients()):
            pos_name = self.restaurantGraph.getEntrancePosition() + '_{}'.format(i)
            client_IDs.append(self.addClient(pos_name))
            self.aspThread.newGoal_signal.emit("isattable(c{}, T)".format(client_IDs[i]))
            self.aspThread.newObservation_signal.emit(
                "has_entered(c{})".format(client_IDs[i]), True
            )
            if i > 0:
                self.aspThread.newObservation_signal.emit(
                    "group(c{}, c{})".format(client_IDs[i-1], client_IDs[i]), True
                )
        self.simThread.group_clients.append(client_IDs)

    @pyqtSlot(str)
    def addClient(self, name):
        if self.restaurantObjects.isChair(name):
            clientID = self.simThread.addSeatedClient(
                str(self.simThread.dataPath / "alfred" / "seated" / "alfred.obj"), name
            )
        elif self.restaurantGraph.isPosition(name):
            # clientID = self.simThread.addStandingClient(str(self.simThread.dataPath / 'alfred' / 'stand' / 'alfred.obj'),name, self.centralWidget.simulationControler.getDialOrientation())
            clientID = self.simThread.addStandingClient(
                str(self.simThread.dataPath / "alfred" / "stand" / "alfred.obj"),
                name,
                0,
            )
        return clientID

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
