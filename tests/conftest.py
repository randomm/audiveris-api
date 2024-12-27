import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import shutil
import os
import sys
from pathlib import Path

# Add the parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api import app

@pytest.fixture
def test_client():
    return TestClient(app)

@pytest.fixture
def test_files_dir():
    """Fixture to provide test files directory"""
    return Path(__file__).parent / "test_files"

@pytest.fixture(autouse=True)
def setup_test_environment(test_files_dir):
    """Setup test environment before each test"""
    # Create test files directory if it doesn't exist
    test_files_dir.mkdir(exist_ok=True)
    
    # Copy test files from tmp directory if they don't exist in test_files
    tmp_dir = Path("tmp")
    if tmp_dir.exists():
        for pdf_file in tmp_dir.glob("*.pdf"):
            dest_file = test_files_dir / pdf_file.name
            if not dest_file.exists():
                shutil.copy2(pdf_file, dest_file)
    
    yield
    
    # Cleanup any .mxl files after tests
    for mxl_file in Path().glob("*.mxl"):
        try:
            os.unlink(mxl_file)
        except OSError:
            pass 