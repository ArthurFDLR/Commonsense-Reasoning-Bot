import matplotlib.pyplot as plt
import os
import sys
import numpy as np
from enum import Enum
from PyQt5 import QtGui
from PyQt5 import QtWidgets as Qtw
from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt, QRectF, QPoint
from pyqtgraph import PlotWidget, plot
import pyqtgraph as pg

## CORE ##
##########

class FurnitureType(Enum):
    Null = 0
    Chair = 1
    Table = 2

class Furniture():
    def __init__(self, heigth:float = 1.0, width:float = 1.0, x:float = 0.0, y:float = 0.0, objType:FurnitureType = FurnitureType.Null):
        self.heigth = heigth
        self.width = width
        self.x = x
        self.y = y
        self.type = objType


class ObjectSet():
    def __init__(self):
        self._objects = {}
    
    def addObject(self, name:str, x:float, y:float, heigth:float, width:float, objType:FurnitureType = None):
        if not self.isObject(name):
            self._objects[name] = Furniture(heigth=heigth, width=width, x=x, y=y, objType=objType)
            return True
        else:
            return False
    
    def isObject(self, name:str) -> bool:
        return name in self._objects.keys()
    
    def getObjects(self, objType:FurnitureType = None):
        if not objType:
            return self._objects.keys()
        else:
            out = []
            for o in self._objects.keys():
                if self._objects[o].type == objType:
                    out.append(o)
            return out
    
    def getCoordinate(self,name:str):
        if self.isObject(name):
            return [self._objects[name].x, self._objects[name].y]
        else:
            return [0.0, 0.0]

class SpatialGraph():
    def __init__(self, directed:bool=True):
        self.directed = directed
        self._graph = {}
        self._nodePositions = {}
        self.startingPosition = None

    # function to find the shortest path 
    def findShortestPath(self, start:str, end:str, path =[]): 
        path = path + [start] 
        if start == end: 
            return path 
        shortest = None
        for node in self._graph[start]: 
            if node not in path: 
                newpath = self.findShortestPath(node, end, path) 
                if newpath: 
                    if not shortest or len(newpath) < len(shortest): 
                        shortest = newpath 
        return shortest

    def getStartingPosition(self):
        return self.startingPosition
    
    def setStartingPosition(self, name:str):
        if self.isPosition(name):
            self.startingPosition = name
            return True
        else:
            return False

    def isPosition(self, name:str) -> bool:
        return name in self._graph.keys()
    
    def addPosition(self, name:str, x:float, y:float, theta:float):
        if not self.isPosition(name):
            self._graph[name] = []
            self._nodePositions[name] = [x,y,theta]
            if len(self._graph) == 0:
                self.startingPosition = name
            return True
        else:
            return False
    
    def addEdge(self, fromPos:str, toPos:str):
        if self.isPosition(fromPos) and self.isPosition(toPos):
            self._graph[fromPos].append(toPos)
            if not self.directed:
                self._graph[toPos].append(fromPos)
            return True
        else:
            return False
    
    def getCoordinate(self,name:str):
        if self.isPosition(name):
            return self._nodePositions[name]
        else:
            return [0.0, 0.0, 0.0]
    
    def showPlotGraph(self):
        for node in self._nodePositions.keys():
            posStart = self._nodePositions[node]
            plt.plot(posStart[0], posStart[1], marker='o', color='black')
            plt.annotate(node, # this is the text
                 (posStart[0],posStart[1]), # this is the point to label
                 textcoords="offset points", # how to position the text
                 xytext=(5,10), # distance from text to points (x,y)
                 ha='center') # horizontal alignment can be left, right or center
            for edge in self._graph[node]:
                posGoal = self._nodePositions[edge]
                plt.plot([posStart[0], posGoal[0]], [posStart[1], posGoal[1]], 'k-')

        plt.show()
    
    def getEdges(self):
        output = []
        for node in self._nodePositions.keys():
            posStart = self._nodePositions[node]
            for edge in self._graph[node]:
                posGoal = self._nodePositions[edge]
                output.append(([posStart[0], posGoal[0]], [posStart[1], posGoal[1]]))
                #plt.plot([posStart[0], posGoal[0]], [posStart[1], posGoal[1]], 'k-')
        return output
    
    def getNodes(self):
        return self._nodePositions.keys()

    def generateASP(self, sceneName:str='default'):
        relativeUrlFile = '.\\Data\\' + sceneName + '.sparc'
        fileAsp = open(relativeUrlFile,'w')
        
        vertexStr = '#vertex = {'
        nbrVertex = len(self._nodePositions)
        edgeSTR = ''

        for counterNode, node in enumerate(self._nodePositions.keys()):
            vertexStr += node
            vertexStr += '}' if counterNode==nbrVertex-1 else ','

            nbrEdge = len(self._graph[node])
            for counterEdge, edge in enumerate(self._graph[node]):
                edgeSTR += 'edge({},{}).'.format(node, edge)
                edgeSTR += '\n' if counterEdge==nbrEdge-1 else '  '
        
        fileAsp.write("%% Graph generated by the RoboticVisionSimulator during {} scene launching.\n\n".format(sceneName))
        fileAsp.write(vertexStr + '\n\n')
        fileAsp.write(edgeSTR)
        fileAsp.close()

        print('ASP graph generated:  ' + os.getcwd() + '\\' + relativeUrlFile)

