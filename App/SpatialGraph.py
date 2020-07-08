import matplotlib.pyplot as plt

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
    
    def showGraph(self):
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