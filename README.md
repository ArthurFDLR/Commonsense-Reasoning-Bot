# Robotics_Vision_Simulator

## Hand pose classifier

This classifier is build upon the excellent pose estimator [**OpenPose**](https://github.com/CMU-Perceptual-Computing-Lab/openpose) from **CMU Perceptual Computing Lab**.

### 1. OpenPose output

The 21 hand keypoints (2D) used as input for this classifier are produced by OpenPose. The hand output format is as follow:

![Hand data output](/.github/markdown/keypoints_hand.png)

<img src="/.github/markdown/keypoints_hand.png" width="200">

More information can be found [here](https://github.com/CMU-Perceptual-Computing-Lab/openpose/blob/master/doc/output.md#face-and-hands). Please note that even if only hand keypoints are used, [OpenPose recquiered the whole body to be analysed](https://github.com/CMU-Perceptual-Computing-Lab/openpose/blob/master/doc/standalone_face_or_hand_keypoint_detector.md) in order to generate hand informations. Furtheremore keypoints coordinates are given in the frame of reference of the image feeded to OpenPose. Thus, the coordinates have to be normalized.

### 2. Keypoints normalization

To prepare the data for the input of the neural network, coordinates are normalized relatively to finger length and the center of gravity of the hand.

* **Scaling:** First, the length of each fingers - defined as a set of lines of the same color, see above - is calculated. The euclidian distances of all segments of a finger are sumed *- e.g.* <img src="https://render.githubusercontent.com/render/math?math=Thumb\_length = \sum_{i=0}^{3} d(\boldsymbol{k_i}, \boldsymbol{k_{i%2B1}})">. Then, every coordinates composing the hand are divided by the greater finger length.

* **Centering:** Keypoints are centered relatively to the center of mass of the hand which in this case, is simply defined as <img src="https://render.githubusercontent.com/render/math?math=(\bar{\boldsymbol{k_x}}, \bar{\boldsymbol{k_y}})">.

![Formatted data example ('Super')](/.github/markdown/formated_hand.png)

## Physics simulator

![Hand data Formatting](/.github/markdown/handDataFormatting.png)

![RSV Gui](/.github/markdown/GUIexample.PNG)

![OpenPose test on generated image](/.github/markdown/InSimTest_OpenPose.jpg)
