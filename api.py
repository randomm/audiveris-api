from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sse_starlette.sse import EventSourceResponse
import tempfile
import os
import subprocess
import logging
import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Maximum file size in bytes (e.g., 10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

def is_jpod_available():
    """Check if JPod PDF handling is available"""
    try:
        result = subprocess.run(
            ['java', '-cp', '/opt/audiveris/lib/*', 'de.intarsys.pdf.content.CSInterpreter'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except subprocess.CalledProcessError:
        return False

async def convert_pdf_to_tiff(pdf_path: Path) -> Path:
    """Convert PDF to TIFF using ImageMagick"""
    tiff_path = pdf_path.with_suffix('.tiff')
    try:
        logger.info(f"Converting PDF to TIFF: {pdf_path}")
        process = await asyncio.create_subprocess_exec(
            'convert', '-density', '300', str(pdf_path), '-colorspace', 'Gray', str(tiff_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"PDF conversion failed: {stderr.decode()}")
        
        logger.info("PDF conversion successful")
        return tiff_path
    except Exception as e:
        logger.error(f"PDF conversion failed: {str(e)}")
        raise

async def process_file(input_path: Path) -> bytes:
    """Process a file with Audiveris and return the MusicXML content"""
    try:
        # Handle PDF files
        file_to_process = input_path
        if input_path.suffix.lower() == '.pdf':
            logger.info("Detected PDF file")
            if not is_jpod_available():
                logger.info("JPod not available, converting to TIFF")
                file_to_process = await convert_pdf_to_tiff(input_path)
        
        # Run Audiveris command
        logger.info(f"Running Audiveris on: {file_to_process}")
        process = await asyncio.create_subprocess_exec(
            'audiveris',
            '-batch',
            '-export',
            str(file_to_process),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"Audiveris processing failed: {stderr.decode()}")
        
        # Get the base name without extension
        base_name = input_path.stem
        
        # Check Audiveris default output location
        output_path = Path(f"/root/.local/share/AudiverisLtd/audiveris/{base_name}/{base_name}.mxl")
        logger.info(f"Looking for output file at: {output_path}")
        
        if not output_path.exists():
            raise RuntimeError("Output file not found after Audiveris processing")
        
        # Read and return the MusicXML content
        return output_path.read_bytes()
        
    finally:
        # Clean up any temporary files
        if 'file_to_process' in locals() and file_to_process != input_path:
            try:
                os.unlink(file_to_process)
                logger.info("Temporary TIFF file cleaned up")
            except OSError as e:
                logger.warning(f"Failed to clean up temporary file: {e}")

async def process_file_with_progress(input_path: Path) -> AsyncGenerator[dict, None]:
    """Process a file with Audiveris and yield progress updates"""
    try:
        # Initial progress update
        yield {"status": "processing", "message": "Starting conversion..."}
        
        # Handle PDF files
        file_to_process = input_path
        if input_path.suffix.lower() == '.pdf':
            yield {"status": "processing", "message": "Detected PDF file"}
            if not is_jpod_available():
                yield {"status": "processing", "message": "Converting PDF to TIFF..."}
                file_to_process = await convert_pdf_to_tiff(input_path)
                yield {"status": "processing", "message": "PDF conversion complete"}
        
        # Run Audiveris command
        yield {"status": "processing", "message": f"Processing with Audiveris: {file_to_process}"}
        process = await asyncio.create_subprocess_exec(
            'audiveris',
            '-batch',
            '-export',
            str(file_to_process),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Monitor stdout for progress
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            message = line.decode().strip()
            if message:
                yield {"status": "processing", "message": message}
        
        # Wait for process to complete
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"Audiveris processing failed: {stderr.decode()}")
        
        # Get the base name without extension
        base_name = input_path.stem
        
        # Check Audiveris default output location
        output_path = Path(f"/root/.local/share/AudiverisLtd/audiveris/{base_name}/{base_name}.mxl")
        
        if not output_path.exists():
            raise RuntimeError("Output file not found after Audiveris processing")
        
        yield {"status": "complete", "message": "Processing complete"}
        
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        yield {"status": "error", "message": str(e)}
        
    finally:
        # Clean up any temporary files
        if 'file_to_process' in locals() and file_to_process != input_path:
            try:
                os.unlink(file_to_process)
                logger.info("Temporary TIFF file cleaned up")
            except OSError as e:
                logger.warning(f"Failed to clean up temporary file: {e}")

async def check_file_size(file: UploadFile):
    """Check if file size is within limits"""
    # Read and measure file size
    contents = await file.read()
    size = len(contents)
    
    # Reset file position for subsequent reads
    await file.seek(0)
    
    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({size / 1024 / 1024:.1f}MB) exceeds maximum allowed size ({MAX_FILE_SIZE / 1024 / 1024:.1f}MB)"
        )

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.post("/convert")
async def convert_file(file: UploadFile = File(...)):
    """Convert a music score file to MusicXML"""
    await check_file_size(file)
    
    # Create a temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        
        # Give the uploaded file a unique name by prepending a UUID
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        input_path = temp_dir_path / unique_filename
        
        try:
            logger.info(f"Processing file: {file.filename}")
            contents = await file.read()
            input_path.write_bytes(contents)
            logger.info(f"File saved to: {input_path}")
            
            # Process the file
            result = await process_file(input_path)
            
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to process file"
                )
            
            return Response(
                content=result,
                media_type="application/vnd.recordare.musicxml+xml"
            )
            
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

@app.post("/convert/stream")
async def convert_file_stream(file: UploadFile = File(...)):
    """Convert a music score file to MusicXML with progress updates"""
    await check_file_size(file)
    
    async def event_generator():
        # Create a temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            input_path = temp_dir_path / file.filename
            
            try:
                # Save uploaded file
                logger.info(f"Processing file: {file.filename}")
                contents = await file.read()
                input_path.write_bytes(contents)
                logger.info(f"File saved to: {input_path}")
                
                # Start processing with progress updates
                async for update in process_file_with_progress(input_path):
                    yield {
                        "event": "message",
                        "data": json.dumps(update)
                    }
                    
            except Exception as e:
                logger.error(f"Error processing file: {str(e)}")
                yield {
                    "event": "message",
                    "data": json.dumps({
                        "status": "error",
                        "message": str(e)
                    })
                }
    
    return EventSourceResponse(event_generator()) 