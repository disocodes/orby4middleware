import argparse
from pathlib import Path
import httpx
from .serial_transport import capture_serial
from .spool import FileSpool


def cmd_capture(args):
    data = capture_serial(args.port, args.baud, data_bits=args.data_bits, parity=args.parity,
                          stop_bits=args.stop_bits, seconds=args.seconds)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_bytes(data)
    print(f"captured {len(data)} bytes to {args.output}")
    print(data.hex(" "))


def cmd_replay(args):
    spool = FileSpool(args.spool)
    headers = {"X-API-Key": args.api_key}
    for path in spool.pending():
        payload = path.read_text(encoding="utf-8")
        response = httpx.post(args.url, content=payload, headers={**headers, "Content-Type": "application/json"}, timeout=15)
        if 200 <= response.status_code < 300:
            spool.ack(path)
            print(f"delivered {path.name}")
        else:
            print(f"failed {path.name}: {response.status_code} {response.text[:200]}")
            break


def main():
    p = argparse.ArgumentParser(prog="orby4-edge")
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("capture", help="capture raw serial bytes without parsing/delivery")
    c.add_argument("--port", required=True); c.add_argument("--baud", type=int, default=9600)
    c.add_argument("--data-bits", type=int, default=8); c.add_argument("--parity", default="N")
    c.add_argument("--stop-bits", type=int, default=1); c.add_argument("--seconds", type=int, default=30)
    c.add_argument("--output", required=True); c.set_defaults(func=cmd_capture)
    r = sub.add_parser("replay", help="replay locally spooled JSON payloads")
    r.add_argument("--spool", default="spool"); r.add_argument("--url", required=True)
    r.add_argument("--api-key", required=True); r.set_defaults(func=cmd_replay)
    args = p.parse_args(); args.func(args)


if __name__ == "__main__":
    main()
