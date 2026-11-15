# ytdlp-sp-api

A lightweight API project built around `yt-dlp` for extracting media metadata and supporting download workflows through a service interface.

## Overview

This repository provides a simple backend for working with yt-dlp in an API-oriented setup. It is intended to make media extraction, metadata retrieval, and download orchestration easier to integrate into other services or applications.

## Features

- URL metadata extraction with `yt-dlp`
- Download support for compatible media sources
- API-style interface for external clients
- Easy local development and deployment workflows
- Extensible backend structure for future integrations

## Project Structure

```text
.
├── app/
├── config/
├── src/
├── requirements.txt
├── README.md
├── .env.example
└── main.py
```

> Adjust exact paths to match the project layout in this repository as it evolves.

## Requirements

- Python 3.10+
- `ffmpeg` (if media conversion or format processing is required)
- `yt-dlp`
- pip / virtual environment support

## Installation

```bash
git clone https://github.com/dragonser999/ytdlp-sp-api.git
cd ytdlp-sp-api
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running the Project

Start the application with the project entry point:

```bash
python main.py
```

If the project uses an ASGI/HTTP framework, run the service with the appropriate command for that framework (for example `uvicorn` or `gunicorn`).

## Example Usage

```bash
curl -X GET "http://localhost:8000/health"
```

```bash
curl -X POST "http://localhost:8000/download" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/video"}'
```

## Environment Configuration

Create a `.env` file based on the example configuration (if provided in the project):

```bash
cp .env.example .env
```

Then update the values to suit your environment.

## License

This project does not currently declare a license in the repository. If you plan to distribute or publish it, consider adding an appropriate open-source license.

## Contributing

Contributions are welcome. Please open an issue or submit a pull request with a clear summary of the change.

## Contact

For questions or support, reach out through the repository issue tracker on GitHub.
