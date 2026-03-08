"""Shared test fixtures."""

from __future__ import annotations

import pytest
from PIL import Image

from morphic.frontend.app import create_app


@pytest.fixture()
def app():
    """Create a Flask app for testing."""
    application = create_app(initial_folder="/tmp")
    application.config["TESTING"] = True
    return application


@pytest.fixture()
def client(app):
    """Flask test client."""
    with app.test_client() as c:
        yield c


@pytest.fixture()
def tmp_media(tmp_path):
    """Create a temp directory with sample image/video files."""
    # Create images
    for name in ["photo.jpg", "image.png", "pic.tif"]:
        img = Image.new("RGB", (10, 10), color="red")
        img.save(str(tmp_path / name))

    # Create fake video files (0-byte placeholders)
    for name in ["clip.mp4", "movie.mov"]:
        (tmp_path / name).write_bytes(b"\x00" * 100)

    # Create a non-media file
    (tmp_path / "readme.txt").write_text("hello")

    # Subfolder with more files
    sub = tmp_path / "sub"
    sub.mkdir()
    img = Image.new("RGB", (20, 20), color="blue")
    img.save(str(sub / "deep.jpg"))
    (sub / "deep.mp4").write_bytes(b"\x00" * 50)

    return tmp_path


@pytest.fixture()
def test_image(tmp_path):
    """Create a single test image and return its path."""
    path = tmp_path / "test.jpg"
    img = Image.new("RGB", (100, 100), color="green")
    img.save(str(path))
    return str(path)


@pytest.fixture()
def rgba_image(tmp_path):
    """Create an RGBA test image and return its path."""
    path = tmp_path / "test_rgba.png"
    img = Image.new("RGBA", (50, 50), color=(255, 0, 0, 128))
    img.save(str(path))
    return str(path)


@pytest.fixture()
def palette_image(tmp_path):
    """Create a palette (P mode) test image and return its path."""
    path = tmp_path / "test_palette.png"
    img = Image.new("P", (50, 50))
    img.save(str(path))
    return str(path)
