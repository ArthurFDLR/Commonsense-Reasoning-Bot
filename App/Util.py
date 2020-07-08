import cv2

def printHeadLine(name:str = '', mainTitle:bool = True, length:int = 80):
    '''Print title in console:
        #### TITLE ####
        ###############

    Parameters:
        name (str): Title displayed
        mainTitle(bool): Add second '#' line if True
        length(int): Length of lines
    '''

    print('')
    length = max(length,len(name))
    if len(name) > 0:
        firstLine = '#'*((length-len(name))//2) + ' ' + name + ' ' + '#'*((length-len(name))//2)
        print(firstLine)
        if mainTitle:
            print('#'*len(firstLine))
    else:
        print('#'*length)
    print('')

def resizeCvFrame(frame, ratio:float):
    width = int(frame.shape[1] * ratio) 
    height = int(frame.shape[0] * ratio) 
    dim = (width, height) 
    # resize image in down scale
    resized = cv2.resize(frame, dim, interpolation = cv2.INTER_AREA) 
    return resized