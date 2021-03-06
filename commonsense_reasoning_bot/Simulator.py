import pybullet as p
import pybullet_data
from qibullet import PepperVirtual
import numpy as np
import time
import pathlib


from SpatialGraph import SpatialGraph, GraphPlotWidget, MyScene, ObjectSet
from Util import printHeadLine, SwitchButton, euler_to_quaternion
from ASP.CommunicationASP import CommunicationAspThread

from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, Qt
from PyQt5 import QtWidgets as Qtw
from PyQt5.QtGui import QImage, QPixmap

Stylesheet = """
QLineEdit, QLabel, QTabWidget {
    font-family: -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Oxygen,Ubuntu,Cantarell,Fira Sans,Droid Sans,Helvetica Neue,sans-serif;
}
#Control_panel {
    background-color: white;
    border-radius: 3px;
}
"""

class MyBot(PepperVirtual):
    def __init__(self, physicsClientID, sceneGraph: SpatialGraph):
        super().__init__()
        self.goalPosition = sceneGraph.getStartingPosition()
        self.goalOrientation = 0.0
        self.pathToGoalPosition = []
        self.sceneGraph = sceneGraph
        self.loadRobot(
            translation=sceneGraph.getCoordinate(self.goalPosition),
            quaternion=[0, 0, 0, 1],
            physicsClientId=physicsClientID,
        )
        self.showLaser(True)
        self.subscribeLaser()
        self.goToPosture("Stand", 0.8)
        self.camBottomHandle = self.subscribeCamera(PepperVirtual.ID_CAMERA_TOP)
        # print('Available joints ',end='')
        # print(self.joint_dict.items())
        self.setHeadPosition(yaw=0.0, pitch=0.0)

    def update(self):
        ## Positioning
        if len(self.pathToGoalPosition) > 0:
            # If we have reached next position in queue
            if self.isInPosition(self.pathToGoalPosition[0], delta=0.3):
                self.pathToGoalPosition = self.pathToGoalPosition[1:]
                if len(self.pathToGoalPosition) > 0:
                    pos = self.sceneGraph.getCoordinate(self.pathToGoalPosition[0])
                    print("Moving to " + self.pathToGoalPosition[0] + " " + str(pos))
                    self.moveTo(
                        pos[0],
                        pos[1],
                        pos[2] if not self.goalOrientation else self.goalOrientation,
                        _async=True,
                        frame=self.FRAME_WORLD,
                        speed=4.0,
                    )

    def isInPosition(self, x, y, delta=0.01):
        xP, yP, tP = self.getPosition()
        return (xP - x) ** 2 + (yP - y) ** 2 < delta ** 2

    def isInPosition(self, namePosition: str, delta=0.01):
        xP, yP, tP = self.getPosition()
        pos = self.sceneGraph.getCoordinate(namePosition)
        return (xP - pos[0]) ** 2 + (yP - pos[1]) ** 2 < delta ** 2

    def moveToPosition(self, positionName: str, orientation: float = None):
        self.goalOrientation = orientation
        if self.sceneGraph.isPosition(positionName):
            self.pathToGoalPosition = self.sceneGraph.findShortestPath(
                self.goalPosition, positionName
            )
            self.goalPosition = positionName
        else:
            print(positionName + ": Unknown position.")

    def setHeadPosition(self, yaw: float = None, pitch: float = None):
        """ angles in radiant """
        if yaw:
            self.setAngles("HeadYaw", yaw, 1.0)
        if pitch:
            self.setAngles("HeadPitch", pitch, 1.0)

    def getLastFrame(self):
        return self.getCameraFrame(self.camBottomHandle)

    def getGoalPosition(self) -> str:
        return self.goalPosition


