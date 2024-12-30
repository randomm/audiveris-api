import pytest
from pathlib import Path
from fastapi import status
import json
import asyncio
import httpx
from api import app

def test_health_check(test_client):
    """Test health check endpoint"""
    response = test_client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "healthy"}

def test_convert_no_file(test_client):
    """Test conversion endpoint with no file"""
    response = test_client.post("/convert")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_convert_empty_file(test_client):
    """Test conversion endpoint with empty file"""
    files = {"file": ("empty.pdf", b"")}
    response = test_client.post("/convert", files=files)
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

def test_convert_pdf(test_client, test_files_dir):
    """Test conversion of a PDF file"""
    pdf_path = test_files_dir / "o-happy-day.pdf"
    if not pdf_path.exists():
        pytest.skip("Test PDF file not found")
    
    with open(pdf_path, "rb") as f:
        files = {"file": ("o-happy-day.pdf", f, "application/pdf")}
        response = test_client.post("/convert", files=files)
    
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/vnd.recordare.musicxml+xml"
    assert len(response.content) > 0  # Should have content

def test_convert_invalid_file(test_client):
    """Test conversion with invalid file"""
    files = {"file": ("test.pdf", b"invalid content")}
    response = test_client.post("/convert", files=files)
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

def test_convert_oversized_file(test_client):
    """Test conversion with a file that exceeds size limit"""
    # Create a file larger than MAX_FILE_SIZE (10MB)
    oversized_content = b"x" * (11 * 1024 * 1024)  # 11MB
    files = {"file": ("large.pdf", oversized_content)}
    
    response = test_client.post("/convert", files=files)
    assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    assert "exceeds maximum allowed size" in response.json()["detail"]

@pytest.mark.asyncio
async def test_concurrent_conversions(test_client, test_files_dir):
    """Test multiple concurrent conversions"""
    pdf_path = test_files_dir / "o-happy-day.pdf"
    if not pdf_path.exists():
        pytest.skip("Test PDF file not found")
    
    with open(pdf_path, "rb") as f:
        content = f.read()
    
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        # Create 3 concurrent conversion tasks
        files = {"file": ("o-happy-day.pdf", content, "application/pdf")}
        tasks = [
            client.post("/convert", files=files)
            for _ in range(3)
        ]
        
        # Wait for all conversions to complete
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK
            assert len(response.content) > 0

@pytest.mark.asyncio
async def test_stream_conversion_quick(test_client, test_files_dir):
    """Test streaming conversion with a quick file"""
    pdf_path = test_files_dir / "o-happy-day.pdf"
    if not pdf_path.exists():
        pytest.skip("Test PDF file not found")
    
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        with open(pdf_path, "rb") as f:
            files = {"file": ("o-happy-day.pdf", f, "application/pdf")}
            async with client.stream("POST", "/convert/stream", files=files) as response:
                assert response.status_code == status.HTTP_200_OK
                assert "text/event-stream" in response.headers["content-type"]
                
                messages = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])  # Skip "data: " prefix
                        messages.append(data)
                        
                        # Break early if we hit an error
                        if data["status"] == "error":
                            break
                
                # Verify we got progress updates
                assert len(messages) > 0
                
                # Check message sequence
                assert messages[0]["status"] == "processing"
                
                # Verify message format
                for msg in messages:
                    assert "status" in msg
                    assert "message" in msg
                    assert msg["status"] in ["processing", "complete", "error"]

@pytest.mark.asyncio
async def test_stream_conversion_long(test_client, test_files_dir):
    """Test streaming conversion with a longer file"""
    pdf_path = test_files_dir / "messiah.pdf"
    if not pdf_path.exists():
        pytest.skip("Test PDF file not found")
    
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        with open(pdf_path, "rb") as f:
            files = {"file": ("messiah.pdf", f, "application/pdf")}
            response = await client.post("/convert/stream", files=files)
            assert response.status_code == status.HTTP_200_OK
            assert "text/event-stream" in response.headers["content-type"]
            
            # Parse SSE messages from response
            messages = []
            for line in response.text.split('\n'):
                if line.startswith("data: "):
                    data = json.loads(line[6:])  # Skip "data: " prefix
                    messages.append(data)
                    
                    # Break early if we hit an error
                    if data["status"] == "error":
                        break
            
            # Verify we got progress updates
            assert len(messages) > 0
            
            # Check message sequence
            assert messages[0]["status"] == "processing"
            
            # If we got an error, print it for debugging
            if messages[-1]["status"] == "error":
                print(f"Conversion error: {messages[-1].get('message', 'No error message')}")

@pytest.mark.asyncio
async def test_stream_conversion_invalid_file(test_client):
    """Test streaming conversion with invalid file"""
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        files = {"file": ("test.pdf", b"invalid content")}
        response = await client.post("/convert/stream", files=files)
        assert response.status_code == status.HTTP_200_OK
        assert "text/event-stream" in response.headers["content-type"]
        
        # Parse SSE messages from response
        messages = []
        for line in response.text.split('\n'):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                messages.append(data)
        
        # Should get an error message
        assert len(messages) > 0
        assert messages[0]["status"] == "processing"
        assert messages[-1]["status"] == "error"
        assert any("failed" in msg.get("message", "").lower() for msg in messages)

@pytest.mark.asyncio
async def test_stream_conversion_oversized_file(test_client):
    """Test streaming conversion with a file that exceeds size limit"""
    # Create a file larger than MAX_FILE_SIZE (10MB)
    oversized_content = b"x" * (11 * 1024 * 1024)  # 11MB
    
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        files = {"file": ("large.pdf", oversized_content)}
        response = await client.post("/convert/stream", files=files)
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert "exceeds maximum allowed size" in response.json()["detail"] 