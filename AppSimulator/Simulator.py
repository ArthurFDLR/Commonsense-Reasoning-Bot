import pybullet as p
import pybullet_data
from qibullet import PepperVirtual
import numpy as np
import time
from SpatialGraph import SpatialGraph, GraphPlotWidget, MyScene, ObjectSet
from Util import printHeadLine, SwitchButton, euler_to_quaternion
from ASP.CommunicationASP import CommunicationAspThread
import cv2

from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, Qt
from PyQt5 import QtWidgets as Qtw
from PyQt5.QtGui import QImage, QPixmap


class MyBot(PepperVirtual):
    def __init__(self, physicsClientID, sceneGraph:SpatialGraph):
        super().__init__()
        self.goalPosition = sceneGraph.getStartingPosition()
        self.goalOrientation = 0.0
        self.pathToGoalPosition = []
        self.sceneGraph = sceneGraph
        self.loadRobot(translation=sceneGraph.getCoordinate(self.goalPosition), quaternion=[0, 0, 0, 1], physicsClientId=physicsClientID)
        self.showLaser(True)
        self.subscribeLaser()
        self.goToPosture("Stand",0.8)
        self.camBottomHandle = self.subscribeCamera(PepperVirtual.ID_CAMERA_TOP)
        #print('Available joints ',end='')
        #print(self.joint_dict.items())
        self.setHeadPosition(yaw=.0, pitch=.0)

    def update(self):
        ## Positioning 
        if len(self.pathToGoalPosition)>0:
            if self.isInPosition(self.pathToGoalPosition[0], delta=0.3): #If we have reached next position in queue
                self.pathToGoalPosition = self.pathToGoalPosition[1:]
                if len(self.pathToGoalPosition)>0:
                    pos = self.sceneGraph.getCoordinate(self.pathToGoalPosition[0])
                    print('Moving to ' + self.pathToGoalPosition[0] +' '+ str(pos))
                    self.moveTo(pos[0],pos[1],pos[2] if not self.goalOrientation else self.goalOrientation, _async=True, frame=self.FRAME_WORLD, speed=4.0)

    def isInPosition(self, x,y, delta = 0.01):
        xP, yP, tP = self.getPosition()
        return (xP-x)**2 + (yP-y)**2 < delta**2
    
    def isInPosition(self, namePosition:str, delta = 0.01):
        xP, yP, tP = self.getPosition()
        pos = self.sceneGraph.getCoordinate(namePosition)
        return (xP-pos[0])**2 + (yP-pos[1])**2 < delta**2

    def moveToPosition(self, positionName:str, orientation:float=None):
        self.goalOrientation = orientation
        if self.sceneGraph.isPosition(positionName):
            self.pathToGoalPosition = self.sceneGraph.findShortestPath(self.goalPosition, positionName)
            print('Path: ' + str(self.pathToGoalPosition))
            self.goalPosition = positionName
        else:
            print(positionName + ': Unknown position.')
    
    def setHeadPosition(self, yaw:float=None, pitch:float=None):
        ''' angles in radiant '''
        if yaw:
            self.setAngles('HeadYaw', yaw, 1.0)
        if pitch:
            self.setAngles('HeadPitch', pitch, 1.0)
    
    def getLastFrame(self):
        return self.getCameraFrame(self.camBottomHandle)



