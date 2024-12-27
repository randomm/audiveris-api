from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.responses import FileResponse
import subprocess
import tempfile
import os
import shutil
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Audiveris API",
    description="API for converting sheet music (PDF/images) to MusicXML using Audiveris",
    version="1.0.0"
)

def is_jpod_available():
    """Check if JPod PDF handling is available"""
    try:
        result = subprocess.run(
            ['java', '-cp', '/opt/audiveris/lib/*', 'de.intarsys.pdf.content.CSInterpreter'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        logger.error(f"Error checking JPod availability: {e.stderr}")
        return False

def convert_pdf_to_tiff(pdf_path: Path) -> Path:
    """Convert PDF to TIFF using ImageMagick"""
    tiff_path = pdf_path.with_suffix('.tiff')
    try:
        logger.info(f"Converting PDF to TIFF: {pdf_path}")
        result = subprocess.run(
            ['convert', '-density', '300', str(pdf_path), '-colorspace', 'Gray', str(tiff_path)],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info("PDF conversion successful")
        return tiff_path
    except subprocess.CalledProcessError as e:
        logger.error(f"PDF conversion failed: {e.stderr}")
        raise

@app.post("/convert", response_class=FileResponse)
async def convert_to_musicxml(file: UploadFile):
    """
    Convert uploaded sheet music (PDF or image) to MusicXML using Audiveris
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    logger.info(f"Processing file: {file.filename}")
    
    # Create a temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save uploaded file
        temp_input_path = Path(temp_dir) / file.filename
        with open(temp_input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"File saved to: {temp_input_path}")
        
        # Handle PDF files
        input_path = temp_input_path
        tiff_path = None
        if temp_input_path.suffix.lower() == '.pdf':
            logger.info("Detected PDF file")
            if not is_jpod_available():
                logger.info("JPod not available, converting to TIFF")
                try:
                    tiff_path = convert_pdf_to_tiff(temp_input_path)
                    input_path = tiff_path
                except subprocess.CalledProcessError as e:
                    raise HTTPException(
                        status_code=500,
                        detail=f"PDF to TIFF conversion failed: {e.stderr}"
                    )
        
        # Expected output path (Audiveris adds .mxl extension)
        output_path = input_path.with_suffix('.mxl')
        
        try:
            # Run Audiveris command
            logger.info(f"Running Audiveris on: {input_path}")
            process = subprocess.run(
                ['audiveris', str(input_path), '-export'],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Audiveris stdout: {process.stdout}")
            if process.stderr:
                logger.warning(f"Audiveris stderr: {process.stderr}")
            
            # Get the base name without extension
            base_name = Path(file.filename).stem
            
            # Check Audiveris default output location
            output_path = Path(f"/root/.local/share/AudiverisLtd/audiveris/{base_name}/{base_name}.mxl")
            logger.info(f"Looking for output file at: {output_path}")
            
            # Check if output file exists
            if not output_path.exists():
                logger.error("Output file not found after Audiveris processing")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to generate MusicXML output"
                )
            
            logger.info(f"Output file found: {output_path}")
            
            # Clean up temporary TIFF if it was created
            if tiff_path:
                try:
                    os.unlink(tiff_path)
                    logger.info("Temporary TIFF file cleaned up")
                except OSError as e:
                    logger.warning(f"Failed to clean up TIFF file: {e}")
            
            # Return the MusicXML file
            return FileResponse(
                path=output_path,
                media_type="application/vnd.recordare.musicxml+xml",
                filename=output_path.name
            )
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Audiveris processing failed: {e.stderr}")
            raise HTTPException(
                status_code=500,
                detail=f"Audiveris processing failed: {e.stderr}"
            )

@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy"} 