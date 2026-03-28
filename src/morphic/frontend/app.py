"""
Flask application factory and CLI entry-point for morphic.
"""

from __future__ import annotations

import logging
import os
import webbrowser

from flask import Flask


def create_app(initial_folder: str | None = None) -> Flask:
    """Create and configure the Flask application.

    Parameters
    ----------
    initial_folder : str, optional
        Folder path to pre-populate in the UI.
    """
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )
    app.secret_key = os.urandom(24)

    # Store initial folder so templates/routes can access it
    app.config["INITIAL_FOLDER"] = initial_folder or ""

    # Disable caching during development
    @app.after_request
    def _no_cache(response):
        response.headers["Cache-Control"] = (
            "no-cache, no-store, must-revalidate"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    # Register blueprints
    from morphic.frontend.routes_shared import bp as shared_bp
    from morphic.frontend.routes_converter import bp as converter_bp
    from morphic.frontend.routes_dupfinder import bp as dupfinder_bp
    from morphic.frontend.routes_inspector import bp as inspector_bp
    from morphic.frontend.routes_resizer import bp as resizer_bp
    from morphic.frontend.routes_organizer import bp as organizer_bp

    app.register_blueprint(shared_bp)
    app.register_blueprint(converter_bp, url_prefix="/api/converter")
    app.register_blueprint(dupfinder_bp, url_prefix="/api/dupfinder")
    app.register_blueprint(inspector_bp, url_prefix="/api/inspector")
    app.register_blueprint(resizer_bp, url_prefix="/api/resizer")
    app.register_blueprint(organizer_bp, url_prefix="/api/organizer")

    return app


def main() -> None:
    """CLI entry-point: ``morphic``."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="morphic",
        description="Morphic — media format converter & duplicate finder",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)",
    )
    parser.add_argument(
        "--folder",
        default=None,
        help="Pre-populate the folder path in the UI",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Flask debug mode",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't auto-open the browser",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    app = create_app(initial_folder=args.folder)

    url = f"http://{args.host}:{args.port}"
    print("\n  Morphic")
    print(f"  {'─' * 34}")
    print(f"  Open in browser: {url}")
    print("  Press Ctrl+C to stop\n")

    browser_opened = False
    if not args.no_browser and not args.debug:
        try:
            browser_opened = webbrowser.open(url)
            if not browser_opened:
                # fallback to a platform-specific browser if available
                for browser_name in [
                    "windows-default",
                    "macosx",
                    "gnome",
                    "kde",
                    "safari",
                    "firefox",
                    "chrome",
                ]:
                    try:
                        if webbrowser.get(browser_name).open(url):
                            browser_opened = True
                            break
                    except Exception:
                        continue
        except Exception as exc:
            logging.debug("Could not open browser: %s", exc)

        if not browser_opened:
            print(
                "  Warning: Could not automatically open the browser. Please open the URL manually:"
            )
            print(f"  {url}\n")

    try:
        app.run(host=args.host, port=args.port, debug=args.debug)
    except OSError as exc:
        if "Address already in use" in str(exc):
            print(
                f"\n  Error: Port {args.port} is already in use.\n"
                f"  Try: morphic --port {args.port + 1}\n"
            )
        else:
            raise


if __name__ == "__main__":
    main()
