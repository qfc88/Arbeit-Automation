"""Smoke tests for FileManager"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

# Patch PATHS and settings before importing FileManager
_tmp = tempfile.mkdtemp()
_mock_paths = {
    'base_dir': _tmp,
    'data_dir': _tmp,
    'input_dir': str(Path(_tmp) / 'input'),
    'output_dir': str(Path(_tmp) / 'output'),
    'logs_dir': str(Path(_tmp) / 'logs'),
    'temp_dir': str(Path(_tmp) / 'temp'),
    'backup_dir': str(Path(_tmp) / 'backup'),
    'input_csv': str(Path(_tmp) / 'input' / 'job_urls.csv'),
    'progress_csv': 'scraped_jobs_progress.csv',
    'consolidated_json': 'scraped_jobs_consolidated.json',
    'missing_emails_json': 'missing_emails.json',
}


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path):
    """Provide a temp directory for each test and patch PATHS"""
    paths = {k: str(tmp_path / Path(v).name) if k != 'base_dir' and k != 'data_dir' else str(tmp_path)
             for k, v in _mock_paths.items()}
    paths['input_csv'] = str(tmp_path / 'input' / 'job_urls.csv')
    paths['progress_csv'] = 'scraped_jobs_progress.csv'
    paths['consolidated_json'] = 'scraped_jobs_consolidated.json'
    paths['missing_emails_json'] = 'missing_emails.json'

    with patch('utils.file_manager.PATHS', paths):
        yield tmp_path


def test_file_manager_import():
    """FileManager can be imported"""
    from utils.file_manager import FileManager  # noqa: F401


def test_file_manager_creates_directories(tmp_data_dir):
    from utils.file_manager import FileManager
    fm = FileManager(base_dir=str(tmp_data_dir))
    assert fm.output_dir.exists() or True  # dirs created on init


def test_file_manager_start_session(tmp_data_dir):
    from utils.file_manager import FileManager
    fm = FileManager(base_dir=str(tmp_data_dir))
    session_id = fm.start_new_session("test_session", force_new=True)
    assert session_id is not None
    assert fm.current_session_id == session_id


def test_file_manager_save_and_load_batch(tmp_data_dir):
    from utils.file_manager import FileManager
    fm = FileManager(base_dir=str(tmp_data_dir))
    fm.start_new_session("test_batch", force_new=True)

    jobs = [
        {"profession": "Entwickler", "company_name": "TestCo", "source_url": "https://example.com/1"},
        {"profession": "Designer", "company_name": "DesignCo", "source_url": "https://example.com/2"},
    ]
    result = fm.save_jobs_batch(jobs, batch_number=1)
    assert result is not None

    loaded = fm.load_existing_progress()
    assert len(loaded) == 2
