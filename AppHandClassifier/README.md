# II/ TRAINING AND TEST

Human keypoints used in this neural network is produced by OpenPose. There are 18 key-points representing for human skeletons as described below:

![human_ske](images/human_skeleton_coco.png)

For each person, the coordinates of the singular point in is obtained, where n is the joint number. The size of each human skeleton in a frame is varied due to camera distance and camera angle. To prepare the data for the input of the neural network, the coordinates are normalized relative to the body length and relative to the center of gravity.

## 1. How to calculate length of body and center of gravity?

The Euclidean distance between two points (A, B) is defined as below:

```python
      def euclidean_dist(a, b):
          # This function calculates the euclidean distance between 2 point in 2-D coordinates
          # if one of two points is (0,0), dist = 0
          # a, b: input array with dimension: m, 2
          # m: number of samples
          # 2: x and y coordinate
          try:
              if (a.shape[1] == 2 and a.shape == b.shape):
                  # check if element of a and b is (0,0)
                  bol_a = (a[:,0] != 0).astype(int)
                  bol_b = (b[:,0] != 0).astype(int)
                  dist = np.linalg.norm(a-b, axis=1)
                  return((dist*bol_a*bol_b).reshape(a.shape[0],1))
          except:
              print("[Error]: Check dimension of input vector")
              return 0
```
