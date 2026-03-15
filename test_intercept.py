import sys
import json
import os

with open("/tmp/mcp_intercept.log", "a") as f:
    for line in sys.stdin:
        f.write(line)
        f.flush()
        
        # just proxy to the real one
        # but wait we just want to see the initialize request