def MyScene(showGraph:bool=False) -> SpatialGraph:
    graph = SpatialGraph(directed=False)
    graph.addPosition('a', -4.7, -1.75, 0.0)
    graph.addPosition('b', -4.7, 0.15,   0.0)
    graph.addPosition('c', -3.8, 0.875, 0.0)
    graph.addPosition('d', -1.9, 0.875, 0.0)
    graph.addPosition('e', -1.9, -1.75, 0.0)
    graph.addPosition('f', 0.0,  -1.75, 0.0)
    graph.addPosition('g', 2.5,  -1.75, 0.0)
    graph.addPosition('h', 0.0,  0.875, 0.0)
    graph.addPosition('i', 2.5,  0.875, 0.0)
    graph.addPosition('j', -1.9, 3.5,   0.0)
    graph.addPosition('k', 0.0,  3.5,   0.0)
    graph.addPosition('l', 0.75, 3.5,   0.0)
    graph.addPosition('m', 2.5,  3.5,   0.0)
    graph.addPosition('n', 0.75, 5.0,   0.0)
    graph.addPosition('o', -2.3, 3.6,   0.0)
    graph.addPosition('p', -3.8, 3.6,   0.0)
    graph.addPosition('q', -2.3, 5.1,   0.0)

    graph.setStartingPosition('a')

    graph.addEdge('a','b')
    graph.addEdge('b','c')
    graph.addEdge('c','d')
    for pos in ['e','h','j']:
        graph.addEdge('d',pos)
    graph.addEdge('e','f')
    graph.addEdge('f','g')
    graph.addEdge('h','i')
    graph.addEdge('j','k')
    for pos in ['p','q','j']:
        graph.addEdge('o',pos)
    for pos in ['k','n','m']:
        graph.addEdge('l',pos)
    
    if showGraph:
        graph.showPlotGraph()

    objects = ObjectSet()
    objects.addObject(name='table1',
                      objType = FurnitureType.Table,
                      x = 0.0, y = -2.6,
                      heigth = 0.8, width = 0.8)
    objects.addObject(name='chair1t1',
                      objType = FurnitureType.Chair,
                      x = 0.75, y = -2.6,
                      heigth = 0.6, width = 0.6)
    objects.addObject(name='chair2t1',
                      objType = FurnitureType.Chair,
                      x = -0.75, y = -2.6,
                      heigth = 0.6, width = 0.6)

    objects.addObject(name='table2',
                      objType = FurnitureType.Table,
                      x = 0.0, y = -0.4,
                      heigth = 0.8, width = 1.6)
    objects.addObject(name='chair1t2',
                      objType = FurnitureType.Chair,
                      x = 0.75, y = -0.8,
                      heigth = 0.6, width = 0.6)
    objects.addObject(name='chair2t2',
                      objType = FurnitureType.Chair,
                      x = -0.75, y = -0.8,
                      heigth = 0.6, width = 0.6)
    objects.addObject(name='chair3t2',
                      objType = FurnitureType.Chair,
                      x = 0.75, y = 0.0,
                      heigth = 0.6, width = 0.6)
    objects.addObject(name='chair4t2',
                      objType = FurnitureType.Chair,
                      x = -0.75, y = 0.0,
                      heigth = 0.6, width = 0.6)

    objects.addObject(name='table3',
                      objType = FurnitureType.Table,
                      x = 0.0, y = 2.2,
                      heigth = 0.8, width = 1.6)
    objects.addObject(name='chair1t3',
                      objType = FurnitureType.Chair,
                      x = 0.75, y = 1.72,
                      heigth = 0.6, width = 0.6)
    objects.addObject(name='chair2t3',
                      objType = FurnitureType.Chair,
                      x = -0.75, y = 1.72,
                      heigth = 0.6, width = 0.6)
    objects.addObject(name='chair3t3',
                      objType = FurnitureType.Chair,
                      x = 0.75, y = 2.6,
                      heigth = 0.6, width = 0.6)
    objects.addObject(name='chair4t3',
                      objType = FurnitureType.Chair,
                      x = -0.75, y = 2.6,
                      heigth = 0.6, width = 0.6)
    
    objects.addObject(name='table4',
                      objType = FurnitureType.Table,
                      x = 2.5, y = -2.6,
                      heigth = 0.8, width = 0.8)
    objects.addObject(name='chair1t4',
                      objType = FurnitureType.Chair,
                      x = 3.25, y = -2.6,
                      heigth = 0.6, width = 0.6)
    objects.addObject(name='chair2t4',
                      objType = FurnitureType.Chair,
                      x = 1.75, y = -2.6,
                      heigth = 0.6, width = 0.6)

    objects.addObject(name='table5',
                      objType = FurnitureType.Table,
                      x = 2.5, y = -0.4,
                      heigth = 0.8, width = 1.6)
    objects.addObject(name='chair1t5',
                      objType = FurnitureType.Chair,
                      x = 3.25, y = -0.8,
                      heigth = 0.6, width = 0.6)
    objects.addObject(name='chair2t5',
                      objType = FurnitureType.Chair,
                      x = 1.75, y = -0.8,
                      heigth = 0.6, width = 0.6)
    objects.addObject(name='chair3t5',
                      objType = FurnitureType.Chair,
                      x = 3.25, y = 0.0,
                      heigth = 0.6, width = 0.6)
    objects.addObject(name='chair4t5',
                      objType = FurnitureType.Chair,
                      x = 1.75, y = 0.0,
                      heigth = 0.6, width = 0.6)

    objects.addObject(name='table6',
                      objType = FurnitureType.Table,
                      x = 2.5, y = 2.2,
                      heigth = 0.8, width = 1.6)
    objects.addObject(name='chair1t6',
                      objType = FurnitureType.Chair,
                      x = 3.25, y = 1.72,
                      heigth = 0.6, width = 0.6)
    objects.addObject(name='chair2t6',
                      objType = FurnitureType.Chair,
                      x = 1.75, y = 1.72,
                      heigth = 0.6, width = 0.6)
    objects.addObject(name='chair3t6',
                      objType = FurnitureType.Chair,
                      x = 3.25, y = 2.6,
                      heigth = 0.6, width = 0.6)
    objects.addObject(name='chair4t6',
                      objType = FurnitureType.Chair,
                      x = 1.75, y = 2.6,
                      heigth = 0.6, width = 0.6)

    return graph, objects


