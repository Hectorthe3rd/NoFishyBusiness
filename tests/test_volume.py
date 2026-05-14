import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import ValidationError
from backend.models import VolumeRequest
from backend.tools.volume import calculate_volume

def test_valid_input_returns_both_fields():
    result = calculate_volume(24.0, 12.0, 16.0)
    assert "volume_gallons" in result
    assert "weight_pounds" in result
    assert result["volume_gallons"] == round((24.0 * 12.0 * 16.0) / 231.0, 2)
    assert result["weight_pounds"] == round(result["volume_gallons"] * 8.34, 2)

def test_zero_length_raises_validation_error():
    with pytest.raises(ValidationError):
        VolumeRequest(length=0.0, width=12.0, depth=16.0)

def test_zero_width_raises_validation_error():
    with pytest.raises(ValidationError):
        VolumeRequest(length=24.0, width=0.0, depth=16.0)

def test_zero_depth_raises_validation_error():
    with pytest.raises(ValidationError):
        VolumeRequest(length=24.0, width=12.0, depth=0.0)

def test_negative_dimension_raises_validation_error():
    with pytest.raises(ValidationError):
        VolumeRequest(length=-1.0, width=12.0, depth=16.0)

def test_non_numeric_input_raises_validation_error():
    with pytest.raises(ValidationError):
        VolumeRequest(length="abc", width=12.0, depth=16.0)

def test_known_volume_calculation():
    # 10-gallon tank: 20" x 10" x 12"
    result = calculate_volume(20.0, 10.0, 12.0)
    assert result["volume_gallons"] == round((20.0 * 10.0 * 12.0) / 231.0, 2)
    assert result["weight_pounds"] == round(result["volume_gallons"] * 8.34, 2)
