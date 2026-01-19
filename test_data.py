#!/usr/bin/env python3
from utils import load_registries, _user_registry
import json

# Load registries
load_registries()

# Get one user to see structure
if _user_registry:
    first_user = next(iter(_user_registry.values()))
    print('Sample user structure:')
    print(json.dumps(first_user, indent=2, default=str))
