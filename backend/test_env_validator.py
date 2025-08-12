#!/usr/bin/env python3
"""
Test script for environment variable validation.
"""

import os
import sys

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

def test_validation():
    """Test the environment variable validation function."""
    from env_validator import validate_environment_variables
    
    print("Testing environment variable validation...")
    
    # Save original environment
    original_env = os.environ.copy()
    
    try:
        # Test with missing required variables
        print("\n1. Testing with missing GEMINI_API_KEY...")
        if 'GEMINI_API_KEY' in os.environ:
            del os.environ['GEMINI_API_KEY']
        
        try:
            validate_environment_variables()
            print("ERROR: Should have failed but didn't")
        except SystemExit:
            print("SUCCESS: Correctly failed with missing GEMINI_API_KEY")
        
        # Test with invalid API key
        print("\n2. Testing with invalid GEMINI_API_KEY...")
        os.environ['GEMINI_API_KEY'] = 'invalid_key'
        
        try:
            validate_environment_variables()
            print("ERROR: Should have failed but didn't")
        except SystemExit:
            print("SUCCESS: Correctly failed with invalid GEMINI_API_KEY")
        
        # Test with valid API key
        print("\n3. Testing with valid GEMINI_API_KEY...")
        os.environ['GEMINI_API_KEY'] = 'AIzaSyBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
        
        try:
            result = validate_environment_variables()
            if result:
                print("SUCCESS: Correctly passed with valid GEMINI_API_KEY")
            else:
                print("ERROR: Should have passed but didn't")
        except SystemExit:
            print("ERROR: Should have passed but failed")
        
    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)
    
    print("\nSUCCESS: Environment validation tests completed!")

if __name__ == "__main__":
    test_validation()