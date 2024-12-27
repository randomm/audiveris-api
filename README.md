# Audiveris API

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Tests](https://github.com/randomm/audiveris-api/actions/workflows/test.yml/badge.svg)](https://github.com/randomm/audiveris-api/actions/workflows/test.yml)

This directory contains a FastAPI-based REST API wrapper for Audiveris OMR engine. The API provides endpoints for converting sheet music (PDF/images) to MusicXML format.

## Acknowledgments

This project is built upon the excellent [Audiveris](https://github.com/Audiveris/audiveris) Optical Music Recognition (OMR) engine. We are grateful to the Audiveris team for creating and maintaining such a powerful open-source tool for music score analysis. Audiveris is also licensed under AGPL-3.0, which allows us to create this API wrapper while maintaining the same open-source spirit.

The Audiveris version used in this project is configured in `docker-compose.yml` under the build args. To use a different version:
1. Update the `AUDIVERIS_VERSION` build arg in `docker-compose.yml`
2. Rebuild the Docker image:
```bash
docker compose build
```

## Features

- PDF and image file support
- Automatic PDF to TIFF conversion for macOS compatibility
- Health check monitoring
- Docker Compose setup with resource management
- Cached builds for faster development
- Comprehensive test suite

## Prerequisites

- Docker with BuildKit support
- At least 2GB of RAM available for the container
- Sufficient disk space for caching and builds
- Python 3.8 or higher (for local development)
- Tesseract OCR with English language support (installed automatically in Docker)

## Quick Start

1. Clone and start the service:
```bash
git clone <repository-url>
cd audiveris-api
docker compose up --build
```

2. Convert a music score:
```bash
curl -X POST -F "file=@your-sheet-music.pdf" \
     http://localhost:8000/convert \
     -o output.mxl
```

## API Endpoints

- `POST /convert`: Convert uploaded sheet music file to MusicXML
  - Accepts PDF or image files
  - Returns MusicXML file
- `GET /health`: Health check endpoint

API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development

### Running Tests

Tests run in Docker to ensure all dependencies are available:

```bash
# Run all tests
docker compose run --rm test

# Run specific test
docker compose run --rm test python3 -m pytest tests/test_api.py::test_health_check -v

# Clean up
docker compose down
```

### Local Development

For development without Docker (requires manual Audiveris installation):

1. Install dependencies:
```bash
pip install -r requirements.txt
pip install -e ".[test]"
```

2. Install Audiveris following the [official documentation](https://audiveris.github.io/audiveris/_pages/install/sources/#building-from-sources-windows-macos-linux-archlinux)

## Troubleshooting

1. PDF conversion fails:
   - Check if the PDF is valid and readable
   - For macOS, the API automatically converts PDFs to TIFF
   - Check logs with `docker compose logs -f`

2. Memory issues:
   - Ensure at least 2GB RAM is available for the container
   - Adjust memory limits in `docker-compose.yml` if needed

3. Test failures:
   - Ensure you're running tests in the container
   - Check if test files are present in `tests/test_files`
   - Verify Audiveris installation with `docker compose run --rm test audiveris -help`

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0). This means:

- You can use this software for any purpose
- You can modify this software
- You can distribute this software
- You must include the license and copyright notice with the code
- You must share any modifications you make under the same license
- You must disclose your source code when you distribute the software
- If you run a modified version of this software as a service (e.g., on a server), you must make the complete source code available to users of that service

For more details, see the [LICENSE](LICENSE) file in the repository. 