class SimulationThread(QThread):
    newPixmapPepper = pyqtSignal(QImage)
    newPositionPepper_signal = pyqtSignal(float, float, float)  # x,y,theta

    def __init__(
        self,
        aspThread: CommunicationAspThread,
        graph: SpatialGraph,
        objects: ObjectSet,
        logOutput_signal: pyqtSignal,
    ):
        super().__init__()

        sceneName = "Restaurant_Large"
        self.dataPath = pathlib.Path(__file__).parent.absolute() / "Data"
        self.aspThread = aspThread
        self.logOutput_signal = logOutput_signal
        self.objects = objects
        self.graph = graph
        self.graph.generateASP(self.dataPath / "{}.sparc".format(sceneName))
        self.emissionFPS = 24.0
        self.lastTime = time.time()

        self.standingClients = {}

        ## ORDERS MANAGING ##
        #####################
        self.currentOrder = None
        self.orderCompleted = True
        self.currentOrderStr = ""
        # Stores client ID number according to ASP program
        self.clientIDs = {}
        # List of list of ID of client in a same group
        self.group_clients = []
        # Stores client ID number which have been picked by Pepper
        self.clientIDWithPepper = []
        self.clientCounter = 0

        ## SIMULATION INITIALISATION ##
        ###############################
        self.running = False
        # self.emitPepperCam = False
        physicsClientID = p.connect(p.GUI)
        p.setGravity(0, 0, -10)

        p.setAdditionalSearchPath(str(self.dataPath))
        p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)

        worldID = p.loadSDF(sceneName + ".sdf", globalScaling=1.0)

        self.pepper = MyBot(physicsClientID, self.graph)
        p.setRealTimeSimulation(1)

        self.logOutput_signal.emit("Simulation environment ready", 'info')
        printHeadLine("Simulation environment ready", False)

    def addClient(
        self,
        url: str,
        x: float,
        y: float,
        z: float,
        theta: float,
        rotationOffset: float = 0.0,
        newClient: bool = True,
    ):
        if newClient:
            self.clientCounter += 1

        scale = [0.165] * 3
        visShapeId = p.createVisualShape(
            shapeType=p.GEOM_MESH,
            fileName=url,
            meshScale=scale,
            specularColor=[0.0, 0.0, 0],
        )
        colShapeId = p.createCollisionShape(
            shapeType=p.GEOM_MESH, fileName=url, meshScale=scale
        )
        bodyId = p.createMultiBody(
            baseMass=0.0,
            baseInertialFramePosition=[0, 0, 0],
            baseCollisionShapeIndex=colShapeId,
            baseVisualShapeIndex=visShapeId,
            basePosition=[x + rotationOffset * np.cos(theta), y, z],
            baseOrientation=euler_to_quaternion(0.0, 0.0, theta),
        )

        return bodyId

    def getClientsAtTable(self, tableNumber: int):
        clients = []
        for chairName, clientID in self.clientIDs.items():
            if "t{}".format(tableNumber) in chairName:
                clients.append(clientID)
        return clients

    def getAllClients(self):
        """Returns identification numbers and positions of all clients in the scene.

        Returns:
            {str:int}: Dictionnary, with chair name as key and identification number as value.
        """
        return self.clientIDs

    @pyqtSlot(str, str)
    def addSeatedClient(self, url: str, chairName: str):
        if self.objects.isChair(chairName):
            x, y, theta = self.objects.getCoordinate(chairName)

            if self.objects.isOccupied(chairName):
                self.removeSeatedClient(chairName)

            newID = self.addClient(url, x, y, -0.3, theta, 0.15)
            self.clientIDs[chairName] = self.clientCounter
            self.objects.setChairClientID(newID, chairName)

            return self.clientIDs[chairName]
        else:
            return None

    @pyqtSlot(str)
    def removeSeatedClient(self, chairName: str):
        if self.objects.isChair(chairName):
            objectId = self.objects.getChairClientID(chairName)
            p.removeBody(objectId)
            self.objects.setChairClientID(None, chairName)
            del self.clientIDs[chairName]

            return True
        else:
            return False

    @pyqtSlot(str, str, float)
    def addStandingClient(self, url: str, positionName: str, orientation: float = None):
        if self.graph.isPosition(positionName):
            x, y, theta = self.graph.getCoordinate(positionName)
            if not orientation:
                orientation = theta
            if positionName in self.standingClients.keys():
                self.removeStandingClient(positionName)
            objectId = self.addClient(url, x, y, 0.0, orientation, 0.0)
            self.clientIDs[positionName] = self.clientCounter
            self.standingClients[positionName] = objectId
            return self.clientIDs[positionName]
        else:
            return None

    @pyqtSlot(str)
    def removeStandingClient(self, positionName: str):
        if (
            self.graph.isPosition(positionName)
            and positionName in self.standingClients.keys()
        ):
            objectId = self.standingClients[positionName]
            p.removeBody(objectId)
            del self.standingClients[positionName]
            del self.clientIDs[positionName]
            return True
        else:
            return False

    @pyqtSlot(bool)
    def setState(self, b: bool):
        self.logOutput_signal.emit("Simulator " + "started" if b else "stopped", 'info')
        self.running = b

    @pyqtSlot(str, float)
    def pepperGoTo(self, position: str, orientation: float = None):
        self.pepper.moveToPosition(position, orientation)

    def run(self):
        while True:
            if self.running:

                p.setGravity(0, 0, -10)
                self.pepper.update()
                x, y, theta = self.pepper.getPosition()
                # self.newPositionPepper_signal.emit(x,y,theta)

                self.pepperOrdersManager()

    def pepperPickClient(self, clientID: int):
        for group in self.group_clients:
            if clientID in group:
                for client in group:
                    for pos, cId in self.clientIDs.items():
                        if client == cId:
                            pos_del = pos
                            self.clientIDWithPepper.append(client)
                            # Pepper pick a standing client
                            if self.graph.isPosition(pos):
                                self.removeStandingClient(pos)
                            # Pepper pick a seated client
                            if self.objects.isChair(pos):
                                self.removeSeatedClient(pos)
                            break

    def pepperSeatClient(self, clientID: int, idTable: int):
        # If the table exists
        if self.objects.isTable("table" + str(idTable)):
            # If the table is empty
            if len(self.getClientsAtTable(idTable)) == 0:
                for i, cid in enumerate(self.clientIDWithPepper):
                    chairName = "chair" + str(i + 1) + "t" + str(idTable)
                    x, y, theta = self.objects.getCoordinate(chairName)
                    url = self.dataPath / "alfred" / "seated" / "alfred.obj"
                    newID = self.addClient(
                        str(url), x, y, -0.3, theta, 0.15, newClient=False
                    )
                    self.clientIDs[chairName] = cid
                    self.objects.setChairClientID(newID, chairName)
                self.clientIDWithPepper = []

    def pepperOrdersManager(self):
        if not bool(self.currentOrder):
            self.currentOrder = self.aspThread.getCurrentOrder()
            self.orderCompleted = False

        if self.orderCompleted:
            self.logOutput_signal.emit(self.currentOrderStr, 'order')
            self.currentOrder = self.aspThread.currentOrderCompleted()
            self.orderCompleted = False
            #if self.currentOrder:
            #    self.logOutput_signal.emit("New order: " + self.currentOrder, 'order')
            if not self.currentOrder:
                self.logOutput_signal.emit("All actions completed.", 'order_done')

        if self.currentOrder:
            orderSplit = self.currentOrder[:-1].replace("(", ",").split(",")
            order = orderSplit[0]
            orderParams = orderSplit[1:]

            if order == "go_to":
                position = orderParams[1]
                self.currentOrderStr = "Order completed: move to " + position
                if self.pepper.isInPosition(position):
                    self.orderCompleted = True
                else:
                    if self.pepper.getGoalPosition() != position:
                        self.pepperGoTo(position)

            if order == "seat":
                self.currentOrderStr = "Order completed: seat client " + orderParams[1] + " at table " + orderParams[2]
                self.pepperSeatClient(int(orderParams[1][1:]), int(orderParams[2][5:]))
                self.orderCompleted = True

            if order == "give_bill":
                self.currentOrderStr = "Order completed: give bill to " + orderParams[1]
                self.orderCompleted = True

            if order == "pick":
                self.currentOrderStr = "Order completed: pick-up new client " + orderParams[1]
                self.pepperPickClient(int(orderParams[1][1:]))
                self.orderCompleted = True


