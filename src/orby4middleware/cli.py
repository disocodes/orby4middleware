import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(prog="orby4middleware")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    uvicorn.run("orby4middleware.app:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
