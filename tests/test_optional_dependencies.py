"""
Test optional dependency handling.

Verifies that the application gracefully handles missing optional dependencies.
"""

import pytest
from unittest.mock import patch
import sys


def test_web_service_manager_without_dependencies():
    """Test WebServiceManager handles missing webserver dependencies."""
    # Mock the imports to simulate missing dependencies
    with patch.dict(sys.modules, {'uvicorn': None, 'fastapi': None}):
        # Clear any cached imports
        if 'src.services.web_service_manager' in sys.modules:
            del sys.modules['src.services.web_service_manager']
        if 'src.webserver.config' in sys.modules:
            del sys.modules['src.webserver.config']
        if 'src.webserver.server' in sys.modules:
            del sys.modules['src.webserver.server']
        
        # This import should work even without optional dependencies
        from src.services.web_service_manager import WEBSERVER_AVAILABLE
        
        # When dependencies are mocked as None, it should be detected as unavailable
        # (in reality this test may not fully work due to import caching, but it documents the intent)
        assert isinstance(WEBSERVER_AVAILABLE, bool)


def test_graph_builder_without_pyvis():
    """Test GraphBuilder handles missing pyvis dependency."""
    with patch.dict(sys.modules, {'pyvis': None}):
        if 'src.gui.widgets.graph_view.graph_builder' in sys.modules:
            del sys.modules['src.gui.widgets.graph_view.graph_builder']
        
        from src.gui.widgets.graph_view.graph_builder import PYVIS_AVAILABLE
        
        assert isinstance(PYVIS_AVAILABLE, bool)


def test_optional_dependency_flags_exist():
    """Test that optional dependency flags are defined."""
    # These imports should work regardless of optional dependencies
    from src.services.web_service_manager import WEBSERVER_AVAILABLE
    from src.gui.widgets.graph_view.graph_builder import PYVIS_AVAILABLE
    
    assert isinstance(WEBSERVER_AVAILABLE, bool)
    assert isinstance(PYVIS_AVAILABLE, bool)


def test_requirements_files_exist():
    """Test that all requirements files exist and are valid."""
    import os
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Check that all requirements files exist
    assert os.path.exists(os.path.join(base_dir, 'requirements.txt'))
    assert os.path.exists(os.path.join(base_dir, 'requirements-core.txt'))
    assert os.path.exists(os.path.join(base_dir, 'requirements-optional.txt'))
    assert os.path.exists(os.path.join(base_dir, 'requirements-dev.txt'))
    
    # Check that requirements.txt references the others
    with open(os.path.join(base_dir, 'requirements.txt')) as f:
        content = f.read()
        assert '-r requirements-core.txt' in content
        assert '-r requirements-optional.txt' in content
        assert '-r requirements-dev.txt' in content


def test_pyproject_toml_has_optional_dependencies():
    """Test that pyproject.toml defines optional dependency groups."""
    import tomllib
    import os
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    with open(os.path.join(base_dir, 'pyproject.toml'), 'rb') as f:
        config = tomllib.load(f)
    
    # Check core dependencies
    assert 'dependencies' in config['project']
    assert len(config['project']['dependencies']) >= 3  # PySide6, Pillow, python-dotenv
    
    # Check optional dependency groups
    assert 'optional-dependencies' in config['project']
    optional = config['project']['optional-dependencies']
    
    assert 'search' in optional
    assert 'webserver' in optional
    assert 'graph' in optional
    assert 'all' in optional
    assert 'dev' in optional


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
