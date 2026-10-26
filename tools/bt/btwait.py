#!/usr/bin/env python3
"""Wait until the WCN3990 controller answers HCI (reset or version)."""
import os, sys, time, termios, struct, select
DEV="/dev/ttyHS0"
def open_tty():
    fd=os.open(DEV,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
    a=termios.tcgetattr(fd); iflag,oflag,cflag,lflag,ispeed,ospeed,cc=a
    iflag&=~(termios.IGNBRK|termios.BRKINT|termios.PARMRK|termios.ISTRIP|termios.INLCR|termios.IGNCR|termios.ICRNL|termios.IXON|termios.IXOFF)
    oflag&=~termios.OPOST
    lflag&=~(termios.ECHO|termios.ECHONL|termios.ICANON|termios.ISIG|termios.IEXTEN)
    cflag&=~(termios.CSIZE|termios.PARENB|termios.CSTOPB); cflag|=termios.CS8|termios.CREAD|termios.CLOCAL|termios.CRTSCTS
    cc[termios.VMIN]=0; cc[termios.VTIME]=1
    termios.tcsetattr(fd,termios.TCSANOW,[iflag,oflag,cflag,lflag,termios.B115200,termios.B115200,cc])
    return fd
def send(fd,op,data=b""):
    try: os.write(fd,b"\x01"+struct.pack("<HB",op,len(data))+data)
    except BlockingIOError: pass
def readpkt(fd,t):
    end=time.time()+t; buf=b""
    while time.time()<end:
        r,_,_=select.select([fd],[],[],0.05)
        if not r: continue
        try: b=os.read(fd,1)
        except BlockingIOError: continue
        if not b: continue
        buf+=b
        if len(buf)<3: continue
        if buf[0]!=4: buf=b""; continue
        plen=buf[2]
        while len(buf)<3+plen and time.time()<end:
            r,_,_=select.select([fd],[],[],0.05)
            if r:
                try: buf+=os.read(fd,1)
                except BlockingIOError: pass
        if len(buf)>=3+plen: return buf
    return None
def main():
    fd=open_tty()
    try:
        deadline=time.time()+120
        n=0
        while time.time()<deadline:
            n+=1
            send(fd,0x0C03)
            p=readpkt(fd,0.4)
            if p and p[1]==0x0e:
                print("ready after %d tries (reset)"%n); return 0
            send(fd,0xFC00,b"\x19")
            p=readpkt(fd,0.4)
            if p and p[1]==0xff:
                print("ready after %d tries (version)"%n); return 0
            time.sleep(1)
        print("not ready"); return 1
    finally:
        os.close(fd)
if __name__=="__main__":
    sys.exit(main())
