import argparse

import uvicorn

from .server import create_app


def main():
    parser = argparse.ArgumentParser(
        description="Run the video-use browser workspace and MCP server"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    uvicorn.run(create_app(), host=args.host, port=args.port, access_log=False)


if __name__ == "__main__":
    main()
