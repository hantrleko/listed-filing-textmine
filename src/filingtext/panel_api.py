"""只读面板接口。只提供因子表和检验摘要，不提供章节正文。"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from filingtext import __version__

PUBLIC_FILES = {
    "/panel/factor.parquet": "panel_factor.parquet",
    "/panel/factor.dta": "panel_factor.dta",
    "/panel/readiness.csv": "regression_readiness.csv",
    "/panel/text_factor_eval.json": "text_factor_eval.json",
}


def serve(root: str | Path, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    directory = Path(root)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/health":
                _send_json(self, {"ok": True, "version": __version__})
                return
            if path == "/panel/meta":
                _send_json(self, meta(directory))
                return
            if path == "/panel/factor.json":
                _send_json(self, factor_records(directory))
                return
            name = PUBLIC_FILES.get(path)
            if name is None:
                _send_json(self, {"error": "没有这个资源"}, status=404)
                return
            file_path = (directory / name).resolve()
            if directory.resolve() not in file_path.parents or not file_path.is_file():
                _send_json(self, {"error": "文件不存在"}, status=404)
                return
            blob = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)

        def log_message(self, fmt: str, *args) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)


def meta(root: Path) -> dict:
    factor = root / "panel_factor.parquet"
    payload = {"version": __version__, "files": []}
    for name in PUBLIC_FILES.values():
        path = root / name
        if path.is_file():
            payload["files"].append({"name": name, "bytes": path.stat().st_size})
    if factor.is_file():
        import pandas as pd

        frame = pd.read_parquet(factor)
        payload["n_rows"] = int(len(frame))
        payload["columns"] = [column for column in frame.columns if _public_column(column)]
    return payload


def factor_records(root: Path, limit: int = 2000) -> dict:
    path = root / "panel_factor.parquet"
    if not path.is_file():
        return {"rows": [], "n_rows": 0}
    import pandas as pd

    frame = pd.read_parquet(path)
    keep = [column for column in frame.columns if _public_column(column)]
    view = frame[keep].head(limit)
    rows = json.loads(view.to_json(orient="records", date_format="iso", force_ascii=False))
    return {"n_rows": int(len(frame)), "returned": len(rows), "rows": rows}


def _public_column(name: str) -> bool:
    """因子数字可以出去。章节正文、本地路径和文件指纹留在本机。"""
    lowered = name.lower()
    if lowered in {"section_text", "text", "sentence", "sentences", "body"}:
        return False
    if "sha1" in lowered or lowered.endswith("_sha") or "_sha_" in lowered:
        return False
    if lowered.endswith("_text") or lowered.startswith("text_") or "_text_" in lowered:
        return False
    if lowered.endswith("_path") or lowered.endswith("path") or "_path_" in lowered:
        return False
    return True


def _send_json(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="在本机提供因子表只读接口")
    parser.add_argument("--root", default="data/workspace/output")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = serve(args.root, args.host, args.port)
    print(f"http://{args.host}:{args.port}/health")
    server.serve_forever()


if __name__ == "__main__":
    main()
