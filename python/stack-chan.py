from websocket_server import WebsocketServer
import json
import base64
import time
from threading import Timer
from serial import Serial, SerialException

without_sensor = False
connecting = False
uart = None

def update(client,server):
    time.sleep(3)
    b64 = base64.b64encode(bytes([0,123,1,0,1,1,1,1,1,1])).decode('utf-8')
    response = '{"jsonrpc":"2.0","method":"characteristicDidChange","params":{"serviceId":61445,"characteristicId":"5261da01-fa7e-42ab-850b-7c80220097cc","encoding":"base64","message":"' + b64 + '"}}'
    server.send_message(client, response)

    while connecting:
        if uart and not without_sensor:
            try:
                r = uart.read_until(b'\n').strip()
            except Exception as e:
                print(e)
                break
            #print(r)
            if len(r)>0 and r[0]==42:
                try:
                    s = list(map(int,r[1:].decode('utf-8').split(',')))
                except Exception as e:
                    print(e)
                else:
                    tiltX = 0
                    tiltY = 0
                    if len(s) and s[0] == 1:
                        print(s)
                        tiltX = int(s[1]) * 10
                        tiltY = int(s[2]) * 10
                    buf = bytearray(10)
                    buf[0] = tiltX // 256
                    buf[1] = tiltX % 256
                    buf[2] = tiltY // 256
                    buf[3] = tiltY % 256
                    buf[4] = 1 if int(s[3]) > 50 else 0
                    b64 = base64.b64encode(bytes(buf)).decode('utf-8')
                    response = '{"jsonrpc":"2.0","method":"characteristicDidChange","params":{"serviceId":61445,"characteristicId":"5261da01-fa7e-42ab-850b-7c80220097cc","encoding":"base64","message":"' + b64 + '"}}'
                    server.send_message(client, response)
                    #print(response)
        else:
            b64 = base64.b64encode(bytes(10)).decode('utf-8')
            response = '{"jsonrpc":"2.0","method":"characteristicDidChange","params":{"serviceId":61445,"characteristicId":"5261da01-fa7e-42ab-850b-7c80220097cc","encoding":"base64","message":"' + b64 + '"}}'
            server.send_message(client, response)
            print(response)
            time.sleep(1)
    print("Update exited")

def new_client(client, server):
    print("New client connected: %d" % client['id'])

def client_left(client, server):
    global connecting
    print("Client disconnected: %d" % client['id'])
    connecting = False

def message_received(client, server, message):
    global connecting, uart
    if len(message) > 200:
        message = message[:200]+'..'
    print("Client(%d) said: %s" % (client['id'], message))
    dict = json.loads(message)
    if dict['method'] == 'discover':
        id = dict['id']
        response = '{"jsonrpc":"2.0","id":'+str(id)+',"result":null}'
        server.send_message(client, response)
        response = '{"jsonrpc":"2.0","method":"didDiscoverPeripheral","params":{"name":"python","rssi":-70,"peripheralId":65536}}'
        server.send_message(client, response)
    if dict['method'] == 'connect':
        id = dict['id']
        try:
            uart = Serial("/dev/ttyUSB0", 115200)
        except SerialException:
            print("can't open /dev/ttyUSB0")
            uart = None
            response = '{"jsonrpc":"2.0","id":'+str(id)+',"error":{}}'
        else:
            response = '{"jsonrpc":"2.0","id":'+str(id)+',"result":null}'
        server.send_message(client, response)
    if dict['method'] == 'read':
        connecting = True
        timer = Timer(1, update, (client, server))
        timer.start()
    if dict['method'] == 'write':
        message = base64.b64decode(dict['params']['message'])
        if message[0] == 0x81:
            print(message[1:])
            print('Say "'+message[1:].decode('utf-8')+'"')
            if uart:
                v = '*3,'+','.join(list(map(str,message[1:])))
                print(v)
                uart.write(v.encode('utf-8'))
        elif message[0] == 0x82:
            for x in list(message[1:]):
                print(format(x,"05b")[::-1])
            if uart:
                v = '*0'
                if message[1] == 1 or message[1] == 2:
                    v = '*'+str(message[1])+','+str(message[2]*32 + message[3])
                elif message[1] == 4:
                    v = '*4,'+str(message[2])
                print(v)
                uart.write(v.encode('utf-8'))
        id = dict['id']
        response = '{"jsonrpc":"2.0","id":'+str(id)+',"result":null}'
        server.send_message(client, response)

PORT=20111
server = WebsocketServer(port = PORT)
server.set_fn_new_client(new_client)
server.set_fn_client_left(client_left)
server.set_fn_message_received(message_received)
server.run_forever()