class SimulationControler(Qtw.QWidget):
    newOrderPepper_Position = pyqtSignal(str, float)
    newOrderPepper_HeadPitch = pyqtSignal(float)
    tableCallBill_signal = pyqtSignal(int)  # Table number as argument
    addClient_signal = pyqtSignal(str)
    removeClient_signal = pyqtSignal(str)
    
    stylesheet = """
    #Control_Panel {
        background-color: white;
        border-radius: 3px;
        font-family: -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Oxygen,Ubuntu,Cantarell,Fira Sans,Droid Sans,Helvetica Neue,sans-serif;
    }

    QPushButton {
    border: 1px solid #cbcbcb;
    border-radius: 2px;
    font-size: 16px;
    background: white;
    }
    QComboBox {
    border: 1px solid #cbcbcb;
    border-radius: 2px;
    font-size: 16px;
    background: white;
    max-width: 50px;
    }
    QPushButton:hover {
        border-color: rgb(139, 173, 228);
    }
    QPushButton:pressed {
        color: #cbcbcb;
    }
    """

    def __init__(
        self, graph: SpatialGraph, objects: ObjectSet, newObservation_signal: pyqtSignal
    ):
        super().__init__() #"Simulator control"
        self.setObjectName('Control_Panel')
        self.layout = Qtw.QGridLayout(self)
        self.setLayout(self.layout)

        self.graphPlotWidget = GraphPlotWidget(
            graph,
            objects,
            self.addClient_signal,
            self.removeClient_signal,
            self.newOrderPepper_Position,
            self.tableCallBill_signal,
        )
        screenHeight = Qtw.QDesktopWidget().screenGeometry().height()
        graphSize = screenHeight / 2.0
        self.graphPlotWidget.setFixedSize(graphSize, graphSize)
        self.graphPlotWidget.positionClicked.connect(self.itemClicked)
        self.layout.addWidget(self.graphPlotWidget, 0, 0, 1, 3)

        self.simButton = SwitchButton(self)
        self.layout.addWidget(self.simButton, 1, 0, 1, 1)

        self.newCustomerButton = Qtw.QPushButton("New customer(s)")
        self.layout.addWidget(self.newCustomerButton, 1, 2)

        self.num_customers_cb = Qtw.QComboBox()
        self.num_customers_cb.addItems([str(i+1) for i in range(4)])
        self.layout.addWidget(self.num_customers_cb, 1, 1)

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(self.stylesheet)

        effect = Qtw.QGraphicsDropShadowEffect(self)
        effect.setBlurRadius(10)
        effect.setOffset(0, 0)
        effect.setColor(Qt.gray)
        self.setGraphicsEffect(effect)
    
    def getNbrNewClients(self) -> int:
        return int(self.num_customers_cb.currentText())

    @pyqtSlot(str)
    def itemClicked(self, position: str):
        #self.logOutput_signal.emit(position, 'info')
        print(position)

    def getDialOrientation(self):
        dialValue = self.dial.value()
        return ((dialValue / 20.0) * (2.0 * np.pi)) - (np.pi / 2.0)


if __name__ == "__main__":
    from PyQt5.QtCore import QCoreApplication
    import sys

    app = QCoreApplication([])
    exampleGraph, exampleObjects = MyScene()
    thread = SimulationThread(exampleGraph, exampleObjects)
    thread.finished.connect(app.exit)
    thread.start()
    thread.setState(True)
    thread.pepperGoTo("d", -(7.0 * np.pi) / 4.0)

    sys.exit(app.exec_())
