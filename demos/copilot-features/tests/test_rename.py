"""Tests for the rename CLI tool."""
import pytest
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "cli"))
from rename import rename_tree, OLD_PREFIX, NEW_PREFIX


@pytest.fixture
def temp_demo():
    """Create a temporary demo directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Create a file with the old prefix in its name
        old_file = tmpdir_path / f"{OLD_PREFIX}module.py"
        old_file.write_text("def globex_function():\n    logger = logging.getLogger('globex_demo')")
        
        # Create a file without the prefix
        normal_file = tmpdir_path / "normal.py"
        normal_file.write_text("# This file has no prefix\nprint('hello')")
        
        # Create a binary file
        binary_file = tmpdir_path / "data.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03")
        
        # Create a file with non-UTF-8 content
        non_utf8_file = tmpdir_path / "bad_encoding.py"
        non_utf8_file.write_bytes(b"\x80\x81\x82")
        
        yield tmpdir_path


def test_rename_file_and_content(temp_demo):
    """Test that files are renamed and content is updated."""
    old_file = temp_demo / f"{OLD_PREFIX}module.py"
    
    exit_code = rename_tree(temp_demo, check=False)
    
    assert exit_code == 0
    assert not old_file.exists()
    
    new_file = temp_demo / f"{NEW_PREFIX}module.py"
    assert new_file.exists()
    
    content = new_file.read_text()
    assert "globex_function" not in content
    assert "chroma_function" in content
    assert "globex_demo" not in content
    assert "chroma_demo" in content


def test_skip_binary_files(temp_demo):
    """Test that binary files are skipped without error."""
    binary_file = temp_demo / "data.bin"
    original_content = binary_file.read_bytes()
    
    exit_code = rename_tree(temp_demo, check=False)
    
    assert exit_code == 0
    assert binary_file.read_bytes() == original_content


def test_skip_non_utf8_files(temp_demo):
    """Test that non-UTF-8 files are skipped without error."""
    non_utf8_file = temp_demo / "bad_encoding.py"
    original_content = non_utf8_file.read_bytes()
    
    exit_code = rename_tree(temp_demo, check=False)
    
    assert exit_code == 0
    assert non_utf8_file.read_bytes() == original_content


def test_check_mode_no_modifications(temp_demo):
    """Test that --check mode does not modify files."""
    old_file = temp_demo / f"{OLD_PREFIX}module.py"
    original_content = old_file.read_text()
    
    exit_code = rename_tree(temp_demo, check=True)
    
    assert exit_code == 1  # Pending changes
    assert old_file.exists()  # File not renamed
    assert old_file.read_text() == original_content  # Content not changed


def test_check_mode_no_pending_changes(temp_demo):
    """Test that --check returns 0 when no changes are pending."""
    normal_file = temp_demo / "normal.py"
    original_content = normal_file.read_text()
    
    exit_code = rename_tree(temp_demo, check=True)
    
    # First run should find pending changes (the prefixed file)
    assert exit_code == 1
    
    # Apply the changes
    rename_tree(temp_demo, check=False)
    
    # Remove files without the prefix to leave only renamed files
    for f in temp_demo.glob("*"):
        if f.is_file() and not f.name.startswith(NEW_PREFIX):
            f.unlink()
    
    # Now check should return 0
    exit_code = rename_tree(temp_demo, check=True)
    assert exit_code == 0


def test_collision_detection(temp_demo):
    """Test that file collision is detected."""
    old_file = temp_demo / f"{OLD_PREFIX}module.py"
    new_file = temp_demo / f"{NEW_PREFIX}module.py"
    new_file.write_text("existing file")
    
    with pytest.raises(FileExistsError, match="destination exists"):
        rename_tree(temp_demo, check=False)


def test_skip_git_and_node_modules(temp_demo):
    """Test that .git and node_modules directories are skipped."""
    git_dir = temp_demo / ".git"
    git_dir.mkdir()
    git_file = git_dir / f"{OLD_PREFIX}config.py"
    git_file.write_text("globex_something")
    
    node_dir = temp_demo / "node_modules"
    node_dir.mkdir()
    node_file = node_dir / f"{OLD_PREFIX}package.py"
    node_file.write_text("globex_something")
    
    exit_code = rename_tree(temp_demo, check=False)
    
    assert exit_code == 0
    assert git_file.exists()
    assert node_file.exists()
    assert git_file.read_text() == "globex_something"
    assert node_file.read_text() == "globex_something"


def test_idempotent_rename(temp_demo):
    """Test that running rename twice produces the same result."""
    exit_code1 = rename_tree(temp_demo, check=False)
    exit_code2 = rename_tree(temp_demo, check=False)
    
    assert exit_code1 == 0
    assert exit_code2 == 0
    
    # Second run should report no changes in check mode
    exit_code3 = rename_tree(temp_demo, check=True)
    assert exit_code3 == 0
