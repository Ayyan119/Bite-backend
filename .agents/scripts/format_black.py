#!/usr/bin/env python3
import sys
import json
import os
import subprocess

def main():
    try:
        input_data = json.load(sys.stdin)
    except Exception:
        print(json.dumps({}))
        return

    tool_call = input_data.get("toolCall", {})
    tool_name = tool_call.get("name", "")
    args = tool_call.get("args", {})

    target_file = None
    if tool_name in ["replace_file_content", "write_to_file"]:
        target_file = args.get("TargetFile")

    if target_file and target_file.endswith(".py") and os.path.exists(target_file):
        try:
            # Find black executable or python module
            black_cmd = ["/home/jiggra/.local/bin/black", target_file]
            subprocess.run(black_cmd, capture_output=True, text=True, check=False)
        except Exception:
            pass

    print(json.dumps({}))

if __name__ == "__main__":
    main()
