import cv2
import numpy as np 
import requests 
import time
from ultralytics import YOLO


URL="http://192.168.4.1:81/stream"


model = YOLO("yolov8n.pt")



def connect_stream():
    while True:
        try:
            print("connecting to camera stream .... ")
            stream =requests.get(URL, stream=True, timeout=5)
            print("Camera connected!")
            return stream
        except:
            print("Waiting for camera ...")
            time.sleep(2)
  


print("\nControls: W A S D | Q =Quit ")






while True:
    try:
        stream = connect_stream()
        bytes_data =b""
        fps_time =time.time()
        frame_count =0

        for chunk in stream.iter_content(chunk_size=1024):
            bytes_data += chunk

            a = bytes_data.find(b'\xff\xd8')
            b = bytes_data.find(b'\xff\xd9')

            if a!= -1 and b!=-1:
                jpg= bytes_data[a:b+2]
                bytes_data = bytes_data[b+2:]

                frame =cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8),cv2.IMREAD_COLOR)
                frame= cv2.resize(frame,(640,480))

                #YOLO detection
                results= model(frame,verbose=False)
                annotated = results[0].plot()

                #simple navigation
                gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
                edges =cv2.Canny(gray,50, 150)

                roi =edges[300:480,:]
                left =np.sum(roi[:,:213])
                center =np.sum(roi[:,213:426])
                right= np.sum(roi[:,426:])


                if center < left and center< right:
                    decision= "FORWARD"
                elif left<right:
                    decision="LEFT"
                else:
                    decision="RIGHT"

                cv2.putText(annotated,"AI : "+ decision,(10,60),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)


                frame_count+=1
                if frame_count>=10:
                    fps =frame_count/(time.time()- fps_time)
                    fps_time =time.time()
                    frame_count=0
                    cv2.putText(annotated,f"FPS: {int(fps)}",(10,30),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)

                cv2.imshow("Robot Brain", annotated)

                key =cv2.waitKey(1)&0xFF
                if key == ord('w'):
                    print("FORWARD")
                elif key == ord('s'):
                    print("BACKWARD")
                elif key == ord('a'):
                    print("LEFT")
                elif key== ord('d'):
                    print("RIGHT")
                elif key == ord('q'):
                    exit()
    except Exception as e:
        print(" Stream lost , Reconnection ... ")
        time.sleep(2)







cv2.destroyAllWindows()
