import time

ENQ = b"\x05"
ACK = b"\x06"
NAK = b"\x15"
EOT = b"\x04"
ETX = b"\x03"


def capture_serial(port: str, baud: int, *, data_bits: int = 8, parity: str = "N", stop_bits: int = 1,
                   seconds: int = 30) -> bytes:
    import serial
    ser = serial.Serial(port=port, baudrate=baud, bytesize=data_bits, parity=parity,
                        stopbits=stop_bits, timeout=0.2)
    buf = bytearray(); end = time.time() + seconds
    try:
        while time.time() < end:
            chunk = ser.read(4096)
            if chunk:
                buf.extend(chunk)
    finally:
        ser.close()
    return bytes(buf)


def receive_enq_ack_session(ser, *, timeout_seconds: float = 15.0) -> bytes:
    """Receive a simple ENQ/ACK framed analyzer session.

    This intentionally does not assume model-specific checksum/frame numbering. A model profile can
    wrap or replace it when the vendor protocol requires additional framing rules.
    """
    deadline = time.time() + timeout_seconds
    buf = bytearray()
    while time.time() < deadline:
        b = ser.read(1)
        if not b:
            continue
        if b == ENQ:
            ser.write(ACK)
            continue
        if b == EOT:
            break
        buf.extend(b)
        if b == ETX:
            ser.write(ACK)
    return bytes(buf)
