"""python3 -m yap_forever <command>: see cli.py. Checks the Python version before anything else."""
import sys


def python_too_old(version: tuple[int, int]) -> str | None:
    if tuple(version) >= (3, 11):
        return None
    return f"yap-forever needs Python 3.11 or newer; you have {version[0]}.{version[1]}."


if __name__ == "__main__":
    message = python_too_old(sys.version_info[:2])
    if message:
        print(message)
        sys.exit(1)
    from yap_forever import cli
    sys.exit(cli.main(sys.argv[1:]))
