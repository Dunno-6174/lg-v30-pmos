#!/usr/bin/env python3
"""Bridge H4 over /dev/ttyHS0 to /dev/vhci (Linux virtual HCI)."""
import os, sys, time, termios, select, struct

TTY = "/dev/ttyHS0"
VHCI = "/dev/vhci"

HDR = {0x01: 3, 0x02: 4, 0x03: 3, 0x04: 2, 0x05: 4}

def open_tty():
    fd = os.open(TTY, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    a = termios.tcgetattr(fd)
    iflag, oflag, cflag, lflag, ispeed, ospeed, cc = a
    iflag &= ~(termios.IGNBRK|termios.BRKINT|termios.PARMRK|termios.ISTRIP|
               termios.INLCR|termios.IGNCR|termios.ICRNL|termios.IXON|termios.IXOFF)
    oflag &= ~termios.OPOST
    lflag &= ~(termios.ECHO|termios.ECHONL|termios.ICANON|termios.ISIG|termios.IEXTEN)
    cflag &= ~(termios.CSIZE|termios.PARENB|termios.CSTOPB)
    cflag |= termios.CS8|termios.CREAD|termios.CLOCAL|termios.CRTSCTS
    cc[termios.VMIN] = 0
    cc[termios.VTIME] = 1
    termios.tcsetattr(fd, termios.TCSANOW,
                      [iflag, oflag, cflag, lflag, termios.B115200, termios.B115200, cc])
    return fd

def take_pkt(buf):
    if len(buf) < 1:
        return None, buf
    t = buf[0]
    if t not in HDR:
        return None, b""
    h = HDR[t]
    if len(buf) < 1 + h:
        return None, buf
    if t in (0x01, 0x03):
        plen = buf[3]
    elif t in (0x02, 0x05):
        plen = struct.unpack("<H", buf[3:5])[0]
    else:
        plen = buf[2]
    total = 1 + h + plen
    if len(buf) < total:
        return None, buf
    return buf[:total], buf[total:]

def write_all(fd, data):
    end = time.time() + 2
    while data and time.time() < end:
        try:
            n = os.write(fd, data)
            data = data[n:]
        except BlockingIOError:
            select.select([], [fd], [], 0.05)

def main():
    tty = open_tty()
    vh = os.open(VHCI, os.O_RDWR | os.O_NONBLOCK)
    tb, vb = b"", b""
    print("bridging tty<->vhci")
    pending_reset = None
    seen_since_reset = False
    try:
        while True:
            r, _, _ = select.select([tty, vh], [], [], 0.5)
            if tty in r:
                try:
                    d = os.read(tty, 4096)
                except BlockingIOError:
                    d = b""
                if d:
                    tb += d
                    while True:
                        p, tb = take_pkt(tb)
                        if not p:
                            break
                        print("OUT", p.hex(), flush=True)
                        write_all(vh, p)
                        if p[:4] == b"\x01\x03\x0c\x00":
                            pending_reset = time.time()
                            seen_since_reset = False
            if pending_reset and not seen_since_reset and time.time() - pending_reset > 0.5:
                cc = b"\x04\x0e\x04\x01\x03\x0c\x00"
                print("INJ", cc.hex(), flush=True)
                write_all(vh, cc)
                pending_reset = None
            if vh in r:
                try:
                    d = os.read(vh, 4096)
                except BlockingIOError:
                    d = b""
                if d:
                    vb += d
                    while True:
                        p, vb = take_pkt(vb)
                        if not p:
                            break
                        print("IN ", p.hex(), flush=True)
                        write_all(tty, p)
                        seen_since_reset = True
    finally:
        os.close(vh)
        os.close(tty)

if __name__ == "__main__":
    sys.exit(main())