## QT GUI ##
############


class ClickablePlotWidget(pg.PlotWidget):
    #newItemClicked = pyqtSignal(float,float)
    def __init__(self, graph:SpatialGraph, objects:ObjectSet, positionClicked:pyqtSignal):
        super(ClickablePlotWidget, self).__init__()
        self.positionClicked = positionClicked
        self.graph = graph
        self.objects = objects

        self.scene().sigMouseClicked.connect(self.mouse_clicked)
        self.setMouseEnabled(False,False)
        
        self.setMenuEnabled(False)
        self.menu = None
        self.menu = self.getMenu()

    def mouse_clicked(self, mouseClickEvent):
        x = mouseClickEvent.pos().x()
        y = mouseClickEvent.pos().y()
        if x%1.0 != 0.0 and y%1.0 != 0.0: #Test if an item is clicked (and not background)
            objectName = self.getNameItemClicked(x,y)
            self.positionClicked.emit(objectName)

            pos  = mouseClickEvent.screenPos()
            self.setMenuTitle(objectName)
            self.menu.popup(QPoint(pos.x(), pos.y()))
    
    def getMenu(self):
        """
        Create the menu
        """
        if self.menu is None:
            self.menu = QtGui.QMenu()

            self.menuTitle = QtGui.QAction(u'Contextual Menu', self.menu)
            self.menuTitle.setEnabled(False)
            self.menu.addAction(self.menuTitle)

            self.menu.addSeparator()

            self.action1 = QtGui.QAction(u'First action', self.menu)
            self.action1.triggered.connect(lambda: print('Action 1'))
            self.action1.setCheckable(False)
            self.action1.setEnabled(True)
            self.menu.addAction(self.action1)

            self.action2 = QtGui.QAction(u'Second action', self.menu)
            self.action2.triggered.connect(lambda: print('Action 2'))
            self.action2.setCheckable(False)
            self.action2.setEnabled(True)
            self.menu.addAction(self.action2)

        return self.menu
    
    def getNameItemClicked(self, x:float, y:float):
        closest = ''
        minDist = sys.float_info.max
        for v in self.graph.getNodes():
            vX, vY, vTheta = self.graph.getCoordinate(v)
            dist = (x - vX)**2 + (y - vY)**2
            if dist < minDist:
                minDist = dist
                closest = v
        for o in self.objects.getObjects():
            oX, oY = self.objects.getCoordinate(o)
            dist = (x - oX)**2 + (y - oY)**2
            if dist < minDist:
                minDist = dist
                closest = o
        return closest
    
    def setMenuTitle(self, name:str):
        self.menuTitle.setText(name)

