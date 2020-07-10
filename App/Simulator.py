import pybullet as p
import pybullet_data
from qibullet import PepperVirtual
import numpy as np
from time import sleep
from SpatialGraph import SpatialGraph, GraphPlotWidget, MyGraph
from Util import printHeadLine
import cv2

from PyQt5.QtCore import QThread, pyqtSlot, Qt
from PyQt5 import QtWidgets as Qtw


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

    def __init__(self, graph:SpatialGraph):
        super().__init__()

        ## SIMULATION INITIALISATION ##
        ###############################
        self.running = True
        physicsClientID = p.connect(p.GUI)
        p.setGravity(0, 0, -10)

        p.setAdditionalSearchPath(r".\Data")
        p.configureDebugVisualizer(p.COV_ENABLE_GUI,0)

        sceneName = 'Restaurant_Large'
        worldID = p.loadSDF(sceneName + '.sdf' , globalScaling=1.0)
        self.turtleID = p.loadURDF("turtlebot.urdf",[-2,1,0])

        graphResLarge = graph
        graphResLarge.generateASP(sceneName)

        self.pepper = MyBot(physicsClientID, graphResLarge)
        p.setRealTimeSimulation(1)

        self.forward=0
        self.turn=0
        printHeadLine('Simulation environment ready',False)
    
    def stop(self):
        self.running = False
    
    @pyqtSlot(str)
    def pepperGoTo(self, position:str):
        self.pepper.moveToPosition(position)

    def run(self):
        while self.running:
            ## SIMULATION LOOP ##
            #####################

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
    def __init__(self, graph:SpatialGraph):
        super().__init__('Pepper control')

        self.layout=Qtw.QHBoxLayout(self)
        self.setLayout(self.layout)

        self.graphPlotWidget = GraphPlotWidget(graph)
        self.layout.addWidget(self.graphPlotWidget)

        screenHeight = Qtw.QDesktopWidget().screenGeometry().height()
        graphSize = screenHeight/2.0
        self.graphPlotWidget.setFixedSize(graphSize, graphSize)
        self.graphPlotWidget.positionClicked.connect(self.itemClicked)
    
    @pyqtSlot(str)
    def itemClicked(self, position:str):
        print(position)


if __name__ == "__main__":
    from PyQt5.QtCore import QCoreApplication
    import sys

    app = QCoreApplication([])
    thread = SimulationThread(MyGraph)
    thread.finished.connect(app.exit)
    thread.start()
    sys.exit(app.exec_())
    