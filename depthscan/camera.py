import cv2
import torch
import numpy as np


class DepthScanner(object):
    def __init__(self, camera:int=0):
        # Set OpenCV video-capture parameters
        self.camera_num = camera
        self.camera = cv2.VideoCapture(self.camera_num)
        self.is_running = False
        
        # Configure PyTorch MiDaS
        self.model_type = "MiDaS_small"
        self.model = torch.hub.load("intel-isl/MiDaS", self.model_type)
        self.__device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        self.model.to(self.device)
        self.model.eval()
        midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")
        self.transform = midas_transforms.small_transform
        
    def __repr__(self) -> str:
        return f'<DepthScanner | camera={self.camera_num}, device={str(self.__device).upper()}>'
    
    @property
    def device(self):
        return str(self.__device)
    
    @staticmethod
    def __normalize(frame, bits:int):
        depth_min = frame.min()
        depth_max = frame.max()
        max_val = (2 ** (8 * bits)) - 1
        
        if depth_max - depth_min > np.finfo("float").eps:
            out = max_val * (frame - depth_min) / (depth_max - depth_min)
        else:
            out = np.zeros(frame.shape, dtype=frame.type)
            
        if bits == 1:
            return out.astype("uint8")
        return out.astype("uint16")
    
    def get_depth(self, frame):
        input_batch = self.transform(frame).to(self.__device)
        with torch.no_grad():
            prediction = self.model(input_batch)
            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=frame.shape[:2],
                mode="bicubic",
                align_corners=False,
            ).squeeze()
        depth_frame = prediction.cpu().numpy()
        return self.__normalize(depth_frame, bits=2)
    
    def capture(self, frame):
        depth_frame = self.get_depth(frame)
        cv2.imshow("Depth Scan", depth_frame)
    
    def run(self, live_mapping:bool=False):
        self.is_running = True
        print(f'[{self.device.upper()}] Running depth scan...')
        
        try:
            while self.is_running:
                ret, frame = self.camera.read()
                display_frame = self.get_depth(frame) if live_mapping else frame
                cv2.imshow("Standard Camera", display_frame)

                key = cv2.waitKey(10)
                if key == ord("c") and not live_mapping:
                    self.capture(frame)
                    print("Frame captured!")
                
                if key == 27:
                    print("Closing scanner...")
                    self.is_running = False
                    break
                
        except Exception as e:
            print(f'Error during camera streaming: {e}')
            
        finally:
            self.camera.release()
            cv2.destroyAllWindows()
            
        print("Scanner closed!")
        