class GraphPlotWidget(Qtw.QWidget):
    positionClicked = pyqtSignal(str)
    def __init__(self, graph:SpatialGraph, objects:ObjectSet):
        super(GraphPlotWidget, self).__init__()
        self.layout=Qtw.QHBoxLayout(self)
        self.setLayout(self.layout)

        self.graph = graph
        self.objects = objects
        self.graphWidget = ClickablePlotWidget(self.graph, self.objects, self.positionClicked)
        self.layout.addWidget(self.graphWidget)

        self.pen = pg.mkPen(color=(0, 0, 0), width=3, style=Qt.SolidLine)
        self.graphWidget.setBackground('w')
        self.resetPlot()

        #self.graphWidget.newItemClicked.connect(self.itemClicked)

        self.graphWidget.setXRange(-5, 4)
        self.graphWidget.setYRange(-3, 6)
        
    
    def resetPlot(self):
        self.graphWidget.clear()

        for e in self.graph.getEdges(): # Plot edges
            self.graphWidget.plot(e[0], e[1], pen=self.pen)

        for v in self.graph.getNodes(): # Plot nodes
            vPos = self.graph.getCoordinate(v)
            self.graphWidget.plot([vPos[0]], [vPos[1]], symbol='o', symbolSize=15, symbolBrush=('k'))

            text = pg.TextItem(html = '<div style="text-align: center"><span style="color: #191919;font-size:15pt;"><b>%s</b></span></div>'%(v), anchor=(0,1), angle=0, color=(50, 50, 50))
            self.graphWidget.addItem(text)
            text.setPos(vPos[0], vPos[1])

        for o in self.objects.getObjects(FurnitureType.Table): # Plot tables
            oPos = self.objects.getCoordinate(o)
            self.graphWidget.plot([oPos[0]], [oPos[1]], symbol='s', symbolSize=50, symbolBrush=('r'))
        
        for c in self.objects.getObjects(FurnitureType.Chair): # Plot chairs
            cPos = self.objects.getCoordinate(c)
            self.graphWidget.plot([cPos[0]], [cPos[1]], symbol='s', symbolSize=20, symbolBrush=('b'))
    
    @pyqtSlot(float,float)
    def itemClicked(self, x:float, y:float):
        closest = ''
        minDist = sys.float_info.max
        for v in self.graph.getNodes():
            vX, vY, vTheta = self.graph.getCoordinate(v)
            dist = (x - vX)**2 + (y - vY)**2
            if dist < minDist:
                minDist = dist
                closest = v
        for o in self.objects.getObjects():
            oX, oY = self.objects.getCoordinate(o)
            dist = (x - oX)**2 + (y - oY)**2
            if dist < minDist:
                minDist = dist
                closest = o
        self.positionClicked.emit(closest)

if __name__ == "__main__":
    from PyQt5.QtCore import QCoreApplication

    app = Qtw.QApplication(sys.argv)

    exampleGraph, exampleObjects = MyScene(showGraph=False)

    appGui = GraphPlotWidget(graph = exampleGraph, objects = exampleObjects)
    appGui.positionClicked.connect(lambda s: print(s))
    appGui.show()
    
    sys.exit(app.exec_())
    