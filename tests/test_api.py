import pytest
from pathlib import Path
from fastapi import status

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

@pytest.mark.asyncio
async def test_concurrent_conversions(test_client, test_files_dir):
    """Test multiple concurrent conversions"""
    pdf_path = test_files_dir / "o-happy-day.pdf"
    if not pdf_path.exists():
        pytest.skip("Test PDF file not found")
    
    with open(pdf_path, "rb") as f:
        content = f.read()
    
    # Test 3 concurrent conversions
    files = {"file": ("o-happy-day.pdf", content, "application/pdf")}
    responses = []
    for _ in range(3):
        response = test_client.post("/convert", files=files)
        responses.append(response)
    
    # All should succeed
    for response in responses:
        assert response.status_code == status.HTTP_200_OK
        assert len(response.content) > 0 