class SimulationThread(QThread):
    newPixmapPepper = pyqtSignal(QImage)
    newPositionPepper_signal = pyqtSignal(float,float,float) #x,y,theta
    def __init__(self, aspThread:CommunicationAspThread ,graph:SpatialGraph, objects:ObjectSet):
        super().__init__()

        sceneName = 'Restaurant_Large'
        self.aspThread = aspThread
        self.objects = objects
        self.graph = graph
        self.graph.generateASP(sceneName)
        self.emissionFPS = 24.0
        self.lastTime = time.time()

        self.standingClients = {}

        ## SIMULATION INITIALISATION ##
        ###############################
        self.running = False
        self.emitPepperCam = False
        physicsClientID = p.connect(p.GUI)
        p.setGravity(0, 0, -10)

        p.setAdditionalSearchPath(r".\Data")
        #p.configureDebugVisualizer(p.COV_ENABLE_GUI,0)

        worldID = p.loadSDF(sceneName + '.sdf' , globalScaling=1.0)

        self.pepper = MyBot(physicsClientID, self.graph)
        p.setRealTimeSimulation(1)

        printHeadLine('Simulation environment ready',False)



    def addClient(self, url:str, x:float, y:float, z:float, theta:float, rotationOffset:float=.0):
        scale = [0.165]*3
        visShapeId = p.createVisualShape(shapeType=p.GEOM_MESH,
                                         fileName=url,
                                         meshScale=scale,
                                         specularColor=[0.0, .0, 0])
        colShapeId = p.createCollisionShape(shapeType=p.GEOM_MESH,
                                            fileName=url,
                                            meshScale=scale)
        bodyId = p.createMultiBody(baseMass=.0, baseInertialFramePosition=[0, 0, 0],
                                   baseCollisionShapeIndex=colShapeId, baseVisualShapeIndex=visShapeId,
                                   basePosition=[x+rotationOffset*np.cos(theta),y,z], baseOrientation=euler_to_quaternion(.0,.0, theta))
        return bodyId
    
    @pyqtSlot(str,str)
    def addSeatedClient(self, url:str, chairName:str):
        if self.objects.isChair(chairName):
            x, y, theta = self.objects.getCoordinate(chairName)
            if self.objects.isOccupied(chairName):
                self.removeSeatedClient(chairName) 
            newID = self.addClient(url, x, y, -.3, theta, .15)
            print(newID)
            self.objects.setChairClientID(newID,chairName)
            return newID
        else:
            return None
    
    @pyqtSlot(str)
    def removeSeatedClient(self, chairName:str):
        if self.objects.isChair(chairName):
            objectId = self.objects.getChairClientID(chairName)
            p.removeBody(objectId)
            self.objects.setChairClientID(None, chairName)
            return True
        else:
            return False
    
    @pyqtSlot(str,str, float)
    def addStandingClient(self, url:str, positionName:str, orientation:float=.0):
        if self.graph.isPosition(positionName):
            x, y, theta = self.graph.getCoordinate(positionName)
            if positionName in self.standingClients.keys():
                self.removeStandingClient(positionName) 
            objectId = self.addClient(url, x, y, .0, orientation, .0)
            self.standingClients[positionName] = objectId
            return objectId
        else:
            return None
    
    @pyqtSlot(str)
    def removeStandingClient(self, positionName:str):
        if self.graph.isPosition(positionName) and positionName in self.standingClients.keys():
            objectId = self.standingClients[positionName]
            p.removeBody(objectId)
            del self.standingClients[positionName]
            return True
        else:
            return False

    @pyqtSlot(bool)
    def setState(self, b:bool):
        print('Simulator ' + 'started' if b else 'stopped')
        self.running = b
    
    @pyqtSlot(str, float)
    def pepperGoTo(self, position:str, orientation:float=None):
        self.pepper.moveToPosition(position, orientation)

    def run(self):
        while True:
            ## PEPPER VIEW EMISSION ##
            #########################
            if self.emitPepperCam and time.time() - self.lastTime > 1.0/1.0:
                self.lastTime = time.time()

                frameOutput = self.pepper.getLastFrame()
                rgbImage = cv2.cvtColor(frameOutput, cv2.COLOR_BGR2RGB)
                h, w, ch = rgbImage.shape
                bytesPerLine = ch * w
                convertToQtFormat = QImage(rgbImage.data, w, h, bytesPerLine, QImage.Format_RGB888)
                pixmapPepper = convertToQtFormat.scaled(640, 640, Qt.KeepAspectRatio)
                self.newPixmapPepper.emit(pixmapPepper)

            ## SIMULATION LOOP ##
            #####################
            if self.running:

                p.setGravity(0, 0, -10)
                #sleep(1./240.)
                self.pepper.update()
                x,y,theta = self.pepper.getPosition()
                #self.newPositionPepper_signal.emit(x,y,theta)
                
                self.pepperOrdersManager()
            
    def pepperOrdersManager(self):
        currentOrder = self.aspThread.getCurrentOrder()
        if currentOrder:
            orderSplit = currentOrder[:-1].replace('(', ',').split(',')
            order = orderSplit[0]
            orderParams = orderSplit[1:]

            if order == 'go_to':
                position = orderParams[1]
                if self.pepper.isInPosition(position):
                    self.aspThread.currentOrderCompleted()
                else:
                    self.pepperGoTo(position)
            
            if order == 'seat_customer':
                print(order + ': ' + str(orderParams[1:]))
                self.aspThread.currentOrderCompleted()
    

class SimulationControler(Qtw.QGroupBox):
    newOrderPepper_Position = pyqtSignal(str, float)
    newOrderPepper_HeadPitch = pyqtSignal(float)
    addClient_signal = pyqtSignal(str)
    removeClient_signal = pyqtSignal(str)

    def __init__(self, graph:SpatialGraph, objects:ObjectSet, newObservation_signal:pyqtSignal):
        super().__init__('Simulator control')

        self.layout=Qtw.QGridLayout(self)
        self.setLayout(self.layout)

        self.graphPlotWidget = GraphPlotWidget(graph, objects, self.addClient_signal, self.removeClient_signal, self.newOrderPepper_Position, newObservation_signal)
        screenHeight = Qtw.QDesktopWidget().screenGeometry().height()
        graphSize = screenHeight/2.0
        self.graphPlotWidget.setFixedSize(graphSize, graphSize)
        self.graphPlotWidget.positionClicked.connect(self.itemClicked)
        self.layout.addWidget(self.graphPlotWidget,0,1,2,1)

        self.simButton = SwitchButton(self)
        self.layout.addWidget(self.simButton, 0, 0)

        self.sld = Qtw.QSlider(Qt.Vertical, self)
        self.sld.setRange(-(np.pi/4.0)*10, (np.pi/4.0)*10)
        self.sld.valueChanged.connect(lambda p: self.newOrderPepper_HeadPitch.emit(p/10))
        self.layout.addWidget(self.sld,1,0)

        self.dial = Qtw.QDial()
        self.dial.setMinimum(0)
        self.dial.setMaximum(20)
        self.dial.setValue(0)
        self.dial.valueChanged.connect(lambda: print(str(self.dial.value()) + ' ' + str(self.getDialOrientation())))
        self.layout.addWidget(self.dial, 2,0)


    
    @pyqtSlot(str)
    def itemClicked(self, position:str):
        print(position)
    
    def getDialOrientation(self):
        dialValue = self.dial.value()
        return ((dialValue/20.0) * (2.0*np.pi)) - (np.pi/2.0)


if __name__ == "__main__":
    from PyQt5.QtCore import QCoreApplication
    import sys

    app = QCoreApplication([])
    exampleGraph, exampleObjects = MyScene()
    thread = SimulationThread(exampleGraph, exampleObjects)
    thread.finished.connect(app.exit)
    thread.start()
    thread.setState(True)
    thread.pepperGoTo('d', -(7.0*np.pi)/4.0)

    sys.exit(app.exec_())
    