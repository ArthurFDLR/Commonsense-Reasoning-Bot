import pybullet as p
import pybullet_data
from qibullet import PepperVirtual
import numpy as np
import time
from SpatialGraph import SpatialGraph, GraphPlotWidget, MyScene, ObjectSet
from Util import printHeadLine, SwitchButton, euler_to_quaternion
import cv2

from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, Qt
from PyQt5 import QtWidgets as Qtw
from PyQt5.QtGui import QImage, QPixmap


class MyBot(PepperVirtual):
    def __init__(self, physicsClientID, sceneGraph:SpatialGraph):
        super().__init__()
        self.goalPosition = sceneGraph.getStartingPosition()
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
                    self.moveTo(pos[0],pos[1],pos[2], _async=True, frame=self.FRAME_WORLD, speed=4.0)

    def isInPosition(self, x,y, delta = 0.01):
        xP, yP, tP = self.getPosition()
        return (xP-x)**2 + (yP-y)**2 < delta**2
    
    def isInPosition(self, namePosition:str, delta = 0.01):
        xP, yP, tP = self.getPosition()
        pos = self.sceneGraph.getCoordinate(namePosition)
        return (xP-pos[0])**2 + (yP-pos[1])**2 < delta**2

    def moveToPosition(self, positionName:str):
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
    def __init__(self, graph:SpatialGraph):
        super().__init__()

        ## SIMULATION INITIALISATION ##
        ###############################
        self.running = False
        physicsClientID = p.connect(p.GUI)
        p.setGravity(0, 0, -10)

        p.setAdditionalSearchPath(r".\Data")
        p.configureDebugVisualizer(p.COV_ENABLE_GUI,0)

        sceneName = 'Restaurant_Large'
        worldID = p.loadSDF(sceneName + '.sdf' , globalScaling=1.0)

        self.addSeatedClient('.\\alfred\\seated\\alfred.obj', 0.75, .0, -0.3, .0, rotationOffset=.15)
        self.addSeatedClient('.\\alfred\\seated\\alfred.obj', -0.75,.0, -0.3, np.pi, rotationOffset=.15)
        self.addSeatedClient('.\\alfred\\stand\\alfred.obj', -1.9, -2.0, .0, -np.pi/1.8, rotationOffset=.15)

        self.turtleID = p.loadURDF("turtlebot.urdf",[-2,1,0])

        graphResLarge = graph
        graphResLarge.generateASP(sceneName)

        self.pepper = MyBot(physicsClientID, graphResLarge)
        p.setRealTimeSimulation(1)

        self.forward=0
        self.turn=0
        printHeadLine('Simulation environment ready',False)

        self.emissionFPS = 24.0
        self.lastTime = time.time()


    def addSeatedClient(self, url:str, x:float, y:float, z:float, theta:float, rotationOffset:float=.0):
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

    @pyqtSlot(bool)
    def setState(self, b:bool):
        print('Simulator ' + 'started' if b else 'stopped')
        self.running = b
    
    @pyqtSlot(str)
    def pepperGoTo(self, position:str):
        self.pepper.moveToPosition(position)

    def run(self):
        while True:
            ## PEPPER VIEW EMITION ##
            #########################
            if time.time() - self.lastTime > 1.0/self.emissionFPS:
                self.lastTime = time.time()

                frameOutput = self.pepper.getLastFrame()
                rgbImage = cv2.cvtColor(frameOutput, cv2.COLOR_BGR2RGB)
                h, w, ch = rgbImage.shape
                bytesPerLine = ch * w
                convertToQtFormat = QImage(rgbImage.data, w, h, bytesPerLine, QImage.Format_RGB888)
                pixmapPepper = convertToQtFormat.scaled(480, 480, Qt.KeepAspectRatio)
                self.newPixmapPepper.emit(pixmapPepper)

            ## SIMULATION LOOP ##
            #####################
            if self.running:

                p.setGravity(0, 0, -10)
                #sleep(1./240.)
                self.pepper.update()

                # Turtle movements
                keys = p.getKeyboardEvents()
                leftWheelVelocity=0
                rightWheelVelocity=0
                speed=10
                for k,v in keys.items():
                    if (k == p.B3G_RIGHT_ARROW and (v&p.KEY_WAS_TRIGGERED)):
                        self.turn = -0.5
                    if (k == p.B3G_RIGHT_ARROW and (v&p.KEY_WAS_RELEASED)):
                        self.turn = 0
                    if (k == p.B3G_LEFT_ARROW and (v&p.KEY_WAS_TRIGGERED)):
                        self.turn = 0.5
                    if (k == p.B3G_LEFT_ARROW and (v&p.KEY_WAS_RELEASED)):
                        self.turn = 0

                    if (k == p.B3G_UP_ARROW and (v&p.KEY_WAS_TRIGGERED)):
                        self.forward=1
                    if (k == p.B3G_UP_ARROW and (v&p.KEY_WAS_RELEASED)):
                        self.forward=0
                    if (k == p.B3G_DOWN_ARROW and (v&p.KEY_WAS_TRIGGERED)):
                        self.forward=-1
                    if (k == p.B3G_DOWN_ARROW and (v&p.KEY_WAS_RELEASED)):
                        self.forward=0
                
                rightWheelVelocity+= (self.forward+self.turn)*speed
                leftWheelVelocity += (self.forward-self.turn)*speed
                p.setJointMotorControl2(self.turtleID,0,p.VELOCITY_CONTROL,targetVelocity=leftWheelVelocity,force=1000)
                p.setJointMotorControl2(self.turtleID,1,p.VELOCITY_CONTROL,targetVelocity=rightWheelVelocity,force=1000)
        

class SimulationControler(Qtw.QGroupBox):
    newOrderPepper_Position = pyqtSignal(str)
    newOrderPepper_HeadPitch = pyqtSignal(float)

    def __init__(self, graph:SpatialGraph, objects:ObjectSet):
        super().__init__('Pepper control')

        self.layout=Qtw.QGridLayout(self)
        self.setLayout(self.layout)

        self.graphPlotWidget = GraphPlotWidget(graph, objects)
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
    
    @pyqtSlot(str)
    def itemClicked(self, position:str):
        print(position)


if __name__ == "__main__":
    from PyQt5.QtCore import QCoreApplication
    import sys

    app = QCoreApplication([])
    exampleGraph, exampleObjects = MyScene()
    thread = SimulationThread(exampleGraph)
    thread.finished.connect(app.exit)
    thread.start()
    thread.setState(True)

    sys.exit(app.exec_())
    