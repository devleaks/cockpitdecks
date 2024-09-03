import socket
import json
from datetime import datetime

ANY = "0.0.0.0"

MCAST_GRP = "239.255.1.1"
MCAST_PORT = 49505  # (MCAST_PORT is 49707 for XPlane12)

# Create a UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

# Allow multiple sockets to use the same PORT number
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

# Bind to the port that we know will receive multicast data
sock.bind((ANY, MCAST_PORT))

# Tell the kernel that we want to add ourselves to a multicast group
# The address for the multicast group is the third param
status = sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(MCAST_GRP) + socket.inet_aton(ANY))

# setblocking(False) is equiv to settimeout(0.0) which means we poll the socket.
# But this will raise an error if recv() or send() can't immediately find or send data.
sock.setblocking(False)

while 1:
    try:
        data, addr = sock.recvfrom(1024)
    except socket.error as e:
        pass
    else:
        print("Date: ", datetime.now().isoformat())
        print("From: ", addr)
        # print("Data: ", data)
        print(json.dumps(json.loads(data.decode("utf-8")), indent=2))
