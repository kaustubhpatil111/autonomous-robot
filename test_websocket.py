import socket
s = socket.socket()
try:
    s.connect(('192.168.225.68', 81))
    print("Port 81 is OPEN")
except:
    print("Port 81 is CLOSED")
s.close()