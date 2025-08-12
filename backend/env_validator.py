"""
Environment variable validation module for Kaz Legal Bot backend.
"""

import os
import sys


def validate_environment_variables():
    """
    Validates required environment variables for the backend application.
    Exits the application with descriptive error messages if any are missing or invalid.
    """
    errors = []
    warnings = []
    
    # Required environment variables
    required_vars = {
        'GEMINI_API_KEY': {
            'description': 'Google Gemini API key for AI functionality',
            'example': 'AIzaSyBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'validator': lambda x: x and len(x) > 20 and x.startswith('AIza')
        }
    }
    
    # Optional but recommended environment variables
    optional_vars = {
        'MONGO_URI': {
            'description': 'MongoDB connection string for conversation history',
            'example': 'mongodb+srv://username:password@cluster.mongodb.net/database',
            'validator': lambda x: x and ('mongodb://' in x or 'mongodb+srv://' in x)
        },
        'CORS_ORIGINS': {
            'description': 'Comma-separated list of allowed CORS origins',
            'example': 'https://yourdomain.com,http://localhost:5000',
            'validator': lambda x: x and (',' in x or 'http' in x)
        },
        'PORT': {
            'description': 'Port number for the Flask application',
            'example': '5000',
            'validator': lambda x: x and x.isdigit() and 1000 <= int(x) <= 65535
        },
        'MAX_CONTENT_LENGTH': {
            'description': 'Maximum file upload size in bytes',
            'example': '16777216',
            'validator': lambda x: x and x.isdigit() and int(x) > 0
        }
    }
    
    # Check required variables
    for var_name, config in required_vars.items():
        value = os.getenv(var_name)
        if not value:
            errors.append(f"ERROR REQUIRED: {var_name} is not set.")
            errors.append(f"   Description: {config['description']}")
            errors.append(f"   Example: {config['example']}")
        elif not config['validator'](value):
            errors.append(f"ERROR INVALID: {var_name} has invalid format.")
            errors.append(f"   Current value: {value[:20]}...")
            errors.append(f"   Expected format: {config['example']}")
    
    # Check optional variables
    for var_name, config in optional_vars.items():
        value = os.getenv(var_name)
        if not value:
            warnings.append(f"WARNING OPTIONAL: {var_name} is not set.")
            warnings.append(f"   Description: {config['description']}")
            warnings.append(f"   Example: {config['example']}")
        elif not config['validator'](value):
            warnings.append(f"WARNING INVALID: {var_name} has invalid format.")
            warnings.append(f"   Current value: {value[:50]}")
            warnings.append(f"   Expected format: {config['example']}")
    
    # Print warnings
    if warnings:
        print("WARNING: Environment Variable Warnings:")
        for warning in warnings:
            print(f"   {warning}")
        print()
    
    # Exit if there are errors
    if errors:
        print("ERROR: Environment Variable Validation Failed!")
        print("=" * 60)
        for error in errors:
            print(error)
        print("=" * 60)
        print("Please set the required environment variables and restart the application.")
        print("Create a .env file in the backend directory with the following format:")
        print()
        print("GEMINI_API_KEY=your_api_key_here")
        print("MONGO_URI=your_mongodb_connection_string")
        print("CORS_ORIGINS=http://localhost:5000,http://127.0.0.1:5000")
        print("PORT=5000")
        print("MAX_CONTENT_LENGTH=16777216")
        print()
        sys.exit(1)
    
    print("SUCCESS: Environment variable validation successful!")
    return True