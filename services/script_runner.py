import json
import subprocess

CONFIG_PATH = "config/scripts.json"


def run_script(args, kwargs=None):
    if kwargs is None:
        kwargs = {}
    if not args:
        print("Usage: run <script_name>")
        return

    name = args[0]

    with open(CONFIG_PATH) as f:
        scripts = json.load(f)

    if name not in scripts:
        print(f"Script not found: {name}")
        return

    command = scripts[name]
    subprocess.Popen(command, shell=True)
